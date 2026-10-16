"""Read-only replay of three saved responses; no inference or broker calls.

Run: python -m tests.social_stance_replay_browser_fixture --port 18767
Use --check to verify the replay without starting a server.
"""
import argparse
import copy
import hashlib
from http.server import HTTPServer
import json
from pathlib import Path
import socket

from tests import ui_gate_browser_fixture as fixture
from tradingagents.agents.post_screen import laya_screen

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "56938b20-afd1-4696-9a0a-a13d48e460d0"
HASHES = (
    "97c6ed28c2edffb93f435e3a3caefc375072ce603768e684aa27415bec0201d4",
    "f22a83b41b57fffa077c3f313234bd801aa03c844003ef2636abd8d5573658b4",
    "f021d40f3ef67aa7423e4e882956eab35888ce665dfd2e0fb28efc9c1117898b",
)


def replay():
    path = ROOT / ".paper-desk/desk.json"
    original_bytes = path.read_bytes()
    document = json.loads(original_bytes)
    run = next(item for item in document["runs"] if item["id"] == RUN_ID)
    result = next(item for item in run["results"] if item["symbol"] == "META")
    by_hash = {row["text_sha256"]: row for row in result["social_sentiment"]["sources"]["stocktwits"]["posts"]}
    rows = [copy.deepcopy(by_hash[key]) for key in HASHES]
    for key, row in zip(HASHES, rows, strict=True):
        assert hashlib.sha256(row["text"].encode()).hexdigest() == key

    class ReplayGateway:
        index = 0
        calls = []

        def execute(self, domain, command, parameters, *, on_dispatch=None):
            assert domain == "laya" and command in {"count_context", "decide"}
            assert parameters["state"]["post"] == rows[self.index]["text"]
            if on_dispatch:
                on_dispatch()
            self.calls.append(command)
            row = rows[self.index]
            if command == "count_context":
                return copy.deepcopy(row["token_budget"])
            self.index += 1
            return copy.deepcopy(row["result"])

    gateway = ReplayGateway()
    callback = laya_screen("META", gateway, max_posts=3, source="stocktwits",
                           instrument="Meta Platforms, Inc. (META)")
    keep, _ = callback([row["text"] for row in rows])
    evidence = callback.evidence
    assert keep == [True, True, True]
    assert evidence["counts"]["unclear"] == 3
    assert gateway.calls == ["count_context", "decide"] * 3
    for original, updated in zip(rows, evidence["posts"], strict=True):
        assert updated["result"] == original["result"]
        assert updated["stance"] == "unclear"
        assert updated["raw_prediction"] == original["result"]["answers"]["stance"]["value"]
        updated["provenance"] = "Offline replay of saved StockTwits message; no new inference."
    evidence["note"] = "OFFLINE REPLAY VERIFICATION — saved responses reinterpreted by corrected code, not new inference. " + evidence["note"]
    evidence["replay_source_run"] = RUN_ID
    evidence["replayed_text_hashes"] = list(HASHES)
    assert path.read_bytes() == original_bytes, "Journal changed during read-only replay; retry once idle."
    return {"status": "completed", "model": "multilingual", "sources": {"stocktwits": evidence}}


def configure(social):
    seed = """
fixtureState.config.name='OFFLINE STANCE REPLAY';
fixtureState.config.universe=['META'];
fixtureState.proposals=[];
fixtureState.runs[0].symbols=['META'];
fixtureState.runs[0].counts={completed:1};
fixtureState.runs[0].results=[{symbol:'META',status:'completed',reports:{},social_sentiment:SOCIAL}];
fixtureState.runs[0].events=[{stage:'offline replay',message:'Saved responses replayed through corrected admission logic. No new inference, research or orders.'}];
fixtureState.research={META:{status:'completed',social_sentiment:SOCIAL}};
""".replace("SOCIAL", json.dumps(social, ensure_ascii=True).replace("<", "\\u003c"))
    fixture.BOOT = fixture.BOOT.replace("window.fetch=async", seed + "\nwindow.fetch=async")
    # Remove unrelated synthetic control buttons from the base fixture.
    fixture.BOOT = fixture.BOOT.split("document.addEventListener('DOMContentLoaded'")[0] + "</script>"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18767)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    social = replay()
    if args.check:
        print(json.dumps({"mode": "offline replay, no new inference", "source_run": RUN_ID,
                          "counts": social["sources"]["stocktwits"]["counts"], "hashes": HASHES}))
    else:
        configure(social)
        server = HTTPServer(("127.0.0.1", args.port), fixture.Handler, bind_and_activate=False)
        server.allow_reuse_address = False
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        server.server_bind()
        server.server_activate()
        server.serve_forever()
