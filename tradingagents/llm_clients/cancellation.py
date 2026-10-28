"""Interruptible, per-research bridge from synchronous graph nodes to async models."""

import asyncio
import concurrent.futures
import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from .base_client import normalize_content

logger = logging.getLogger(__name__)


class ResearchCancellationController:
    """Own one event loop and the model transports for a single research run."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cancelled = False
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="research-model-loop", daemon=True)
        self._futures = set()
        self._clients = []
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        self._loop.close()

    def wrap(self, model):
        if isinstance(model, BaseChatModel) and type(model)._agenerate is BaseChatModel._agenerate:
            raise RuntimeError("This model does not support interruptible async requests.")
        with self._lock:
            if self._cancelled or self._closed:
                raise InterruptedError("Research cancelled")
            self._clients.append(model)
        return _InterruptibleRunnable(model, self)

    def invoke(self, runnable, input, config=None, **kwargs):
        async def call():
            return await runnable.ainvoke(input, config=config, **kwargs)

        with self._lock:
            if self._cancelled or self._closed:
                raise InterruptedError("Research cancelled")
            future = asyncio.run_coroutine_threadsafe(call(), self._loop)
            self._futures.add(future)
        try:
            result = future.result()
            with self._lock:
                if self._cancelled:
                    raise InterruptedError("Research cancelled")
            return normalize_content(result) if hasattr(result, "content") else result
        except concurrent.futures.CancelledError:
            raise InterruptedError("Research cancelled") from None
        finally:
            with self._lock:
                self._futures.discard(future)

    def cancel(self):
        with self._lock:
            self._cancelled = True
            futures = tuple(self._futures)
        for future in futures:
            future.cancel()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            futures = tuple(self._futures)
        for future in futures:
            future.cancel()

        async def cleanup():
            current = asyncio.current_task()
            tasks = [task for task in asyncio.all_tasks() if task is not current]
            if tasks:
                # Futures above already requested cancellation. A second cancel can
                # interrupt provider cleanup (notably the Codex helper shutdown).
                _, pending = await asyncio.wait(tasks, timeout=30)
                if pending:
                    logger.warning("Research model tasks did not finish cleanup within 30 seconds")
            seen = set()
            for model in self._clients:
                # Google owns both transports and provides loop-aware cleanup.
                if getattr(model, "_client_cleanup", None) is not None:
                    try:
                        await asyncio.wait_for(model.aclose(), timeout=5)
                    except Exception:
                        logger.warning("Could not close research model client", exc_info=True)
                # Anthropic caches clients lazily; inspect the instance dictionary
                # so closing an unused model does not create a new transport.
                cached = getattr(model, "__dict__", {})
                clients = (
                    (getattr(model, "root_async_client", None), True),
                    (getattr(model, "root_client", None), False),
                    (cached.get("_async_client"), True),
                    (cached.get("_client"), False),
                )
                for client, is_async in clients:
                    if client is None or id(client) in seen:
                        continue
                    seen.add(id(client))
                    try:
                        if is_async:
                            await asyncio.wait_for(client.close(), timeout=5)
                        else:
                            client.close()
                    except Exception:
                        logger.warning("Could not close research model client", exc_info=True)

        try:
            asyncio.run_coroutine_threadsafe(cleanup(), self._loop).result(timeout=35 + 15 * len(self._clients))
        except Exception:
            logger.warning("Could not finish research model cleanup", exc_info=True)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("Research model loop did not stop within 5 seconds")



class _InterruptibleRunnable(Runnable):
    def __init__(self, runnable, controller):
        self._runnable = runnable
        self._controller = controller

    def invoke(self, input, config=None, **kwargs):
        return self._controller.invoke(self._runnable, input, config, **kwargs)

    def bind_tools(self, *args, **kwargs):
        return _InterruptibleRunnable(self._runnable.bind_tools(*args, **kwargs), self._controller)

    def with_structured_output(self, *args, **kwargs):
        return _InterruptibleRunnable(self._runnable.with_structured_output(*args, **kwargs), self._controller)

    def __getattr__(self, name):
        return getattr(self._runnable, name)
