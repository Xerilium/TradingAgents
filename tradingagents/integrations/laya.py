"""App-owned, bounded local Laya batches. Predictions never authorize trading."""

from collections import deque
from importlib.metadata import version
import os
from pathlib import Path
import re
import threading
import time

MODEL = "convaiinnovations/laya-multilingual"
REVISION = "1720e3e3357cfe1e281542e223f8273b0890ca34"
MAX_TOKENS, HEAD_TOKENS, BATCH_SIZE = 8192, 512, 5


def local_failure_details(error):
    """Bound local classifier diagnostics and remove remote credential material."""
    details, seen = [], set()
    while error is not None and id(error) not in seen and len(details) < 4:
        seen.add(id(error))
        message = str(error)
        message = re.sub(r"(?i)https?://\S+", "[URL redacted]", message)
        message = re.sub(r"([?&][^=\s&]+)=[^&\s]+", r"\1=[redacted]", message)
        message = re.sub(r'''(?im)\b(?:authorization|api[_ -]?key|token|password|secret|cookie)\b["'\s]*[:=][^\r\n]*''',
                         "[credential redacted]", message)
        message = re.sub(r"(?i)\bbearer\s+\S+|\bhf_[A-Za-z0-9_-]+|\bsk-[A-Za-z0-9_-]+",
                         "[credential redacted]", message)
        detail = {"class": type(error).__name__[:80], "message": message[:400]}
        status = getattr(getattr(error, "response", None), "status_code", None)
        if type(status) is int:
            detail["http_status"] = status
        details.append(detail)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return details


class LocalLaya:
    def __init__(self):
        root = Path(__file__).resolve().parents[2]
        cache = Path(os.getenv("TRADINGAGENTS_LAYA_CACHE", ".cache/laya"))
        self.cache = (root / cache).resolve()
        self.device = os.getenv("TRADINGAGENTS_LAYA_DEVICE", "cpu")
        self.lane = threading.Condition(), deque()
        self.ready, self.closed = threading.Event(), threading.Event()
        self.router = None
        self.details = {"status": "loading", "model": MODEL, "revision": REVISION,
                        "device": self.device, "cache": str(self.cache), "batch_size": BATCH_SIZE}
        self.loader = threading.Thread(target=self._load, name="local-laya-load", daemon=True)
        self.loader.start()

    def _load(self):
        router = None
        try:
            if version("laya") != "0.4.14":
                raise RuntimeError("Install the pinned Laya dependencies from pyproject.toml")
            from huggingface_hub import snapshot_download
            from laya import Router
            snapshot = snapshot_download(MODEL, revision=REVISION, cache_dir=str(self.cache),
                allow_patterns=["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"])
            router = Router(models={"multilingual": snapshot}, device=self.device,
                            max_loaded=1, agent_kwargs={"backend": "eager"})
            agent = router.load("multilingual")
            with self.lane[0]:
                if self.closed.is_set():
                    router.unload()
                    return
                self.router = router
                self.details = {**self.details, "status": "ready", "package": version("laya"),
                                "device": str(agent.device)}
        except Exception as exc:
            if router:
                router.unload()
            details = local_failure_details(exc)
            self.details = {**self.details, "status": "failed", "error_details": details,
                            "error": "; ".join(f"{d['class']}: {d['message']}" for d in details)[:500]}
        finally:
            self.ready.set()

    def state(self):
        return dict(self.details)

    def close(self):
        self.closed.set()
        threading.Thread(target=self._release, name="local-laya-close", daemon=True).start()

    def _release(self):
        # A batch already on the device settles before eviction; queued work stops.
        with self.lane[0]:
            while self.lane[1]:
                self.lane[0].wait(.25)
            if self.router:
                self.router.unload()
                self.router = None
            self.details = {**self.details, "status": "stopped"}

    def predict_batch(self, posts, questions, *, cancelled, deadline, on_dispatch):
        while not self.ready.wait(.25):
            self._check(cancelled, deadline)
        self._check(cancelled, deadline)
        if self.details["status"] != "ready":
            raise RuntimeError("Local Laya unavailable: " + self.details.get("error", self.details["status"]))
        if not 0 < len(posts) <= BATCH_SIZE:
            raise ValueError("Local Laya requires one bounded batch of original posts")
        from laya.common import build_sequence, encode_text, render_options
        agent = self.router.load("multilingual")
        schema = {key: {"type": "noul" if q["kind"] == "yes_no" else q["kind"],
                        "instructions": q["instructions"], "criteria": q["criteria"]}
                  for key, q in questions.items()}
        internal = {key: {"t": q["type"], "ins": q["instructions"], "crit": q["criteria"]}
                    for key, q in schema.items()}
        measured = []
        for post in posts:
            counts, complete = {}, True
            for key, q in internal.items():
                tokens = lambda text: encode_text(agent.tok, text.replace(agent.tok.mask_token, " "),
                                                  add_special_tokens=False)["input_ids"]
                options = [tokens(" " + option) for option in render_options(q)]
                head = len(tokens(f"{q['t']} question: {q['ins']}")) + sum(len(o) + 1 for o in options)
                complete &= head <= HEAD_TOKENS and all(len(o) <= 48 for o in options)
                ids, _, stats = build_sequence(agent.tok, post, q, MAX_TOKENS, HEAD_TOKENS,
                                                return_truncation_stats=True)
                counts[key] = len(ids)
                complete &= stats["truncated"] is False
            measured.append((counts, complete))
        self._check(cancelled, deadline)
        on_dispatch()
        raw = self.router.predict_batch([
            {"state": post, "questions": schema, "model": "multilingual",
             "max_len": MAX_TOKENS, "head_max_len": HEAD_TOKENS} for post in posts], batch_size=BATCH_SIZE)
        if len(raw) != len(posts):
            raise ValueError("Local Laya returned a different post count")
        results = []
        for result, (counts, complete) in zip(raw, measured, strict=True):
            usage, answers = result.get("usage", {}), result.get("answers", {})
            full = (complete and usage.get("input_tokens") == sum(counts.values()) and usage.get("truncated") is False
                    and usage.get("state_tokens_dropped") == 0 and not usage.get("options"))
            about, stance = answers.get("about", {}), answers.get("stance", {})
            if about.get("type") != "noul" or stance.get("type") != "choice":
                raise ValueError("Local Laya returned invalid social answer types")
            probability = about["noul"]
            # The Python API has no contract grade. Preserve that absence as uncertainty.
            results.append({"raw_result": result, "model_identity": self.state(),
                "answers": {"about": {**about, "kind": "yes_no",
                    "probabilities": {"true": probability, "false": 1 - probability}},
                    "stance": {**stance, "kind": "choice", "value": stance["choice"]}},
                "usage": {**usage, "context_budget": {"model": "multilingual",
                    "effective_max_tokens": MAX_TOKENS, "sequence_tokens": counts,
                    "questions_complete": full, "state_complete": full}}})
        return results

    def _check(self, cancelled, deadline):
        if self.closed.is_set() or cancelled():
            raise InterruptedError("Local Laya screening stopped")
        if time.monotonic() >= deadline:
            error = TimeoutError("Local Laya screening processing budget expired before inference")
            error.social_budget_expired = True
            raise error
