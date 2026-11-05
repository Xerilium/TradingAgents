import copy
import unittest

from tradingagents.web.portfolio_scenario import account_portfolio, parse_actions, validate_model


class PortfolioScenarioTransferTest(unittest.TestCase):
    def setUp(self):
        self.model = {"id": "original-job", "inputs": [{"symbol": s} for s in ("MSFT", "AMZN", "SGOV")],
                      "result": {"capital": 100000, "target_cash_weight": 0.4,
                                 "allocations": [{"symbol": s, "weight": w} for s, w in (("MSFT", 0.12), ("AMZN", 0.08), ("SGOV", 0.4))]}}

    def test_exact_weights_drive_accounting(self):
        bars = {s: {"2021-11-04": {"open": "100", "close": "100"}} for s in ("MSFT", "AMZN", "SGOV")}
        fills = {s: {"shares": q, "price": "100", "fee_usd": "0"} for s, q in (("MSFT", "120"), ("AMZN", "80"), ("SGOV", "400"))}
        ledger = account_portfolio(bars, {s: [] for s in bars}, "0", fills, self.model)
        self.assertEqual(ledger["shares"], {"MSFT": "120", "AMZN": "80", "SGOV": "400"})
        self.assertEqual(ledger["cash_usd"], "40000")

    def test_rejects_invalid_archives_and_missing_evidence(self):
        for change in (lambda m: m.pop("id"), lambda m: m["result"].update(capital="NaN"),
                       lambda m: m["result"]["allocations"][0].update(weight=-1),
                       lambda m: m["inputs"][0].update(symbol="OTHER"),
                       lambda m: m["result"].update(target_cash_weight=0.3)):
            model = copy.deepcopy(self.model)
            change(model)
            with self.assertRaises(ValueError):
                validate_model(model)
        with self.assertRaises(ValueError):
            parse_actions("MSFT", "2021-11-04", "2026-11-04", None)


if __name__ == "__main__":
    unittest.main()
