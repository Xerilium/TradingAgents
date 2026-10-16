"""Cash, holdings, provenance and price limits for paper equity proposals."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tradingagents.paper import engine

NOW = datetime(2026, 10, 13, 18, 0, tzinfo=UTC)


@pytest.fixture
def inputs(monkeypatch):
    monkeypatch.setattr(engine, "_now", lambda: NOW)
    return {
        "config": {"universe": ["AAPL", "MSFT"], "allocation_pct": 70,
                   "max_position_pct": 15, "max_order_notional": 5000,
                   "reserve_pct": 20, "price_buffer_bps": 25},
        "account": {"status": "ACTIVE", "currency": "USD", "equity": "100000",
                    "cash": "100000", "trading_blocked": False, "account_blocked": False},
        "positions": [], "open_orders": [],
        "quotes": {symbol: {"price": "100", "bid": "100", "ask": "100",
                            "timestamp": NOW.isoformat()} for symbol in ("AAPL", "MSFT")},
        "results": [{"symbol": symbol, "status": "completed", "trade_date": "2026-10-13",
                     "rating": "Buy", "laya": {"auto_execute": True}}
                    for symbol in ("AAPL", "MSFT")],
        "run_id": "run-1",
    }


def plan(inputs):
    return engine.plan_orders(**inputs)


def validate(proposal, inputs):
    return engine.validate_proposal(proposal, **{
        key: value for key, value in inputs.items() if key not in ("results", "run_id")
    })


def test_orders_are_stable_full_share_day_limits_with_exact_decimal_math(inputs):
    first, second = plan(inputs)
    assert first["qty"] == 49
    assert first["limit_price"] == "100.25"
    assert first["notional"] == "4912.25"
    assert first["type"] == "limit"
    assert first["time_in_force"] == "day"
    assert first["id"] == plan(inputs)[0]["id"]
    assert first["id"] != second["id"]
    assert validate(first, inputs) is first


def test_cash_reserve_is_shared_across_proposals_and_ignores_buying_power(inputs):
    inputs["account"].update(cash="26000", buying_power="1000000")
    orders = plan(inputs)
    assert [order["qty"] for order in orders] == [49, 10]
    assert sum(Decimal(order["notional"]) for order in orders) <= Decimal("6000")


def test_existing_buys_reserve_cash_even_outside_the_universe(inputs):
    inputs["account"]["cash"] = "26000"
    inputs["open_orders"] = [{"symbol": "NVDA", "side": "buy", "qty": "40",
                              "filled_qty": "10", "limit_price": "100", "status": "new"}]
    orders = plan(inputs)
    assert orders[0]["qty"] == 29
    assert orders[1]["status"] == "skipped"


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_any_open_order_blocks_the_symbol(inputs, side):
    inputs["open_orders"] = [{"symbol": "AAPL", "side": side, "qty": "1",
                              "limit_price": "100", "status": "accepted"}]
    assert plan(inputs)[0]["status"] == "blocked"
    assert "open order" in plan(inputs)[0]["reason"]


def test_sell_proceeds_never_fund_other_buys(inputs):
    inputs["account"]["cash"] = "20000"
    inputs["positions"] = [{"symbol": "AAPL", "qty": "10"}]
    inputs["results"][0]["rating"] = "Sell"
    sell, buy = plan(inputs)
    assert (sell["side"], sell["qty"], sell["limit_price"]) == ("sell", 10, "99.75")
    assert buy["status"] == "skipped"


@pytest.mark.parametrize(("rating", "expected"), [("Sell", 9), ("Underweight", 4)])
def test_reductions_use_only_held_full_shares(inputs, rating, expected):
    inputs["positions"] = [{"symbol": "AAPL", "qty": "9.75"}]
    inputs["results"][0]["rating"] = rating
    order = plan(inputs)[0]
    assert order["qty"] == expected
    assert validate(order, inputs) is order


def test_buy_and_overweight_targets_are_deterministic_and_capped(inputs):
    inputs["config"].update(allocation_pct=20, max_order_notional=20000)
    inputs["results"][1]["rating"] = "Overweight"
    buy, overweight = plan(inputs)
    assert buy["qty"] == 99
    assert overweight["qty"] == 74
    inputs["positions"] = [{"symbol": "AAPL", "qty": "100"}]
    assert plan(inputs)[0]["status"] == "skipped"


@pytest.mark.parametrize("rating", ["Hold", "REVIEW"])
def test_hold_and_review_do_not_order_even_without_laya(inputs, rating):
    inputs["results"][0].update(rating=rating, laya=None)
    assert plan(inputs)[0]["status"] == "skipped"


@pytest.mark.parametrize("result_patch", [
    {"status": "failed"}, {"trade_date": "2026-10-12"}, {"rating": "BUY NOW"},
])
def test_only_completed_current_recognized_analysis_can_propose(inputs, result_patch):
    inputs["results"][0].update(result_patch)
    assert plan(inputs)[0]["status"] == "blocked"


@pytest.mark.parametrize("timestamp", [
    (NOW - timedelta(minutes=16)).isoformat(),
    (NOW + timedelta(minutes=2)).isoformat(),
    "2026-10-13T18:00:00", None,
])
def test_missing_stale_or_future_quote_timestamps_block(inputs, timestamp):
    inputs["quotes"]["AAPL"]["timestamp"] = timestamp
    assert plan(inputs)[0]["status"] == "blocked"


@pytest.mark.parametrize("account_patch", [
    {"trading_blocked": True}, {"account_blocked": True}, {"status": "ACCOUNT_UPDATED"},
    {"currency": "EUR"}, {"cash": "NaN"}, {"equity": "Infinity"}, {"cash": "-1"},
])
def test_restricted_or_invalid_accounts_are_rejected(inputs, account_patch):
    inputs["account"].update(account_patch)
    with pytest.raises(ValueError):
        plan(inputs)


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-100", "0", True])
def test_invalid_market_prices_block(inputs, price):
    inputs["quotes"]["AAPL"]["price"] = price
    assert plan(inputs)[0]["status"] == "blocked"


@pytest.mark.parametrize(("field", "value"), [("bid", 0), ("ask", False), ("bid", 101)])
def test_invalid_or_crossed_bid_ask_cannot_fall_back_to_last_price(inputs, field, value):
    inputs["quotes"]["AAPL"][field] = value
    assert plan(inputs)[0]["status"] == "blocked"


@pytest.mark.parametrize("value", [False, "NaN", None, "garbage", 0])
def test_normalized_malformed_quote_cannot_become_trade_price(inputs, value):
    from tradingagents.web.service import normalize_quotes

    inputs["quotes"] = normalize_quotes({"AAPL": {
        "latestTrade": {"p": 100, "t": NOW.isoformat()},
        "latestQuote": {"bp": 99, "ap": value, "t": NOW.isoformat()},
    }})
    assert plan(inputs)[0]["status"] == "blocked"


@pytest.mark.parametrize("quote_time", [None, (NOW - timedelta(minutes=16)).isoformat()])
def test_normalized_quote_requires_own_freshness_even_with_fresh_trade(inputs, quote_time):
    from tradingagents.web.service import normalize_quotes

    inputs["quotes"] = normalize_quotes({"AAPL": {
        "latestTrade": {"p": 100, "t": NOW.isoformat()},
        "latestQuote": {"bp": 99, "ap": 100, "t": quote_time},
    }})
    assert plan(inputs)[0]["status"] == "blocked"


def test_pre_submit_validation_uses_fresh_cash_and_does_not_resize(inputs):
    proposal = plan(inputs)[0]
    approved = deepcopy(proposal)
    inputs["account"]["cash"] = "20100"
    with pytest.raises(ValueError, match="Insufficient cash"):
        validate(proposal, inputs)
    assert proposal == approved


def test_pre_submit_validation_rejects_new_open_orders_and_insufficient_shares(inputs):
    inputs["positions"] = [{"symbol": "AAPL", "qty": "10"}]
    inputs["results"][0]["rating"] = "Sell"
    proposal = plan(inputs)[0]
    inputs["positions"][0]["qty"] = "9"
    with pytest.raises(ValueError, match="short selling"):
        validate(proposal, inputs)
    inputs["open_orders"] = [{"symbol": "AAPL", "side": "sell", "qty": "1"}]
    with pytest.raises(ValueError, match="open order"):
        validate(proposal, inputs)


@pytest.mark.parametrize("changes", [
    {"qty": "1.5"}, {"notional": "0.01"}, {"limit_price": "100.251"},
    {"side": "short"}, {"type": "market"}, {"time_in_force": "gtc"},
    {"symbol": "NVDA"}, {"status": "blocked"},
])
def test_pre_submit_rejects_malformed_or_changed_proposals(inputs, changes):
    proposal = plan(inputs)[0]
    proposal.update(changes)
    with pytest.raises(ValueError):
        validate(proposal, inputs)


def test_quote_movement_requires_a_new_plan_instead_of_repricing(inputs):
    proposal = plan(inputs)[0]
    inputs["quotes"]["AAPL"].update(price="90", bid="90", ask="90")
    with pytest.raises(ValueError, match="new plan"):
        validate(proposal, inputs)


def test_position_cap_is_checked_again_at_submission(inputs):
    proposal = plan(inputs)[0]
    inputs["positions"] = [{"symbol": "AAPL", "qty": "140"}]
    with pytest.raises(ValueError, match="position limit"):
        validate(proposal, inputs)


def test_unknown_open_market_buy_value_fails_closed(inputs):
    inputs["open_orders"] = [{"symbol": "NVDA", "side": "buy", "qty": "5", "type": "market"}]
    with pytest.raises(ValueError, match="No quote"):
        plan(inputs)


def test_unrelated_holdings_can_exhaust_the_total_allocation(inputs):
    inputs["positions"] = [{"symbol": "NVDA", "qty": "700", "market_value": "70000"}]
    assert all(order["status"] == "skipped" for order in plan(inputs))


def test_allocation_budget_is_shared_across_existing_open_and_proposed_buys(inputs):
    inputs["positions"] = [{"symbol": "NVDA", "qty": "660", "market_value": "66000"}]
    inputs["open_orders"] = [{"symbol": "META", "side": "buy", "qty": "10",
                              "limit_price": "100", "status": "new"}]
    first, second = plan(inputs)
    assert first["qty"] == 29
    assert first["notional"] == "2907.25"
    assert second["status"] == "skipped"


def test_broker_long_market_value_takes_precedence_over_partial_position_values(inputs):
    inputs["account"]["long_market_value"] = "70000"
    inputs["positions"] = [{"symbol": "NVDA", "qty": "700"}]
    assert all(order["status"] == "skipped" for order in plan(inputs))


def test_long_exposure_falls_back_to_fresh_quote_when_market_value_missing(inputs):
    inputs["positions"] = [{"symbol": "NVDA", "qty": "700"}]
    inputs["quotes"]["NVDA"] = dict(inputs["quotes"]["AAPL"])
    assert all(order["status"] == "skipped" for order in plan(inputs))


def test_missing_existing_holding_valuation_fails_closed(inputs):
    inputs["positions"] = [{"symbol": "NVDA", "qty": "700"}]
    with pytest.raises(ValueError, match="No quote"):
        plan(inputs)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", True])
def test_invalid_total_long_market_value_fails_closed(inputs, value):
    inputs["account"]["long_market_value"] = value
    with pytest.raises(ValueError, match="long market value"):
        plan(inputs)


def test_pre_submit_rechecks_total_allocation_against_fresh_exposure(inputs):
    proposal = plan(inputs)[0]
    approved = deepcopy(proposal)
    inputs["account"]["long_market_value"] = "69000"
    with pytest.raises(ValueError, match="total allocation limit"):
        validate(proposal, inputs)
    assert proposal == approved


def test_pre_submit_includes_unrelated_open_buys_in_total_allocation(inputs):
    proposal = plan(inputs)[0]
    inputs["account"]["long_market_value"] = "65000"
    inputs["open_orders"] = [{"symbol": "NVDA", "side": "buy", "qty": "10",
                              "limit_price": "100", "status": "new"}]
    with pytest.raises(ValueError, match="total allocation limit"):
        validate(proposal, inputs)
