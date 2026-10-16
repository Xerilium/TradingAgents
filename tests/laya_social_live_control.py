"""One bounded real social classification; no broker commands or journal writes.

Run one case under run-bounded.py --seconds 80. Existing receipts prevent replay.
"""
import argparse
import json
from pathlib import Path

from tradingagents.agents.post_screen import laya_screen
from tradingagents.integrations.maenifold import MaenifoldGateway

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "bullish": ("I am buying META because I expect its stock price to rise.", "bullish"),
    "bearish": ("I am selling META because I expect its stock price to fall.", "bearish"),
    "neutral": ("What time does Meta Platforms report earnings?", "neutral"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--series", default="")
    args = parser.parse_args()
    post, expected = CASES[args.case]
    if args.series and not args.series.replace('-', '').isalnum():
        raise ValueError("Series must be alphanumeric with optional hyphens")
    suffix = f"-{args.series}" if args.series else ""
    path = ROOT / ".paper-desk" / f"laya-social-{args.case}{suffix}.json"
    receipt = {"case": args.case, "post": post, "expected": expected, "calls": [], "status": "prepared"}
    with path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)

    def save():
        path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    class OnlyLaya:
        def __init__(self):
            self.inner = MaenifoldGateway(timeout=60)
            self.inner.discover("laya")

        async def aexecute(self, domain, command, parameters, *, on_dispatch=None):
            assert domain == "laya" and command in {"count_context", "decide"}
            call = {"command": command, "parameters": parameters}
            receipt["calls"].append(call)
            save()
            result = await self.inner.aexecute(domain, command, parameters, on_dispatch=on_dispatch)
            call["result"] = result
            save()
            return result

    try:
        screen = laya_screen("META", OnlyLaya(), max_posts=1, source="synthetic_control",
                             instrument="Meta Platforms (META)")
        receipt["keep"], receipt["note"] = screen([post])
        receipt["evidence"] = screen.evidence
        row = screen.evidence["posts"][0]
        receipt["semantics_match"] = row.get("stance") == expected and row["status"] == "classified"
        if row.get("result"):
            actual = row["result"]["usage"]["context_budget"]
            receipt["input_verified"] = all(actual[key] == row["token_budget"][key]
                                             for key in ("sequence_sha256", "sequence_tokens"))
        receipt["status"] = "completed"
    except Exception as exc:
        receipt.update(status="failed_or_unknown", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save()
    print(json.dumps({key: receipt.get(key) for key in ("case", "status", "semantics_match", "input_verified")}))


if __name__ == "__main__":
    main()
