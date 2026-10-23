"""Per-post social screening: Maenifold Laya for the desk, optional Jev for CLI.

``laya_screen`` uses the injected MCP SDK gateway, a shared timed serial
screen, and exact multilingual token receipts. Its labels are sentiment
evidence, never research approval or trading authority.

Jev answers typed questions with calibrated probabilities. Each StockTwits or
Reddit post is asked two: is it about the instrument, and which way does it
lean on the instrument's stock. Code turns the answers into what the Sentiment
Analyst reads: posts that are clearly about something else are dropped, and a
stance count over the rest heads the source's block.

Configured by TypeSafe's own SDK variables, ``TYPESAFE_API_KEY``,
``TYPESAFE_DEFAULT_MODEL`` and ``TYPESAFE_BASE_URL`` (OpenRouter serves Jev at
``https://openrouter.ai/api``). Without a key nothing here runs; if any request fails, the source's posts are kept unscreened and the
block says screening was unavailable.
"""

import asyncio
import copy
import hashlib
import logging
import math
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from contextlib import contextmanager
from contextvars import copy_context
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from tradingagents.agents.context import resolve_instrument_identity
from tradingagents.dataflows.router import observe_jev_call, queued_jev_job

logger = logging.getLogger(__name__)

# Social classification is evidence, never permission to place an order.
_LAYA_LANE = threading.Condition()
_LAYA_QUEUE = deque()
SOCIAL_ADMISSION_VERSION = "stance-contract-v2"
LAYA_QUESTIONS = {
    "about": {"kind": "yes_no", "instructions": "Is this post about {instrument}: the company, its stock, products or outlook?",
              "criteria": {
                  "true": "Discusses the named company itself: its stock, products or outlook.",
                  "false": "Names the company only in passing or in a list of tickers, is spam or promotion, or discusses a different company.",
              }},
    "stance": {"kind": "choice", "instructions": "What sentiment does the author express about {instrument} stock? Judge the author, not an opponent quoted in the post.",
               "criteria": {"bullish": "Positive: expects the share price to rise, buys shares, or holds them long.",
                            "bearish": "Negative: expects the share price to fall, sells shares, or shorts them.",
                            "neutral": "No directional opinion about the stock: a question, factual news, or someone else's view quoted."}},
}


def _laya_payload(value):
    return value["data"] if isinstance(value, dict) and value.get("success") is True else value


def _distribution(answer, labels):
    if not isinstance(answer, dict):
        raise ValueError("missing answer")
    values = answer.get("probabilities")
    if (not isinstance(values, dict) or set(values) != set(labels)
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                   for v in values.values()) or abs(sum(values.values()) - 1) > .001):
        raise ValueError("invalid probability distribution")
    return values


@contextmanager
def _laya_turn(budget, max_seconds, cancelled):
    """FIFO chunks; charge processing time, not time waiting behind other stocks."""
    ticket, queued_at, started = object(), time.monotonic(), None
    active_time = budget.setdefault("time_policy", "wall_clock_v1" if budget.get("expires_at") else "active_lane_v1") == "active_lane_v1"
    if not active_time and budget.get("deadline") is None:
        budget["deadline"] = time.monotonic() + max(0, budget.setdefault("expires_at", time.time() + max_seconds) - time.time())
    with _LAYA_LANE:
        _LAYA_QUEUE.append(ticket)
    try:
        with _LAYA_LANE:
            while _LAYA_QUEUE[0] is not ticket:
                if cancelled():
                    raise InterruptedError("Social screening stopped by operator")
                if not active_time and time.monotonic() >= budget["deadline"]:
                    raise TimeoutError("Original social screening time budget expired while queued")
                _LAYA_LANE.wait(.25)
        started = time.monotonic()
        budget["queue_wait_seconds"] = budget.get("queue_wait_seconds", 0) + started - queued_at
        if active_time:
            budget["deadline"] = started + budget.setdefault("remaining_seconds", max_seconds)
        yield
    finally:
        if active_time and started is not None:
            budget["remaining_seconds"] = max(0, budget["deadline"] - time.monotonic())
            budget["deadline"] = None
        with _LAYA_LANE:
            _LAYA_QUEUE.remove(ticket)
            _LAYA_LANE.notify_all()


def laya_screen(ticker, gateway, *, max_posts=None, budget=None, on_evidence=None,
                source="social", cancelled=lambda: False, instrument=None, retained=None, on_progress=None):
    """Existing fetcher hook, with serial SDK calls and an honest unclassified remainder.

    One symbol shares a configurable 100-post / 600-second budget across sources.
    Five-post chunks share a FIFO lane. Processing includes model loading and
    transport; waiting for other stocks does not consume a new run's allowance.
    Unknown outcomes remain unscreened and are never replayed.
    """
    if max_posts is not None and (type(max_posts) is not int or max_posts < 0):
        raise ValueError("max_posts must be a nonnegative integer or None")
    budget = budget if budget is not None else {"remaining": 100 if max_posts is None else max_posts,
                                                 "deadline": None}
    max_seconds = budget.get("max_seconds", 600)
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError("max_seconds must be a positive finite number")
    instrument = instrument or ticker

    def execute(command, parameters):
        def dispatch():
            if cancelled() or time.monotonic() >= budget["deadline"]:
                raise InterruptedError("Social screening stopped; budget exhausted")
        from tradingagents.integrations.maenifold import gateway_observation
        with gateway_observation("laya", command, "gateway_invocation",
                                 parameters=parameters, purpose="social_sentiment") as observed:
            if hasattr(gateway, "aexecute"):
                async def run():
                    remaining = budget["deadline"] - time.monotonic()
                    deadline = asyncio.timeout(max(.01, remaining))
                    try:
                        async with deadline:
                            return await gateway.aexecute("laya", command, parameters, on_dispatch=dispatch)
                    except TimeoutError as exc:
                        # Event-loop timers may fire a clock tick before monotonic
                        # reaches the deadline. Record which limit actually fired.
                        if deadline.expired():
                            exc.social_budget_expired = True
                        raise
                result = asyncio.run(run())
            else:
                result = gateway.execute("laya", command, parameters, on_dispatch=dispatch)
            observed.update(output=result, result_available=True)
            return _laya_payload(result)

    def screen(posts):
        keep = [True] * len(posts)
        evidence = {"status": "empty" if not posts else "unavailable", "source": source,
                    "admission_version": SOCIAL_ADMISSION_VERSION,
                    "model": "multilingual", "counts": dict.fromkeys(
                        ("bullish", "bearish", "neutral", "unclear", "off_topic", "unscreened"), 0),
                    "posts": [], "total_count": len(posts)}
        rows = evidence["posts"]
        for post in posts:
            rows.append({"text": post, "text_sha256": hashlib.sha256(post.encode()).hexdigest(),
                         "provenance": "complete fetched Reddit title/body" if source == "reddit" else "source message body",
                         "status": "unscreened", "model": "multilingual"})
        if retained is not None:
            if [row["text_sha256"] for row in rows] != [row["text_sha256"] for row in retained["posts"]]:
                raise ValueError("Saved social inputs differ from the resumed source; original labels cannot be reassigned.")
            rows[:] = copy.deepcopy(retained["posts"])
            if any(row["status"] == "pending" for row in rows):
                raise ValueError("A prior social request has an unknown outcome and cannot be replayed.")

        def progress():
            if on_progress:
                on_progress(copy.deepcopy(evidence), budget)
        try:
            progress()
            for start in range(0, len(posts), 5):
                if all(row["status"] == "classified" for row in rows[start:start + 5]):
                    continue
                with _laya_turn(budget, max_seconds, cancelled):
                    for index in range(start, min(start + 5, len(posts))):
                        post = posts[index]
                        if rows[index]["status"] == "classified":
                            continue
                        if cancelled():
                            evidence["stop_reason"] = "operator_cancelled"
                            break
                        if ((max_posts is not None and index >= max_posts)
                                or (budget["remaining"] is not None and budget["remaining"] <= 0)):
                            evidence["stop_reason"] = "post_budget_exhausted"
                            break
                        if time.monotonic() >= budget["deadline"]:
                            evidence["stop_reason"] = "time_budget_exhausted"
                            break
                        parameters = {"state": post,
                                      "questions": copy.deepcopy(LAYA_QUESTIONS), "model": "multilingual"}
                        for question in parameters["questions"].values():
                            question["instructions"] = question["instructions"].format(instrument=instrument)
                        if budget["remaining"] is not None:
                            budget["remaining"] -= 1
                        rows[index]["status"] = "pending"
                        progress()
                        response = execute("decide", parameters)
                        counts = response.get("usage", {}).get("context_budget", {}) if isinstance(response, dict) else {}
                        tokens = counts.get("sequence_tokens", {}) if isinstance(counts, dict) else {}
                        if (not isinstance(counts, dict) or counts.get("model") != "multilingual"
                                or type(counts.get("effective_max_tokens")) is not int or counts["effective_max_tokens"] <= 0
                                or counts.get("questions_complete") is not True or counts.get("state_complete") is not True
                                or set(tokens) != set(LAYA_QUESTIONS)
                                or any(type(n) is not int or not 0 < n <= counts["effective_max_tokens"] for n in tokens.values())):
                            rows[index].update(error="Full input could not be verified; original post retained", result=response)
                            continue
                        rows[index].update(token_budget=counts, result=response)
                        answers = response.get("answers", {}) if isinstance(response, dict) else {}
                        if (not isinstance(answers, dict) or not isinstance(answers.get("about"), dict)
                                or answers["about"].get("kind") != "yes_no"
                                or not isinstance(answers.get("stance"), dict) or answers["stance"].get("kind") != "choice"):
                            raise ValueError("invalid typed social answers")
                        about = _distribution(answers.get("about"), ("true", "false"))["true"]
                        stance = answers.get("stance")
                        probabilities = _distribution(stance, ("bullish", "bearish", "neutral"))
                        choice = stance.get("value")
                        if choice not in probabilities or probabilities[choice] != max(probabilities.values()):
                            raise ValueError("invalid winning stance")
                        about_answer = answers["about"]
                        # Dropping evidence is an action: only the relevance answer's
                        # own confident contract may exclude it. Reconsider/absent
                        # contracts keep the post, even if P(about) is below .3.
                        relevance_certain = about_answer.get("grade") == "auto_execute"
                        # Classifier mistakes must not remove source evidence from the analyst.
                        keep[index] = True
                        stance_grade = stance.get("grade", "unknown")
                        label = (choice if stance_grade == "auto_execute" and probabilities[choice] >= _STANCE_CONFIDENCE
                                 else "unclear")
                        rows[index].update(status="classified", relevance_prediction="off_topic" if about < _OFF_TOPIC_BELOW and relevance_certain else "retained",
                                           about_probability=about, relevance_uncertain=not relevance_certain,
                                           relevance_grade=about_answer.get("grade", "unknown"),
                                           stance=label, raw_prediction=choice, stance_grade=stance_grade,
                                           stance_probability=probabilities[choice])
                        progress()
                if evidence.get("stop_reason"):
                    break
        except Exception as exc:
            from tradingagents.integrations.maenifold import GatewayTimeout
            evidence["error_class"] = type(exc).__name__
            if isinstance(exc, (TimeoutError, GatewayTimeout)):
                expired = (getattr(exc, "social_budget_expired", False)
                           or budget.get("remaining_seconds") == 0
                           or budget.get("deadline") is not None and time.monotonic() >= budget["deadline"])
                evidence["stop_reason"] = "time_budget_exhausted" if expired else "inference_timeout"
                evidence["error"] = (
                    "Social screening time budget expired; remaining posts are unscreened. "
                    if expired else "Laya request timed out; remaining posts are unscreened. "
                ) + ("The in-flight result is unknown and will not be replayed." if any(row["status"] == "pending" for row in rows)
                     else "No inference was dispatched for the remaining posts.")
            else:
                if isinstance(exc, InterruptedError):
                    evidence["stop_reason"] = "operator_cancelled"
                evidence["error"] = str(exc).strip()[:300] or type(exc).__name__
        finally:
            progress()
        for row in rows:
            key = row["stance"] if row["status"] == "classified" else "unscreened"
            evidence["counts"][key] += 1
        counts = evidence["counts"]
        evidence["status"] = ("empty" if not posts else "unavailable" if counts["unscreened"] == len(posts)
                              else "partial" if counts["unscreened"] else "completed")
        if counts["unscreened"] == len(posts) and evidence.get("stop_reason"):
            evidence["status"] = "deferred"
        uncertain_relevance = sum(row.get("relevance_uncertain", False) for row in rows)
        evidence["relevance_uncertain_count"] = uncertain_relevance
        classified = len(posts) - counts["unscreened"]
        evidence["classified_count"] = classified
        evidence["retained_count"] = sum(keep)
        note = ("Laya social sentiment: " + ", ".join(f"{n} {key}" for key, n in counts.items())
                + f". Coverage: {classified} of {len(posts)} fetched posts classified; {sum(keep)} retained. "
                + f"{uncertain_relevance} retained posts have uncertain relevance. "
                + "All fetched posts are retained for analyst review, including classifier off-topic predictions. Classifier relevance and stance are fallible annotations; correct them from the original text. Uncertain or missing stance contracts count as unclear; their raw predictions remain in the evidence. User-provided Bullish/Bearish/no-label tags describe a separate signal. "
                + (f"Screening deferred: {evidence['stop_reason']}; fetched posts remain available, not a source failure. " if evidence.get("stop_reason") else "")
                 + (f"Screening error: {evidence['error']} " if evidence.get("error") else "")
                + "Unscreened is not neutral. Classification is evidence, not trade approval.")
        evidence.update(note=note, completed_at=datetime.now(UTC).isoformat())
        screen.evidence = evidence
        if on_evidence:
            on_evidence(copy.deepcopy(evidence))
        annotations = ["Classifier annotations (ID = source:SHA256 of exact screened text; labels are fallible):"]
        for row in rows:
            annotations.append(f"{source}:{row['text_sha256']} | status={row['status']} | "
                               f"stance={row.get('stance', 'unknown')} | raw_prediction={row.get('raw_prediction', 'unknown')} | "
                               f"stance_grade={row.get('stance_grade', 'unknown')}")
        return keep, note + "\n" + "\n".join(annotations)

    screen.evidence = None
    return screen

_DEFAULT_BASE_URL = "https://api.typesafe.ai"
_DEFAULT_MODEL = "jev-latest"
_RETRY_STATUSES = (429, 529)    # rate limited, overloaded: back off and retry
_TRANSIENT = (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError)
_ATTEMPTS = 3
_MAX_WAIT = 30.0
_TIMEOUT = 15.0
_WORKERS = 16                   # well inside the documented 1,200 requests per minute

# A post is dropped only on a clear "not about it"; the uncertain middle stays.
_OFF_TOPIC_BELOW = 0.3
# A stance counts only when Jev is not genuinely uncertain about it.
_STANCE_CONFIDENCE = 0.5

QUESTIONS = {
    "about": {
        "type": "noul",
        "instructions": "Is `post` about `instrument`: the company, its stock, its products or its outlook?",
        "criteria": {
            "true": "`post` discusses `instrument` itself.",
            "false": "`post` names `instrument` only in passing or in a list of tickers, is spam or "
                     "promotion, or is about a different company.",
        },
    },
    "stance": {
        "type": "choice",
        "instructions": "What does the author of `post` expect for the stock price of `instrument`?",
        "criteria": {
            "bullish": "The author expects `instrument`'s stock to rise, or is buying or holding it long.",
            "bearish": "The author expects `instrument`'s stock to fall, or is selling or shorting it.",
            "neutral": "The author gives no view of their own on `instrument`'s stock: a question, "
                       "news without opinion, or someone else's view quoted.",
        },
    },
}


class TypeSafeError(Exception):
    """A System One request that did not produce answers."""


def system_one(state, questions: dict) -> dict[str, dict]:
    """Ask ``questions`` about ``state``; return the answers keyed by question name.

    Rate-limit and overload responses and dropped connections are retried with
    backoff, honouring ``Retry-After``; any other failure raises
    ``TypeSafeError`` at once.
    """
    body = {
        "state": state,
        "model": os.environ.get("TYPESAFE_DEFAULT_MODEL") or _DEFAULT_MODEL,
        "questions": questions,
    }
    headers = {"Authorization": f"Bearer {os.environ.get('TYPESAFE_API_KEY', '')}"}
    backoff, retry_after = 1.0, None
    previous = None
    for attempt in range(_ATTEMPTS):
        if attempt:
            wait = retry_after if retry_after is not None else backoff * random.uniform(0.8, 1.2)
            previous["receipt"].update(retry_action="wait", selected_wait_seconds=wait)
            previous["emit"]()
            time.sleep(wait)
            backoff *= 2
        with observe_jev_call("jev_post", parameters=body, ordinal=attempt + 1) as observed:
            previous = observed
            receipt = observed["receipt"]
            receipt["request_started_at"] = datetime.now(UTC).isoformat()
            request_started = time.monotonic()
            try:
                response = requests.post(_url(), json=body, headers=headers, timeout=_TIMEOUT)
            except requests.RequestException as exc:
                failure, retry_after = type(exc).__name__, None
                receipt.update(outcome="unknown", error_class=failure if failure in {
                    "ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout", "ChunkedEncodingError",
                    "InvalidHeader", "TooManyRedirects"} else "RequestException")
                if isinstance(exc, _TRANSIENT):
                    receipt["retry_action"] = "retry_pending" if attempt + 1 < _ATTEMPTS else "exhausted"
                    continue
                receipt["retry_action"] = "stop"
                break
            finally:
                receipt.update(request_ended_at=datetime.now(UTC).isoformat(),
                               request_elapsed_seconds=time.monotonic() - request_started)
            receipt["http_status"] = response.status_code
            if response.status_code == 200:
                return _answers(response, questions, observed)
            failure, retry_after = f"HTTP {response.status_code}", _retry_after(response)
            receipt.update(outcome="error", retry_after_seconds=retry_after, error_body="not_consumed")
            if response.status_code not in _RETRY_STATUSES:
                receipt["retry_action"] = "stop"
                break
            if retry_after is not None and retry_after > _MAX_WAIT:
                receipt.update(outcome="deferred", retry_action="defer")
                raise TypeSafeError(
                    f"{failure}; Retry-After {retry_after:g} seconds exceeds the "
                    f"{_MAX_WAIT:g}-second automatic wait limit; screening deferred"
                )
            receipt["retry_action"] = "retry_pending" if attempt + 1 < _ATTEMPTS else "exhausted"
    raise TypeSafeError(failure)


def _retry_after(response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        delay = float(value)
    except (TypeError, ValueError):
        try:
            deadline = parsedate_to_datetime(value)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            delay = deadline.timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, delay) if math.isfinite(delay) else None


def _answers(response, questions: dict, observed=None) -> dict[str, dict]:
    try:
        payload = response.json()
        if observed is not None:
            observed.update(output=payload, result_available=True)
        answers = payload["answers"]
        if all(answers[q]["type"] == spec["type"] for q, spec in questions.items()):
            logger.debug("TypeSafe answered with %s", payload.get("model"))
            return answers
    except (ValueError, KeyError, TypeError):
        pass
    raise TypeSafeError("malformed response")


def _stance(answer: dict) -> str:
    choice = answer["choice"]
    if choice not in QUESTIONS["stance"]["criteria"] or answer["confidence"] < _STANCE_CONFIDENCE:
        return "unclear"
    return choice


def _url() -> str:
    """System One's endpoint: the base TypeSafe's SDKs read, plus /v1/systemone."""
    base = os.environ.get("TYPESAFE_BASE_URL") or _DEFAULT_BASE_URL
    return base.rstrip("/") + "/v1/systemone"


def jev_screen(ticker: str):
    """A post screen for the social fetchers, or None without a TypeSafe key.

    The screen takes the post texts and returns one keep flag per post and a
    note line for the top of the source's block.
    """
    if not os.environ.get("TYPESAFE_API_KEY"):
        return None
    name = resolve_instrument_identity(ticker).get("company_name")
    instrument = f"{name} ({ticker})" if name else ticker

    def apply_screen(posts: list[str]) -> tuple[list[bool], str]:
        try:
            answers = _ask_each(instrument, posts)
            keep = [True] * len(posts)
            stances = [_stance(a["stance"]) for a, kept in zip(answers, keep, strict=True) if kept]
        except (KeyError, TypeError):
            return _unscreened(instrument, posts, "malformed response")
        except TypeSafeError as exc:
            return _unscreened(instrument, posts, str(exc))
        counts = ", ".join(f"{stances.count(s)} {s}" for s in ("bullish", "bearish", "neutral", "unclear"))
        return keep, (
            f"Screened by Jev: all {len(posts)} fetched posts retained for analyst review. "
            f"Classifier stance on {instrument}: {counts}. Classifier labels may be wrong; read the original text."
        )

    def screen(posts: list[str]) -> tuple[list[bool], str]:
        with observe_jev_call("jev_batch", parameters={"instrument": instrument, "posts": posts}) as observed:
            keep, note = apply_screen(posts)
            applied = note.startswith("Screened by Jev:")
            observed["receipt"].update(screening_applied=applied, outcome="success" if applied else "unscreened")
            observed.update(output={"keep": keep, "screening_applied": applied}, result_available=True)
            return keep, note

    return screen


def _unscreened(instrument: str, posts: list[str], failure: str) -> tuple[list[bool], str]:
    logger.warning("Jev screening failed for %s: %s", instrument, failure)
    return [True] * len(posts), f"<Jev screening unavailable ({failure}); posts are unscreened>"


def _ask_each(instrument: str, posts: list[str]) -> list[dict]:
    """One request per post. The first failure raises at once: requests not yet
    sent are cancelled, and those in flight finish in the background unread."""
    answers: list = [None] * len(posts)
    pool = ThreadPoolExecutor(max_workers=_WORKERS)

    def ask(job, state):
        with observe_jev_call("jev_job", observation=job) as observed:
            answer = system_one(state, QUESTIONS)
            observed.update(output=answer, result_available=True)
            return answer

    try:
        futures = {}
        for i, post in enumerate(posts):
            state = {"instrument": instrument, "post": post}
            job = queued_jev_job(i, state)
            worker_context, callback_context = copy_context(), copy_context()
            try:
                future = pool.submit(worker_context.run, ask, job, state)
            except BaseException:
                job["receipt"].update(outcome="error", error_class="SubmissionFailed", ended_at=datetime.now(UTC).isoformat())
                job["emit"]()
                raise
            futures[future] = i

            def cancelled(future, observation=job):
                if future.cancelled():
                    observation["receipt"].update(outcome="cancelled", ended_at=datetime.now(UTC).isoformat())
                    observation["emit"]()

            future.add_done_callback(lambda completed, context=callback_context, callback=cancelled: context.run(callback, completed))
        for future in as_completed(futures):
            answers[futures[future]] = future.result()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return answers
