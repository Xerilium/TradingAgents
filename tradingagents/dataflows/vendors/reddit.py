"""Reddit search fetcher for ticker-specific discussion posts.

Reads Reddit's public Atom/RSS search feed, searching all subreddits in one
combined request. The JSON search endpoint is WAF-blocked (``HTTP 403``) for
anonymous clients (#862), so RSS is the only path; it carries no score or comment
counts. Transient reads use the research retry setting; every wait is capped at 30 seconds.

A fetch that fails is reported as ``<unavailable>``, never as "no posts found":
the two are different claims, and passing a rate-limited fetch off as silence
hands the sentiment analyst a signal that was never observed (#1295).

No API key required. Returns formatted plaintext blocks ready for prompt
injection and degrades gracefully — returns a placeholder string rather than
raising, so callers never special-case missing data.
"""

from __future__ import annotations

import hashlib
import html
import http.client
import json
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.date_window import coverage_gap, in_window
from tradingagents.dataflows.symbols import crypto_base

logger = logging.getLogger(__name__)


def _within_window(posts, start_date, end_date):
    """Keep only posts published in [start_date, end_date] (look-ahead safe).

    No window (both None) leaves the list untouched for live callers. A post with
    no ``created_utc`` epoch is dropped in a historical window (#1220).
    """
    if not (start_date and end_date):
        return posts
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return [p for p in posts if in_window(_posted_at(p), start_dt, end_dt)]


def _posted_at(post) -> datetime | None:
    """A post's ``created_utc`` epoch as a UTC datetime, or None when missing."""
    ts = post.get("created_utc")
    return datetime.fromtimestamp(ts, tz=UTC) if ts else None


def _coverage_dates(posts, page_limit=None) -> list:
    """Dates that bound the feed's coverage. The search is limited to the last
    week (``t=week``), so the lookback start bounds it even when nothing came
    back; a full page may have cut older matches off, so then only the posts
    themselves do."""
    dates = [_posted_at(p) for p in posts]
    if len(posts) < (page_limit if page_limit is not None else _FEED_PAGE):
        dates.append(datetime.now(UTC) - _SEARCH_LOOKBACK)
    return dates


_RSS = "https://www.reddit.com/r/{sub}/search.rss?{qs}"
# A descriptive, identified User-Agent (per Reddit's API etiquette). Reddit
# blocks generic/anonymous tokens like bare "Mozilla/5.0" or "curl/…" but
# serves this one on both endpoints; the RSS feed accepts it even when the
# JSON search endpoint 403s, so no browser-spoofing is needed.
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Default subreddits ordered roughly by signal density for ticker-specific
# discussion. wallstreetbets has the most volume but most noise; stocks /
# investing trend more measured. Caller can override.
DEFAULT_SUBREDDITS = ("wallstreetbets", "stocks", "investing")

# Crypto is discussed in crypto communities, where a coin's own subreddit carries
# most of it; the stock subreddits above barely mention it.
CRYPTO_SUBREDDITS = ("CryptoCurrency", "CryptoMarkets")
_COIN_SUBREDDITS = {"BTC": "Bitcoin", "ETH": "ethereum", "SOL": "solana"}


def subreddits_for(ticker: str) -> tuple[str, ...]:
    """The subreddits searched for ``ticker``: crypto communities for a crypto pair."""
    base = crypto_base(ticker)
    if not base:
        return DEFAULT_SUBREDDITS
    coin = _COIN_SUBREDDITS.get(base)
    return ((coin,) if coin else ()) + CRYPTO_SUBREDDITS

# Reddit's maximum page size. A week of posts for a ticker across the default
# subreddits fits well inside one page, which keeps a high-volume subreddit from
# crowding the others out of a combined search.
_FEED_PAGE = 100


_SEARCH_LOOKBACK = timedelta(days=7)  # matches t=week below


def _search_qs(ticker: str, limit: int) -> str:
    return urlencode({
        "q": ticker,
        "restrict_sr": "on",
        "sort": "new",
        "t": "week",  # last 7 days
        "limit": limit,
    })


def _iso_to_timestamp(iso_str: str | None) -> float | None:
    """Parse an Atom ``published`` timestamp to a UTC epoch, or None."""
    if not iso_str:
        return None
    try:
        normalized = iso_str[:-1] + "+00:00" if iso_str.endswith("Z") else iso_str
        return datetime.fromisoformat(normalized).timestamp()
    except (ValueError, TypeError):
        return None


def _strip_html(content: str) -> str:
    """Reduce the HTML body Reddit embeds in an Atom entry to plain text."""
    if not content:
        return ""
    # Reddit wraps the real selftext between SC_OFF / SC_ON markers.
    if "<!-- SC_OFF -->" in content and "<!-- SC_ON -->" in content:
        content = content.split("<!-- SC_OFF -->")[1].split("<!-- SC_ON -->")[0]
    text = re.sub(r"<[^>]+>", " ", content)
    return " ".join(html.unescape(text).split())


_REDDIT_FETCH_LOCK = threading.Lock()
_REDDIT_COOLDOWN_UNTIL = 0.0


# Reddit search feeds are small (a page of results); cap the read so a
# compromised or misbehaving endpoint can't stream an unbounded body into
# memory before we parse it. Overflow raises http.client.HTTPException, which
# both fetch paths already treat as a failed fetch (degrade to empty / RSS).
_MAX_FEED_BYTES = 5 * 1024 * 1024


def _check_cancelled(cancelled):
    if cancelled and cancelled():
        raise InterruptedError("Research cancelled")


def _wait(seconds, cancelled):
    end = time.monotonic() + seconds
    while True:
        _check_cancelled(cancelled)
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.2, remaining))


def _read_capped(resp) -> bytes:
    """Read a response body bounded to ``_MAX_FEED_BYTES``, raising on overflow."""
    data = resp.read(_MAX_FEED_BYTES + 1)
    if len(data) > _MAX_FEED_BYTES:
        raise http.client.HTTPException(
            f"Reddit feed exceeded {_MAX_FEED_BYTES} bytes; refusing to parse"
        )
    return data


def _fetch_subreddit_rss(
    ticker: str,
    sub: str,
    limit: int,
    timeout: float,
    cancelled=None,
) -> list[dict] | str:
    """Fetch one combined Atom feed, retrying transient failures before giving up."""
    global _REDDIT_COOLDOWN_UNTIL
    from tradingagents.dataflows.router import observe_source_call, source_retry_plan

    url = _RSS.format(sub=sub, qs=_search_qs(ticker, limit))
    req = Request(url, headers={"User-Agent": _UA})
    failures = []
    retries = get_config().get("research_retries", 10)
    for attempt in range(1, retries + 2):
        _check_cancelled(cancelled)
        _wait(max(0.0, _REDDIT_COOLDOWN_UNTIL - time.monotonic()), cancelled)
        retry = {"attempt": attempt, "retry_action": "not_needed"}

        def read_response():
            global _REDDIT_COOLDOWN_UNTIL
            try:
                with urlopen(req, timeout=timeout) as resp:
                    return _read_capped(resp)
            except (OSError, http.client.HTTPException) as exc:
                if isinstance(exc, InterruptedError):
                    raise
                retry.update(source_retry_plan(exc, attempt=attempt))
                if retry["failure_kind"] == "rate_limited":
                    _REDDIT_COOLDOWN_UNTIL = max(
                        _REDDIT_COOLDOWN_UNTIL,
                        time.monotonic() + retry["retry_after_seconds"],
                    )
                raise

        try:
            raw = observe_source_call(
                "reddit_rss", "reddit", "http_response_bytes",
                read_response, retry=retry, ticker=ticker,
            )
            root = None

            def parse_response():
                nonlocal root
                root = ET.fromstring(raw)
                if root.tag != f"{{{_ATOM_NS['atom']}}}feed":
                    raise ET.ParseError("Reddit response is not an Atom feed")
                entries = root.findall("atom:entry", _ATOM_NS)
                for entry in entries:
                    title = entry.find("atom:title", _ATOM_NS)
                    published = entry.find("atom:published", _ATOM_NS)
                    link = entry.find("atom:link", _ATOM_NS)
                    if (title is None or not title.text or published is None
                            or _iso_to_timestamp(published.text) is None
                            or link is None or not link.get("href")):
                        raise ET.ParseError("Reddit Atom feed contains a malformed entry")
                return {"root_tag": root.tag, "entry_count": len(entries)}

            observe_source_call("reddit_rss_parse", "reddit", "parsed_feed_metadata",
                                parse_response, requirement="supplemental", ticker=ticker)
            break
        except (OSError, http.client.HTTPException, ET.ParseError) as exc:
            if isinstance(exc, InterruptedError):
                raise
            failures.append(dict(retry))
            if retry["retry_action"] != "retry":
                logger.warning("Reddit RSS fetch failed for r/%s · %s after %d attempts: %s",
                               sub, ticker, attempt, type(exc).__name__)
                return f"<Reddit unavailable: {json.dumps({'error_class': type(exc).__name__, 'attempts': failures})}; this is not an absence of discussion>"
            logger.warning("Reddit RSS r/%s · %s: retry %d/%d in %.1fs",
                           sub, ticker, attempt, retries, retry["retry_after_seconds"])
            _wait(retry["retry_after_seconds"], cancelled)

    posts = []
    for entry in root.findall("atom:entry", _ATOM_NS)[:limit]:
        title_el = entry.find("atom:title", _ATOM_NS)
        published_el = entry.find("atom:published", _ATOM_NS)
        content_el = entry.find("atom:content", _ATOM_NS)
        category_el = entry.find("atom:category", _ATOM_NS)
        posts.append({
            "url": entry.find("atom:link", _ATOM_NS).get("href", "") if entry.find("atom:link", _ATOM_NS) is not None else "",
            "title": (title_el.text if title_el is not None else "") or "",
            "created_utc": _iso_to_timestamp(
                published_el.text if published_el is not None else None
            ),
            "selftext": _strip_html(content_el.text if content_el is not None else ""),
            # A combined feed names each entry's subreddit; a single-subreddit
            # feed may omit it, and then it can only be that one.
            "subreddit": category_el.get("term") if category_el is not None
            else (sub if "+" not in sub else ""),
        })
    return posts


def fetch_reddit_posts(
    ticker: str,
    subreddits: Iterable[str] | None = None,
    *,
    limit_per_sub: int | None = None,
    timeout: float = 10.0,
    start_date: str | None = None,
    end_date: str | None = None,
    screen=None,
    limit: int | None = None,
    on_acquisition=None,
    cancelled=None,
) -> str:
    """Fetch recent Reddit posts mentioning ``ticker`` across finance
    subreddits (by default ``subreddits_for(ticker)``) and return them as a
    formatted plaintext block.

    All subreddits are searched in one combined feed (``r/a+b+c``): anonymous
    RSS allows about one request per minute per IP, so a request per subreddit
    spent a back-off on almost every run. Each entry names its subreddit, and
    posts are grouped back by it.

    When ``start_date``/``end_date`` (yyyy-mm-dd) are given, posts are trimmed to
    that window so a historical run does not leak current discussion into a
    backtest (#1220).

    ``screen``, when given, takes each post's title and body and returns a keep
    flag per post and a note line that heads the block. It runs before the
    per-subreddit cut, so the posts it keeps fill the slots.
    """
    if cancelled is None:
        from tradingagents.dataflows.router import source_cancelled
        cancelled = source_cancelled
    subreddits = list(subreddits or subreddits_for(ticker))
    # Crypto reaches us as a Yahoo pair (BTC-USD); search Reddit for the base
    # ("BTC") so the query actually matches discussion instead of near-nothing.
    ticker = crypto_base(ticker) or ticker
    label = ", ".join(f"r/{s}" for s in subreddits)
    requested = limit if limit is not None else get_config().get("social_screen_max_posts", 100)
    def report(status, reason=None, **details):
        if on_acquisition:
            on_acquisition({"status": status, "reason": reason, **details})

    while not _REDDIT_FETCH_LOCK.acquire(timeout=0.2):
        _check_cancelled(cancelled)
    try:
        _check_cancelled(cancelled)
        _wait(max(0.0, _REDDIT_COOLDOWN_UNTIL - time.monotonic()), cancelled)
        fetched = _fetch_subreddit_rss(ticker, "+".join(subreddits), min(requested, _FEED_PAGE), timeout, cancelled=cancelled)
    finally:
        _REDDIT_FETCH_LOCK.release()
    if isinstance(fetched, str):
        report("unavailable", "Reddit feed request or parsing failed; inspect source receipts")
        return fetched

    window = bool(start_date and end_date)
    posts = _within_window(fetched, start_date, end_date)
    page_limit = min(requested, _FEED_PAGE)
    gap = window and coverage_gap(
        _coverage_dates(fetched, page_limit), start_date, end_date,
        "Reddit search", f"discussion of {ticker.upper()}",
    )
    limited = bool(gap) or len(fetched) >= page_limit
    reason = (str(gap) if gap else "The requested feed page was full; additional matches are unverified" if limited else None)
    report("limited" if limited else "populated" if posts else "empty", reason,
           fetched_count=len(fetched), eligible_count=len(posts), requested_limit=page_limit,
           coverage="Public RSS searches only the past week; older matches are unverified")
    if not posts:
        period = f"within {start_date}..{end_date}" if window else "in the past 7 days"
        return gap or f"<no Reddit posts found mentioning {ticker.upper()} across {label} {period}>"

    def sub_of(p):
        return p.get("subreddit") or (subreddits[0] if len(subreddits) == 1 else "unknown")

    note, screened_out = f"Reddit acquisition: requested up to {requested} posts; public RSS serves at most {_FEED_PAGE} matches from the past week. Older or additional matches are not verified.", set()
    if screen:
        keep, screening_note = screen([f"{p.get('title') or ''}\n{p.get('selftext') or ''}"
                             for p in posts])
        note += "\n" + screening_note
        screened_out = {sub_of(p).lower() for p, kept in zip(posts, keep, strict=True) if not kept}
        posts = [p for p, kept in zip(posts, keep, strict=True) if kept]

    # Group by the subreddit each entry names, in the requested order. Nothing
    # is dropped: an unlabelled post from a one-subreddit request belongs to it,
    # and any other name gets its own block.
    by_sub = {s.lower(): (s, []) for s in subreddits}
    for p in posts:
        by_sub.setdefault(sub_of(p).lower(), (sub_of(p), []))[1].append(p)

    page_full = len(fetched) >= page_limit
    blocks = []
    for sub, sub_posts in by_sub.values():
        if not sub_posts:
            if sub.lower() in screened_out:
                blocks.append(f"r/{sub}: <no posts about {ticker.upper()} after screening>")
            else:
                blocks.append(
                    f"r/{sub}: <not among the newest {page_limit} matches across {label}>"
                    if page_full else f"r/{sub}: <no posts found mentioning {ticker.upper()}>"
                )
            continue
        sub_posts = sub_posts[:limit_per_sub] if limit_per_sub is not None else sub_posts
        lines = [f"r/{sub} — {len(sub_posts)} recent posts mentioning {ticker.upper()}:"]
        for p in sub_posts:
            text_id = hashlib.sha256(f"{p.get('title') or ''}\n{p.get('selftext') or ''}".encode()).hexdigest()
            title = (p.get("title") or "").replace("\n", " ").strip()
            created = p.get("created_utc")
            created_str = time.strftime("%Y-%m-%d", time.gmtime(created)) if created else "?"
            selftext = (p.get("selftext") or "").replace("\n", " ").strip()
            lines.append(
                f"  [reddit:{text_id}] [{created_str}] {title}"
                + (f"\n    body: {selftext}" if selftext else "")
                + (f"\n    Source: {p['url']}" if p.get("url") else "")
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(([note] if note else []) + blocks)
