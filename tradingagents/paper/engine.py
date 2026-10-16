"""Deterministic, cash-funded paper equity orders from reviewed analysis.

The model supplies a rating. This module owns quantities, cash reservations,
price limits, and the final check immediately before submission. It never calls
a broker and cannot establish whether a broker connection is a paper account.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

ZERO = Decimal("0")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
_TERMINAL_ORDERS = {"filled", "canceled", "cancelled", "expired", "rejected", "replaced"}
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def _now() -> datetime:
    return datetime.now(UTC)


def _decimal(value, name, *, positive=False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} is missing or invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} is invalid") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return number


def _symbol(value) -> str:
    symbol = str(value or "").strip().upper()
    if not _SYMBOL.fullmatch(symbol):
        raise ValueError("Invalid stock symbol")
    return symbol


def _settings(config) -> dict:
    universe = [_symbol(value) for value in config.get("universe", [])]
    if not universe or len(set(universe)) != len(universe):
        raise ValueError("Universe must contain distinct stock symbols")
    settings = {"universe": universe}
    for key, default in (("allocation_pct", 70), ("max_position_pct", 15),
                         ("reserve_pct", 20), ("max_order_notional", 5000),
                         ("price_buffer_bps", 25)):
        settings[key] = _decimal(config.get(key, default), key)
    if any(settings[key] > 100 for key in ("allocation_pct", "max_position_pct", "reserve_pct")):
        raise ValueError("Allocation, position, and reserve percentages cannot exceed 100")
    if settings["max_order_notional"] == 0 or settings["max_position_pct"] == 0:
        raise ValueError("Order and position limits must be positive")
    if settings["price_buffer_bps"] >= 10000:
        raise ValueError("Price buffer must be below 10000 basis points")
    return settings


def _account(account) -> tuple[Decimal, Decimal]:
    if str(account.get("status", "")).upper() != "ACTIVE":
        raise ValueError("Account must be ACTIVE")
    if str(account.get("currency", "")).upper() != "USD":
        raise ValueError("Only USD equity accounts are supported")
    for key in ("trading_blocked", "account_blocked", "trade_suspended_by_user"):
        value = account.get(key, False)
        if value not in (False, "false", "False", 0):
            raise ValueError(f"Account restriction: {key}")
    return (_decimal(account.get("cash"), "Account cash"),
            _decimal(account.get("equity"), "Account equity", positive=True))


def _positions(positions) -> dict[str, Decimal]:
    book = {}
    for position in positions:
        symbol = _symbol(position.get("symbol", position.get("ticker")))
        if symbol in book:
            raise ValueError(f"Duplicate position for {symbol}")
        book[symbol] = _decimal(position.get("qty", position.get("quantity")),
                                f"{symbol} held quantity")
    return book


def _long_exposure(account, positions, quotes, now) -> Decimal:
    """Value the entire long book, including holdings outside the chosen index."""
    if account.get("long_market_value") is not None:
        return _decimal(account["long_market_value"], "Account long market value")
    exposure = ZERO
    for position in positions:
        symbol = _symbol(position.get("symbol", position.get("ticker")))
        if position.get("market_value") is not None:
            exposure += _decimal(position["market_value"], f"{symbol} position market value")
            continue
        quantity = _decimal(position.get("qty", position.get("quantity")),
                            f"{symbol} held quantity")
        if quantity:
            exposure += quantity * _quote(quotes, symbol, now)["price"]
    return exposure


def _timestamp(value) -> datetime:
    try:
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            timestamp = datetime.fromtimestamp(value, UTC)
        else:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Quote timestamp requires a timezone")
        return timestamp.astimezone(UTC)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise ValueError("Quote timestamp is missing or invalid") from exc


def _quote(quotes, symbol, now) -> dict:
    quote = quotes.get(symbol)
    if not isinstance(quote, dict):
        raise ValueError(f"No quote for {symbol}")
    if quote.get("invalid_quote"):
        raise ValueError(f"Quote for {symbol} contains an invalid bid or ask")
    age = now - _timestamp(quote.get("timestamp"))
    if age > timedelta(minutes=15) or age < -timedelta(seconds=60):
        raise ValueError(f"Quote for {symbol} is stale or future-dated")
    if "quote_timestamp" in quote:
        quote_age = now - _timestamp(quote["quote_timestamp"])
        if quote_age > timedelta(minutes=15) or quote_age < -timedelta(seconds=60):
            raise ValueError(f"Bid/ask quote for {symbol} is stale or future-dated")
    price = _decimal(quote.get("price"), f"{symbol} quote price", positive=True)
    bid = _decimal(price if quote.get("bid") is None else quote["bid"],
                   f"{symbol} bid", positive=True)
    ask = _decimal(price if quote.get("ask") is None else quote["ask"],
                   f"{symbol} ask", positive=True)
    if bid > ask:
        raise ValueError(f"Quote for {symbol} has crossed bid and ask")
    return {"price": price, "bid": bid, "ask": ask}


def _limit(quote, side, settings) -> Decimal:
    buffer = settings["price_buffer_bps"] / Decimal("10000")
    if side == "buy":
        return (quote["ask"] * (1 + buffer)).quantize(CENT, rounding=ROUND_CEILING)
    price = (quote["bid"] * (1 - buffer)).quantize(CENT, rounding=ROUND_FLOOR)
    if price <= 0:
        raise ValueError("Buffered sell limit is below one cent")
    return price


def _reservations(open_orders, quotes, settings, now):
    reserved_cash = ZERO
    reserved_shares = {}
    occupied = set()
    for order in open_orders:
        if str(order.get("status", "")).lower() in _TERMINAL_ORDERS:
            continue
        symbol = _symbol(order.get("symbol"))
        side = str(order.get("side", "")).lower()
        if side not in ("buy", "sell"):
            raise ValueError(f"Open order for {symbol} has an unknown side")
        occupied.add(symbol)
        if side == "buy" and order.get("notional") is not None:
            reserved_cash += _decimal(order["notional"], f"{symbol} open buy notional")
            continue
        quantity = _decimal(order.get("qty"), f"{symbol} open order quantity")
        filled = _decimal(order.get("filled_qty", 0), f"{symbol} filled quantity")
        if filled > quantity:
            raise ValueError(f"Open order for {symbol} has invalid filled quantity")
        remaining = quantity - filled
        if side == "sell":
            reserved_shares[symbol] = reserved_shares.get(symbol, ZERO) + remaining
        else:
            if order.get("limit_price") is not None:
                price = _decimal(order["limit_price"], f"{symbol} open buy price", positive=True)
            else:
                price = _limit(_quote(quotes, symbol, now), "buy", settings)
            reserved_cash += remaining * price
    return reserved_cash, reserved_shares, occupied


def _whole(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_DOWN))


def _proposal(run_id, symbol, now) -> dict:
    return {"id": str(uuid5(NAMESPACE_URL, f"tradingagents:paper:{run_id}:{symbol}")),
            "symbol": symbol, "side": None, "qty": 0, "limit_price": "0.00",
            "notional": "0.00", "status": "skipped", "reason": "", "run_id": str(run_id),
            "created_at": now.isoformat(), "type": "limit", "time_in_force": "day"}


def plan_orders(config, account, positions, open_orders, quotes, results, run_id) -> list[dict]:
    """Plan a bounded batch, reserving each buy's cash and total allocation once.

    Each analysis must be completed on today's New York date, contain a known
    rating, and satisfy the deterministic trading limits before proposing an order.
    Sales never fund buys in this batch. Invalid shared account data raises;
    per-symbol data failures produce a visible blocked row.
    """
    now = _now()
    today = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    settings = _settings(config)
    cash, equity = _account(account)
    book = _positions(positions)
    exposure = _long_exposure(account, positions, quotes, now)
    reserved_cash, reserved_shares, occupied = _reservations(open_orders, quotes, settings, now)
    available = max(ZERO, cash - equity * settings["reserve_pct"] / HUNDRED - reserved_cash)
    allocation_available = max(
        ZERO, equity * settings["allocation_pct"] / HUNDRED - exposure - reserved_cash
    )
    analysis = {}
    for result in results:
        symbol = _symbol(result.get("symbol"))
        if symbol in analysis:
            raise ValueError(f"Duplicate analysis for {symbol}")
        analysis[symbol] = result
    proposals = []
    for symbol in settings["universe"]:
        proposal = _proposal(run_id, symbol, now)
        proposals.append(proposal)
        try:
            result = analysis.get(symbol, {})
            if result.get("status") != "completed" or result.get("trade_date") != today:
                raise ValueError("A completed analysis for today's trading date is required")
            rating = result.get("rating")
            if rating in ("Hold", "REVIEW"):
                proposal["reason"] = f"{rating}: no order"
                continue
            if rating not in ("Buy", "Overweight", "Underweight", "Sell"):
                raise ValueError("Analysis has no recognized rating")
            if symbol in occupied:
                raise ValueError("An open order already exists for this symbol")
            quote = _quote(quotes, symbol, now)
            held = book.get(symbol, ZERO)
            side = "buy" if rating in ("Buy", "Overweight") else "sell"
            price = _limit(quote, side, settings)
            if side == "buy":
                target_pct = min(settings["allocation_pct"] / len(settings["universe"]),
                                 settings["max_position_pct"])
                if rating == "Overweight":
                    target_pct *= Decimal("0.75")
                shortfall = max(ZERO, equity * target_pct / HUNDRED - held * quote["price"])
                budget = min(shortfall, settings["max_order_notional"], available, allocation_available)
                quantity = _whole(budget / price)
            else:
                free = max(ZERO, held - reserved_shares.get(symbol, ZERO))
                target = free / 2 if rating == "Underweight" else free
                quantity = min(_whole(target), _whole(settings["max_order_notional"] / price))
            if quantity == 0:
                proposal["reason"] = "No whole shares fit the position, allocation, order, and cash limits"
                continue
            notional = quantity * price
            proposal.update(side=side, qty=quantity, limit_price=str(price),
                            notional=f"{notional:.2f}", status="proposed",
                            reason=f"{rating}: deterministic full-share allocation")
            if side == "buy":
                available -= notional
                allocation_available -= notional
        except ValueError as exc:
            proposal.update(status="blocked", reason=str(exc))
    return proposals


def validate_proposal(proposal, config, account, positions, open_orders, quotes) -> dict:
    """Validate the approved quantities unchanged against a fresh broker snapshot.

    Returns the original proposal, or raises ``ValueError``. The caller must
    separately establish paper-account provenance, approval, and run freshness.
    """
    now = _now()
    settings = _settings(config)
    cash, equity = _account(account)
    book = _positions(positions)
    reserved_cash, reserved_shares, occupied = _reservations(open_orders, quotes, settings, now)
    symbol = _symbol(proposal.get("symbol"))
    if symbol not in settings["universe"]:
        raise ValueError("Symbol is outside the configured universe")
    if proposal.get("status") != "proposed":
        raise ValueError("Only proposed orders can be submitted")
    if proposal.get("type", "limit") != "limit" or proposal.get("time_in_force", "day") != "day":
        raise ValueError("Only DAY limit orders are supported")
    if symbol in occupied:
        raise ValueError("An open order already exists for this symbol")
    side = proposal.get("side")
    if side not in ("buy", "sell"):
        raise ValueError("Order side must be buy or sell")
    quantity = _decimal(proposal.get("qty"), "Order quantity", positive=True)
    if quantity != quantity.to_integral_value():
        raise ValueError("Only whole-share orders are supported")
    price = _decimal(proposal.get("limit_price"), "Limit price", positive=True)
    if price != price.quantize(CENT):
        raise ValueError("Limit price must use cent increments")
    notional = quantity * price
    if _decimal(proposal.get("notional"), "Order notional", positive=True) != notional:
        raise ValueError("Order notional does not match its quantity and limit")
    if notional > settings["max_order_notional"]:
        raise ValueError("Order exceeds the configured notional limit")
    quote = _quote(quotes, symbol, now)
    fresh_limit = _limit(quote, side, settings)
    # A changed market may make the approved limit unsafe; never silently reprice.
    if (side == "buy" and price > fresh_limit) or (side == "sell" and price < fresh_limit):
        raise ValueError("Approved limit is outside the current buffered quote; create a new plan")
    held = book.get(symbol, ZERO)
    if side == "buy":
        available = max(ZERO, cash - equity * settings["reserve_pct"] / HUNDRED - reserved_cash)
        if notional > available:
            raise ValueError("Insufficient cash after the reserve and open buy orders")
        exposure = _long_exposure(account, positions, quotes, now)
        allocation_available = max(
            ZERO, equity * settings["allocation_pct"] / HUNDRED - exposure - reserved_cash
        )
        if notional > allocation_available:
            raise ValueError("Order exceeds the total allocation limit after existing holdings and open buys")
        if held * quote["price"] + notional > equity * settings["max_position_pct"] / HUNDRED:
            raise ValueError("Order exceeds the configured position limit")
    elif quantity > held - reserved_shares.get(symbol, ZERO):
        raise ValueError("Insufficient unreserved shares; short selling is disabled")
    return proposal
