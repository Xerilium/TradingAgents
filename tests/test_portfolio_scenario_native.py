"""Synthetic fixture only: this is not historical market evidence or performance."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tradingagents" / "web"))
from evaluation import digest


class SyntheticNativePortfolioTest(unittest.TestCase):
    def test_dynamic_capital_and_native_fills(self):
        symbols = ("MSFT", "AMZN", "SGOV")
        model = {"id": "synthetic", "inputs": [{"symbol": s} for s in symbols],
                 "result": {"capital": 200000, "target_cash_weight": 0.4,
                            "allocations": [{"symbol": s, "weight": w} for s, w in zip(symbols, (0.12, 0.08, 0.4))]}}
        bars = {s: {day: {"open": "100", "high": "100", "low": "100", "close": "100", "volume": "100000"}
                    for day in ("2021-11-04", "2021-11-05")} for s in symbols}
        spec = {"kind": "portfolio_scenario", "model": model, "fee_usd": "0", "bars": bars,
                "actions": {s: [] for s in symbols}}
        spec["spec_sha256"] = digest(spec)
        worker = Path(__file__).resolve().parents[1] / "tradingagents" / "web" / "evaluation_worker.py"
        result = subprocess.run([sys.executable, str(worker)], input=json.dumps(spec), text=True, capture_output=True, check=True)
        result = json.loads(result.stdout)
        self.assertEqual(result["status"], "completed", result.get("error"))
        self.assertEqual(result["ledger"]["shares"], {"MSFT": "240", "AMZN": "160", "SGOV": "800"})
        self.assertEqual(result["ledger"]["cash_usd"], "80000")
        report = result["native_fills"]
        rows = [dict(zip(report["columns"], row)) for row in report["data"]]
        self.assertEqual({row["instrument_id"]: row["last_qty"] for row in rows},
                         {"MSFT.ALPACA": "240", "AMZN.ALPACA": "160", "SGOV.ALPACA": "800"})
        self.assertTrue(all(row["commission"] == "0.00 USD" for row in rows))
        print("Synthetic native fills: MSFT 240, AMZN 160, SGOV 800; zero commission; cash USD 80000")


if __name__ == "__main__":
    unittest.main()
