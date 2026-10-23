"""StockTwits public symbol-stream fetcher.

StockTwits exposes a per-symbol message stream at
``api.stocktwits.com/api/2/streams/symbol/{ticker}.json`` that requires no
API key, no OAuth, and no registration. Each message includes a
user-labeled sentiment field (``Bullish``/``Bearish``/null), the message
body, timestamp, and posting user.

The function is deliberately self-contained: short timeout, graceful
degradation on any HTTP or parse failure, and a string return type so
the calling agent gets a uniform interface regardless of whether the
network call succeeded.
"""

from __future__ import annotations

import contextlib
import hashlib
import html
import http.client
import json
import logging
from datetime import datetime
from urllib.request import Request, urlopen

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.date_window import coverage_gap, in_window
from tradingagents.dataflows.symbols import crypto_base

logger = logging.getLogger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"


def _created_at(message) -> datetime | None:
    """Parse a message's ISO 8601 ``created_at``; None when missing or malformed."""
    raw = message.get("created_at")
    if not raw:
        return None
    with contextlib.suppress(ValueError, TypeError):
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return None


def _within_window(messages, start_date, end_date):
    """Keep only messages published in [start_date, end_date] (look-ahead safe).

    No window (both None) leaves the list untouched for live callers. A message
    whose ``created_at`` (ISO 8601) is unparseable is dropped in a historical
    window, since we can't prove it isn't from after the as-of date (#1220).
    """
    if not (start_date and end_date):
        return messages
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return [m for m in messages if in_window(_created_at(m), start_dt, end_dt)]


def _body(message) -> str:
    """The message text; the API serves it HTML-escaped (``&amp;``, ``&#39;``)."""
    body = html.unescape(message.get("body") or "")
    quoted = (message.get("reshare_message") or {}).get("message") or {}
    return body + (f"\nQuoted post: {html.unescape(quoted.get('body') or '')}" if quoted else "")


def _stocktwits_symbol(ticker: str) -> str:
    """Map a crypto pair to StockTwits' ``<BASE>.X`` convention.

    StockTwits lists crypto as ``BTC.X`` (Yahoo's ``BTC-USD`` form 404s), so any
    crypto symbol resolves to its base plus ``.X``; other symbols pass through
    upper-cased.
    """
    base = crypto_base(ticker)
    return f"{base}.X" if base else ticker.strip().upper()


def fetch_stocktwits_messages(
    ticker: str,
    limit: int | None = None,
    timeout: float = 10.0,
    start_date: str | None = None,
    end_date: str | None = None,
    screen=None,
) -> str:
    """Fetch recent StockTwits messages for ``ticker`` and return them as a
    formatted plaintext block ready for prompt injection.

    When ``start_date``/``end_date`` (yyyy-mm-dd) are given, messages are trimmed
    to that window, so a historical run never sees today's chatter (#1220). The
    public stream only serves recent messages, so a window it cannot reach is
    reported as unavailable rather than as silence.

    ``screen``, when given, takes the message bodies and returns a keep flag per
    message and a note line that heads the block.

    Returns a placeholder string when the endpoint is unreachable, the
    symbol has no messages, or the response shape is unexpected — the
    caller never has to special-case None or exceptions.
    """
    if limit is None:
        limit = get_config().get("social_screen_max_posts", 100)
    url = _API.format(ticker=_stocktwits_symbol(ticker))
    from tradingagents.dataflows.router import observe_source_call

    def read_response(request):
        with urlopen(request, timeout=timeout) as resp:
            return resp.read()

    try:
        fetched, seen, cursor, more = [], set(), None, True
        while more and len(_within_window(fetched, start_date, end_date)) < limit:
            request = Request(url + (f"?max={cursor}" if cursor else ""), headers={"User-Agent": _UA, "Accept": "application/json"})
            raw = observe_source_call("stocktwits_stream", "stocktwits", "http_response_bytes", lambda request=request: read_response(request),
                                      ticker=ticker, start_date=start_date, end_date=end_date)
            data = json.loads(raw)
            page = data.get("messages", []) if isinstance(data, dict) else []
            fresh = [m for m in page if m.get("id") not in seen]
            fetched.extend(fresh)
            seen.update(m.get("id") for m in fresh)
            next_cursor = (data.get("cursor") or {}).get("max")
            more = bool(fresh and next_cursor and next_cursor != cursor and (data.get("cursor") or {}).get("more"))
            if start_date and fresh and all(m.get("created_at", "9999")[:10] < start_date for m in fresh):
                more = False
            cursor = next_cursor
    except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
        # OSError covers URLError/TimeoutError/connection resets; HTTPException
        # covers chunked-transfer errors (IncompleteRead/BadStatusLine, #1024).
        logger.warning("StockTwits fetch failed for %s: %s", ticker, type(exc).__name__)
        return f"<stocktwits unavailable: {type(exc).__name__}>"

    messages = _within_window(fetched, start_date, end_date)[:limit]
    if not messages:
        if start_date and end_date:
            gap = coverage_gap(
                (_created_at(m) for m in fetched), start_date, end_date,
                "StockTwits", f"messages about ${ticker.upper()}",
            )
            return gap or (
                f"<no StockTwits messages for ${ticker.upper()} within "
                f"{start_date}..{end_date}>"
            )
        return f"<no StockTwits messages found for ${ticker.upper()}>"

    note = f"StockTwits acquisition: {len(messages)} in-window messages, requested maximum {limit}; newest-page sample, not exhaustive window coverage."
    if screen:
        keep, screening_note = screen([_body(m) for m in messages])
        note += "\n" + screening_note
        screened = len(messages)
        messages = [m for m, kept in zip(messages, keep, strict=True) if kept]
        if not messages:
            return f"{note}\n\n<none of the {screened} StockTwits messages is about ${ticker.upper()}>"

    lines = []
    bullish = bearish = unlabeled = 0
    for m in messages:
        created = m.get("created_at", "")
        user = (m.get("user") or {}).get("username", "?")
        entities = m.get("entities") or {}
        sentiment_obj = entities.get("sentiment") or {}
        sentiment = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None
        body = _body(m).replace("\n", " ").strip()

        if sentiment == "Bullish":
            bullish += 1
            tag = "Bullish"
        elif sentiment == "Bearish":
            bearish += 1
            tag = "Bearish"
        else:
            unlabeled += 1
            tag = "no-label"
        text_id = hashlib.sha256(_body(m).encode()).hexdigest()
        lines.append(f"[stocktwits:{text_id}] [{created} · @{user} · {tag}] {body}")

    total = bullish + bearish + unlabeled
    bull_pct = round(100 * bullish / total) if total else 0
    bear_pct = round(100 * bearish / total) if total else 0
    summary = (
        f"Bullish: {bullish} ({bull_pct}%) · "
        f"Bearish: {bearish} ({bear_pct}%) · "
        f"Unlabeled: {unlabeled} · "
        f"Total: {total} most-recent messages"
    )
    return (f"{note}\n\n" if note else "") + summary + "\n\n" + "\n".join(lines)
