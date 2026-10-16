"""Run one explicit, bounded Laya control through the MCP SDK; never submit orders.

Invoke under .paper-desk/run-bounded.py --seconds 85. Receipts prohibit replay.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tradingagents.integrations.maenifold import MaenifoldGateway
from tradingagents.web.laya_review import QUESTIONS, LIMIT, RESERVE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--series", default="")
    args = parser.parse_args()
    controls = json.loads((ROOT / "tests/laya_choice_controls.json").read_text())
    if args.case == "saved_meta":
        saved = json.loads((ROOT / ".paper-desk/laya-saved-packet-review.json").read_text(encoding="utf-8"))
        control = {"id": "saved_meta", "expected": {"evidence_complete": "B"},
                   "state": saved["audit"]["parameters"]["state"]}
    else:
        control = next(c for c in controls["controls"] if c["id"] == args.case)
    questions = copy.deepcopy(QUESTIONS)
    if args.questions:
        questions = json.loads(args.questions.read_text(encoding="utf-8"))
        if not args.series or not args.series.replace('-', '').isalnum():
            raise ValueError("Candidate questions require a simple unique series identifier")
    assert all(q["kind"] == "choice" for q in questions.values())
    if args.reverse:
        for question in questions.values():
            question["criteria"] = dict(reversed(list(question["criteria"].items())))
    name = args.case + ("-reverse" if args.reverse else "-forward")
    if args.series:
        name = args.series + "-" + name
    output = ROOT / ".paper-desk" / ("laya-control-" + name + ".json")
    journal = json.loads((ROOT / ".paper-desk/desk.json").read_text(encoding="utf-8"))
    assert not any(r["status"] in ("running", "queued", "cancelling") for r in journal["runs"])
    parameters = {"state": control["state"], "questions": questions,
                  "model": "multilingual", "threshold": "high"}
    receipt = {"status": "prepared", "case": name, "expected": control["expected"],
               "parameters": parameters}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    try:
        gateway = MaenifoldGateway(timeout=65)
        gateway.discover("laya")
        count = gateway.execute("laya", "count_context", {
            key: parameters[key] for key in ("state", "questions", "model")})
        receipt["preflight"] = count
        assert count["effective_max_tokens"] == LIMIT
        assert count["state_complete"] and count["questions_complete"]
        assert max(count["sequence_tokens"].values()) <= LIMIT - RESERVE
        receipt["status"] = "dispatched_once"
        output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        def dispatch_once():
            if receipt.get("inference_dispatches", 0):
                raise RuntimeError("Control inference retry refused; inspect original receipt")
            receipt["inference_dispatches"] = 1
            output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        result = gateway.execute("laya", "decide", parameters, on_dispatch=dispatch_once)
        receipt["result"] = result
        actual = result["usage"]["context_budget"]
        assert actual["sequence_sha256"] == count["sequence_sha256"]
        assert actual["sequence_tokens"] == count["sequence_tokens"]
        answers = {key: value.get("value") for key, value in result["answers"].items()}
        receipt["observed"] = answers
        receipt["semantics_match"] = all(answers.get(key) == value for key, value in control["expected"].items())
        receipt["status"] = "verified_transport"
    except Exception as exc:
        receipt["status"] = "failed_or_unknown"
        receipt["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in (
        "case", "status", "expected", "observed", "semantics_match")}))


if __name__ == "__main__":
    main()
