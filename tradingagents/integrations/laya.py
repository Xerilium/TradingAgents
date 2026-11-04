"""App-owned, bounded local Laya batches. Predictions never authorize trading."""

from collections import deque
from importlib.metadata import version
import os
import hashlib
import json
import logging
import atexit
import multiprocessing
import uuid
from pathlib import Path
import re
import sys
import threading
import time

MODEL = "convaiinnovations/laya-multilingual"
REVISION = "1720e3e3357cfe1e281542e223f8273b0890ca34"
MAX_TOKENS, HEAD_TOKENS, BATCH_SIZE = 8192, 512, 5
logger = logging.getLogger(__name__)


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


class _LocalLayaRuntime:
    def __init__(self, cache_root=None, device="cpu"):
        if device not in {"cpu", "gpu"}:
            raise ValueError("Laya device must be cpu or gpu")
        root = Path(cache_root) if cache_root is not None else Path(__file__).resolve().parents[2]
        cache = Path(os.getenv("TRADINGAGENTS_LAYA_CACHE", ".cache/laya"))
        self.cache = (root / cache).resolve()
        self.requested_device = device
        self.lane = threading.Condition(), deque()
        self.ready, self.closed = threading.Event(), threading.Event()
        self.router = None
        self._close_lock = threading.Lock()
        self._closer = None
        self._close_error = None
        self.details = {"status": "loading", "model": MODEL, "revision": REVISION,
                        "requested_device": device, "device": None, "actual_device": None,
                        "fallback_reason": None, "cpu_fallback_count": 0,
                        "cpu_fallback_observed": False, "cache": str(self.cache), "batch_size": BATCH_SIZE}
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
            selected, fallback = self._resolve_device()
            router = Router(models={"multilingual": snapshot}, device=selected,
                            max_loaded=1, agent_kwargs={"backend": "eager"})
            try:
                agent = router.load("multilingual")
            except Exception as load_error:
                if selected == "cpu":
                    raise
                try:
                    router.unload()
                except Exception as cleanup_error:
                    # Keep the original load failure and let the outer cleanup
                    # retain ownership if the router still cannot be unloaded.
                    raise load_error from cleanup_error
                fallback = "Laya could not load the model on the accelerator; using CPU."
                router = Router(models={"multilingual": snapshot}, device="cpu",
                                max_loaded=1, agent_kwargs={"backend": "eager"})
                agent = router.load("multilingual")
            with self.lane[0]:
                self.router = router
                if self.closed.is_set():
                    return
                actual = str(agent.device)
                if self.requested_device == "gpu" and actual == "cpu" and fallback is None:
                    fallback = "Laya could not load the model on the accelerator and fell back to CPU."
                self.details = {**self.details, "status": "ready", "package": version("laya"),
                                "device": actual, "actual_device": actual, "fallback_reason": fallback}
        except Exception as exc:
            details = local_failure_details(exc)
            cleanup_details = []
            if router:
                try:
                    router.unload()
                except Exception as cleanup_error:
                    cleanup_details = local_failure_details(cleanup_error)
                    # close(wait=True) will retry this owned router and report
                    # failure rather than allowing an overlapping replacement.
                    with self.lane[0]:
                        self.router = router
            with self.lane[0]:
                self.details = {**self.details, "status": "failed", "error_details": details,
                                "cleanup_error_details": cleanup_details,
                                "error": "; ".join(f"{d['class']}: {d['message']}" for d in details)[:500]}
        finally:
            self.ready.set()

    def _resolve_device(self):
        if self.requested_device == "cpu":
            return "cpu", None
        try:
            import torch
            if sys.platform == "darwin":
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return "mps", None
                return "cpu", "Apple MPS is unavailable; using CPU."
            if torch.cuda.is_available():
                return "cuda", None
            return "cpu", "CUDA is unavailable in the installed PyTorch runtime; using CPU."
        except Exception:
            return "cpu", "Accelerator availability could not be checked; using CPU."

    def state(self):
        with self.lane[0]:
            return dict(self.details)

    def close(self, *, wait=False):
        with self._close_lock:
            self.closed.set()
            if self._closer is None:
                self._closer = threading.Thread(target=self._release, name="local-laya-close", daemon=True)
                self._closer.start()
            closer = self._closer
        if wait:
            closer.join()
            if self._close_error is not None:
                raise RuntimeError("Could not unload the previous Laya model.") from self._close_error

    def _release(self):
        # Wait for any in-flight load before releasing the sole model.
        self.loader.join()
        # A batch already on the device settles before eviction; queued work stops.
        with self.lane[0]:
            while self.lane[1]:
                self.lane[0].wait(.25)
            try:
                if self.router:
                    self.router.unload()
                    self.router = None
                self.details = {**self.details, "status": "stopped", "device": None, "actual_device": None}
            except Exception as exc:
                self._close_error = exc
                self.details = {**self.details, "status": "failed", "error": "Could not unload the Laya model."}

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
        before_fallbacks = getattr(agent, "cpu_fallback_count", 0)
        batch_id, started, raw = uuid.uuid4().hex, time.monotonic(), None
        question_hash = hashlib.sha256(json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        try:
            raw = self.router.predict_batch([
                {"state": post, "questions": schema, "model": "multilingual",
                 "max_len": MAX_TOKENS, "head_max_len": HEAD_TOKENS} for post in posts], batch_size=BATCH_SIZE)
        finally:
            elapsed = round(time.monotonic() - started, 3)
            logger.info("Laya inference batch=%s posts=%s device=%s elapsed_seconds=%s outcome=%s",
                        batch_id, len(posts), agent.device, elapsed, "returned" if raw is not None else "error")
            after_fallbacks = getattr(agent, "cpu_fallback_count", 0)
            actual = str(agent.device)
            observed = after_fallbacks > before_fallbacks
            with self.lane[0]:
                reason = self.details.get("fallback_reason")
                if observed:
                    reason = "Laya used a CPU fallback after an accelerator memory error."
                elif self.requested_device == "gpu" and actual == "cpu" and reason is None:
                    reason = "Laya is using CPU after an accelerator fallback."
                self.details = {**self.details, "device": actual, "actual_device": actual,
                                "cpu_fallback_count": after_fallbacks,
                                "cpu_fallback_observed": observed, "fallback_reason": reason}
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
            # The pinned SDK returns probabilities, not Gateway authority grades.
            results.append({"raw_result": result, "model_identity": self.state(),
                "inference": {"batch_id": batch_id, "batch_size": len(posts), "elapsed_seconds": elapsed,
                              "api": "Router.predict_batch", "questions": schema, "questions_sha256": question_hash,
                              "rendered_choices": {key: render_options(q) for key, q in internal.items()}},
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


def _laya_worker(connection, cache_root, device):
    """Own every Laya and PyTorch object in a disposable process."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    runtime = _LocalLayaRuntime(cache_root, device)
    send_lock = threading.Lock()
    stopping = threading.Event()

    def send(message):
        with send_lock:
            connection.send(message)

    def publish_state():
        previous = None
        while not stopping.wait(.2):
            state = runtime.state()
            if state != previous:
                try:
                    send(("state", state))
                except (EOFError, OSError, BrokenPipeError):
                    return
                previous = state

    threading.Thread(target=publish_state, daemon=True).start()
    try:
        while True:
            message = connection.recv()
            if message[0] == "close":
                break
            if message[0] != "predict":
                continue
            _, job, posts, questions, deadline = message

            def dispatch():
                send(("dispatch", job))
                reply = connection.recv()
                if reply != ("accept", job):
                    raise InterruptedError("Local Laya screening stopped")

            try:
                result = runtime.predict_batch(posts, questions, cancelled=lambda: False,
                                               deadline=deadline, on_dispatch=dispatch)
                send(("result", job, result, runtime.state()))
            except Exception as exc:
                send(("error", job, type(exc).__name__, str(exc),
                      bool(getattr(exc, "social_budget_expired", False)), runtime.state()))
    except (EOFError, OSError, BrokenPipeError):
        pass
    finally:
        stopping.set()
        # Process exit releases the CUDA context even if unloading fails.
        connection.close()


class LocalLaya:
    """Parent-side proxy for an app-owned, disposable Laya runtime."""

    def __init__(self, cache_root=None, device="cpu"):
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        if device not in {"cpu", "gpu"}:
            raise ValueError("Laya device must be cpu or gpu")
        self.requested_device = device
        root = Path(cache_root) if cache_root is not None else Path(__file__).resolve().parents[2]
        cache = Path(os.getenv("TRADINGAGENTS_LAYA_CACHE", ".cache/laya"))
        self.details = {"status": "loading", "model": MODEL, "revision": REVISION,
                        "requested_device": device, "device": None, "actual_device": None,
                        "fallback_reason": None, "cpu_fallback_count": 0,
                        "cpu_fallback_observed": False, "cache": str((root / cache).resolve()),
                        "batch_size": BATCH_SIZE}
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._batch_lock = threading.Lock()
        self._closed = False
        self._jobs = {}
        self._root = root
        self._start_worker()
        atexit.register(self.close, wait=True)

    def _start_worker(self):
        context = multiprocessing.get_context("spawn")
        if sys.platform == "win32":
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            if not pythonw.is_file():
                raise RuntimeError("Laya requires pythonw.exe alongside the desktop Python runtime.")
            context.set_executable(str(pythonw))
        self._connection, child = context.Pipe()
        self._process = context.Process(target=_laya_worker, args=(child, str(self._root), self.requested_device),
                                        name="local-laya-runtime", daemon=True)
        try:
            self._process.start()
            self.details["pid"] = self._process.pid
        except Exception:
            self._connection.close()
            child.close()
            raise
        child.close()
        self._receiver = threading.Thread(target=self._receive, args=(self._connection, self._process), name="local-laya-receiver", daemon=True)
        self._receiver.start()

    def _send(self, message):
        with self._send_lock:
            self._connection.send(message)

    def _receive(self, connection, process):
        try:
            while True:
                message = connection.recv()
                kind = message[0]
                if kind == "state":
                    with self._lock:
                        self.details = {**message[1], "pid": process.pid} if not self._closed and self._process is process else self.details
                elif kind == "dispatch":
                    with self._lock:
                        job = self._jobs.get(message[1])
                    accepted = False
                    if job is not None:
                        try:
                            if job.get("abandoned"):
                                raise InterruptedError("Local Laya screening stopped")
                            self._check(job["cancelled"], job["deadline"])
                            job["on_dispatch"]()
                            job["dispatched"] = True
                            accepted = True
                        except Exception as exc:
                            job["exception"] = exc
                    with self._send_lock:
                        connection.send(("accept" if accepted else "reject", message[1]))
                elif kind in {"result", "error"}:
                    with self._lock:
                        self.details = {**message[-1], "pid": process.pid} if not self._closed and self._process is process else self.details
                        job = self._jobs.get(message[1])
                    if job is not None:
                        job["message"] = message
                        job["event"].set()
        except (EOFError, OSError, BrokenPipeError):
            pass
        finally:
            with self._lock:
                if self._process is not process:
                    return
                if not self._closed:
                    self.details = {**self.details, "status": "failed", "device": None,
                                    "actual_device": None, "error": "Local Laya process exited unexpectedly."}
                for job in self._jobs.values():
                    job["event"].set()

    def _interrupt_worker(self, job_id):
        """Interrupt owned device inference; a fresh worker handles later requests."""
        process, connection, receiver = self._process, self._connection, self._receiver
        logger.warning("Laya inference interrupted batch=%s pid=%s", job_id, process.pid)
        if process.is_alive():
            process.terminate()
        process.join(5)
        if process.is_alive():
            raise RuntimeError("Could not interrupt the owned Laya process.")
        connection.close()
        receiver.join(1)
        with self._lock:
            if not self._closed:
                self.details = {k: v for k, v in self.details.items() if k not in {"error", "error_details", "cleanup_error_details"}}
                self.details = {**self.details, "status": "loading", "device": None,
                                "actual_device": None, "fallback_reason": None}
                self._start_worker()

    def state(self):
        with self._lock:
            return dict(self.details)

    def _check(self, cancelled, deadline):
        if self._closed or cancelled():
            raise InterruptedError("Local Laya screening stopped")
        if time.monotonic() >= deadline:
            error = TimeoutError("Local Laya screening processing budget expired before inference")
            error.social_budget_expired = True
            raise error

    def predict_batch(self, posts, questions, *, cancelled, deadline, on_dispatch):
        if not 0 < len(posts) <= BATCH_SIZE:
            raise ValueError("Local Laya requires one bounded batch of original posts")
        while not self._batch_lock.acquire(timeout=.25):
            self._check(cancelled, deadline)
        job_id = uuid.uuid4().hex
        job = {"event": threading.Event(), "cancelled": cancelled, "deadline": deadline,
               "on_dispatch": on_dispatch}
        try:
            self._check(cancelled, deadline)
            with self._lock:
                self._jobs[job_id] = job
            try:
                self._send(("predict", job_id, posts, questions, deadline))
            except (OSError, EOFError, BrokenPipeError) as exc:
                raise RuntimeError("Local Laya process is unavailable.") from exc
            while not job["event"].wait(.05):
                try:
                    self._check(cancelled, deadline)
                except (InterruptedError, TimeoutError):
                    with self._lock:
                        job["abandoned"] = True
                    self._interrupt_worker(job_id)
                    raise
            self._check(cancelled, deadline)
            if "exception" in job:
                raise job["exception"]
            message = job.get("message")
            if message is None:
                raise RuntimeError("Local Laya process exited unexpectedly.")
            if message[0] == "error":
                if message[2] == "InterruptedError":
                    raise InterruptedError(message[3])
                if message[2] == "TimeoutError":
                    error = TimeoutError(message[3])
                    error.social_budget_expired = message[4]
                    raise error
                raise RuntimeError("Local Laya unavailable: " + message[3])
            for result in message[2]:
                result["inference"]["request_id"] = job_id
            metadata = message[2][0]["inference"]
            logger.info("Laya batch=%s request=%s posts=%s device=%s elapsed_seconds=%s questions=%s",
                        metadata["batch_id"], job_id, len(posts), message[-1].get("actual_device"),
                        metadata["elapsed_seconds"], metadata["questions_sha256"])
            return message[2]
        finally:
            def release_job():
                with self._lock:
                    self._jobs.pop(job_id, None)
                self._batch_lock.release()
            if job["event"].is_set() or job_id not in self._jobs:
                release_job()
            else:
                job["abandoned"] = True
                def finish_abandoned():
                    job["event"].wait()
                    release_job()
                threading.Thread(target=finish_abandoned, daemon=True).start()

    def close(self, *, wait=False):
        with self._lock:
            first = not self._closed
            self._closed = True
            self.details = {**self.details, "status": "stopped", "device": None, "actual_device": None}
            for job in self._jobs.values():
                job["event"].set()
        if first:
            try:
                self._send(("close",))
            except (OSError, EOFError, BrokenPipeError):
                pass
        if wait:
            self._process.join(10)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(10)
            if self._process.is_alive():
                raise RuntimeError("Could not stop the previous Laya process.")
            self._connection.close()
            atexit.unregister(self.close)
