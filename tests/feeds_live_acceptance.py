"""One real-feed sentiment node, no graph/broker/journal writes.

Run only with the outer run-bounded.py --seconds 300 helper. This module does
not run on import. Existing receipt prevents replay. Not whole-goal acceptance.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def receipt_default(value):
    """Preserve SDK models and raw response bytes without stringifying evidence."""
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode(),
                "sha256": hashlib.sha256(value).hexdigest()}
    if callable(getattr(value, "model_dump", None)):
        return value.model_dump(mode="python", by_alias=True)
    raise TypeError(f"Unsupported receipt value: {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", choices=("META",), default="META")
    parser.add_argument("--series", default="", help="Unique retry receipt suffix; existing receipts are never overwritten")
    args = parser.parse_args()
    if args.series and not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.series):
        parser.error("series must contain 1-40 letters, digits, underscores or hyphens")
    journal = ROOT / ".paper-desk" / "desk.json"
    journal_bytes = journal.read_bytes()
    config = json.loads(journal_bytes)["config"]
    if config["llm_provider"] != "chatgpt":
        raise RuntimeError("Configured provider changed; this acceptance only uses the configured ChatGPT path")
    date = datetime.now().astimezone().date().isoformat()
    suffix = f"-{args.series}" if args.series else ""
    path = ROOT / ".paper-desk" / f"feeds-live-{args.ticker}-{date}{suffix}.json"
    receipt = {"status": "prepared", "ticker": args.ticker, "trade_date": date,
               "provider": config["llm_provider"], "model": config["quick_think_llm"],
               "journal_sha256_before": hashlib.sha256(journal_bytes).hexdigest(),
               "stages": [], "sources": {}, "social": {}, "gateway_calls": [],
               "vendor_observations": [], "model_calls": [], "broker_calls": 0}
    with path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    started = time.monotonic()

    def save():
        path.write_text(json.dumps(receipt, indent=2, default=receipt_default), encoding="utf-8")

    def stage(name):
        receipt["stages"].append({"name": name, "elapsed_seconds": time.monotonic() - started})
        save()

    try:
        from langchain_core.callbacks import BaseCallbackHandler
        from tradingagents.agents.analysts import sentiment_analyst as module
        from tradingagents.agents.post_screen import laya_screen
        from tradingagents.dataflows.config import run_config
        from tradingagents.dataflows.router import capture_vendor_evidence
        from tradingagents.default_config import build_default_config
        from tradingagents.integrations.maenifold import MaenifoldGateway
        from tradingagents.llm_clients.factory import create_tier_client

        class CaptureModel(BaseCallbackHandler):
            raise_error = True

            def on_chat_model_start(self, serialized, messages, **kwargs):
                receipt["model_calls"].append({"run_id": str(kwargs.get("run_id")),
                    "messages": [[{"type": msg.type, "content": msg.content} for msg in batch]
                                 for batch in messages], "status": "started"})
                stage("analyst_model_started")

            def on_llm_end(self, response, **kwargs):
                for row in receipt["model_calls"]:
                    if row["run_id"] == str(kwargs.get("run_id")):
                        row["status"] = "completed"
                save()

            def on_llm_error(self, error, **kwargs):
                for row in receipt["model_calls"]:
                    if row["run_id"] == str(kwargs.get("run_id")):
                        row.update(status="failed", error=str(error)[:500])
                save()

        class OnlyLaya:
            def __init__(self):
                self.inner = MaenifoldGateway(timeout=60)
                stage("laya_discovery_started")
                self.inner.discover("laya")
                stage("laya_discovery_completed")

            async def aexecute(self, domain, command, parameters, *, on_dispatch=None):
                if domain != "laya" or command not in {"count_context", "decide"}:
                    raise RuntimeError("Acceptance blocks all non-classification Gateway commands")
                call = {"command": command, "parameters": parameters, "status": "prepared", "dispatches": 0}
                receipt["gateway_calls"].append(call)
                save()

                def dispatched():
                    if on_dispatch:
                        on_dispatch()
                    call["dispatches"] += 1
                    call["status"] = "dispatched"
                    save()
                try:
                    result = await self.inner.aexecute(domain, command, parameters, on_dispatch=dispatched)
                    call.update(status="completed", result=result)
                    save()
                    return result
                except Exception as exc:
                    call.update(status="failed_or_unknown", error=f"{type(exc).__name__}: {exc}")
                    save()
                    raise

        gateway = OnlyLaya()
        budget = {"remaining": 1, "deadline": None}

        def screen_factory(ticker, source, *, instrument_context=""):
            def capture(evidence):
                receipt["social"][source] = evidence
                save()
            return laya_screen(ticker, gateway, max_posts=1, budget=budget,
                               instrument="Meta Platforms (META)", source=source, on_evidence=capture)

        def observed_feed(name, original):
            def fetch(*positional, **keywords):
                stage(f"{name}_started")
                try:
                    result = original(*positional, **keywords)
                    receipt["sources"][name] = result
                    stage(f"{name}_completed")
                    return result
                except Exception as exc:
                    receipt["sources"][name] = {"error": f"{type(exc).__name__}: {exc}"}
                    stage(f"{name}_failed")
                    raise
            return fetch

        def record_vendor(observation, payload):
            receipt["vendor_observations"].append({"observation": observation, "payload": payload})
            save()

        settings = build_default_config()
        settings.update(config)
        settings["quick_think_provider"] = config["llm_provider"]
        settings["quick_think_backend_url"] = config.get("backend_url")
        llm = create_tier_client(settings, "quick", timeout=90, callbacks=[CaptureModel()]).get_llm()
        state = {"company_of_interest": args.ticker, "trade_date": date, "messages": [],
                 "instrument_context": "Instrument: META. Company: Meta Platforms. Asset type: stock."}
        with run_config(settings), capture_vendor_evidence(record_vendor), \
             patch.object(module, "get_news", SimpleNamespace(func=observed_feed("news", module.get_news.func))), \
             patch.object(module, "fetch_stocktwits_messages", observed_feed("stocktwits", module.fetch_stocktwits_messages)), \
             patch.object(module, "fetch_reddit_posts", observed_feed("reddit", module.fetch_reddit_posts)):
            stage("sentiment_node_started")
            output = module.create_sentiment_analyst(llm, screen_factory=screen_factory)(state)
        receipt["report"] = output["sentiment_report"]
        verified = []
        for evidence in receipt["social"].values():
            for row in evidence.get("posts", []):
                if row.get("result"):
                    actual = row["result"].get("usage", {}).get("context_budget", {})
                    expected = row.get("token_budget", {})
                    verified.append(all(actual.get(key) == expected.get(key) and key in actual
                                        for key in ("sequence_sha256", "sequence_tokens")))
        receipt["actual_post_input_verified"] = bool(verified) and all(verified)
        receipt["status"] = "completed_sentiment_only"
        stage("sentiment_node_completed")
    except Exception as exc:
        receipt.update(status="failed_or_unknown", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["journal_sha256_after"] = hashlib.sha256(journal.read_bytes()).hexdigest()
        receipt["journal_unchanged"] = receipt["journal_sha256_before"] == receipt["journal_sha256_after"]
        save()
    print(json.dumps({key: receipt.get(key) for key in
                     ("status", "actual_post_input_verified", "journal_unchanged", "broker_calls", "elapsed_seconds")}))


if __name__ == "__main__":
    main()
