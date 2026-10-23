"""Compare broker receipts with Nautilus cache snapshots; never calculate a new ledger."""

from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal

from .linked_orders import broker_position_quantity, native_type, native_trail


def history_scope(observed):
    history = observed.get("recovery_history") or {}
    known = all(isinstance(history.get(key), str) and history[key] for key in ("from", "through"))
    complete = known and history.get("complete") is True
    label = ("Source history " + history["from"] + " through " + history["through"] +
             ("; complete for this declared scope" if complete else "; incomplete")) if known else "Source history scope unknown (legacy or incomplete observation); completeness not established"
    limits = history.get("limits")
    if isinstance(limits, dict) and type(limits.get("records")) is int and type(limits.get("pages")) is int:
        label += "; collector limit " + str(limits["records"]) + " activities / " + str(limits["pages"]) + " pages per collection"
    return {"fill_window": label, "fill_window_start_ns": observed.get("lookback_start") if complete else None,
            "fill_history_complete": complete, "fill_history_records": history.get("records"), "fill_history_limits": limits}


def reconcile(observed, native_positions, native_orders, native_cash, *, commands=None, native_epoch=None, native_balance=None):
    gaps = list(observed.get("gaps", []))
    positions, orders, reporting_gaps = [], [], []
    broker_id = (observed.get("account") or {}).get("id")
    native_account_id = "ALPACA-" + broker_id if broker_id else None
    native_by_symbol = {p["instrument_id"].removesuffix(".ALPACA"): p for p in native_positions}
    for source in observed.get("positions", []):
        row = dict(source)
        with suppress(ValueError, TypeError, ArithmeticError, KeyError):
            row["qty"] = str(broker_position_quantity(source))
        if row.get("asset_class") == "us_option":
            from .linked_orders import option_contract
            try:
                option_contract(row.get("option_contract"))
            except (ValueError, KeyError, TypeError, ArithmeticError):
                reason = "Option contract/deliverable metadata is unavailable; native economics remain unknown"
                row.update(import_error=reason, reconciliation_status="incomplete", management_supported=False,
                    nautilus=None, exposure_status="unknown")
                positions.append(row)
                gaps.append(str(row.get("symbol", "Unidentified option")) + ": " + reason)
                continue
        if row.get("asset_class") not in {"us_equity", "us_option"}:
            reason = row.get("import_error") or "Unsupported position retained; native exposure is unknown"
            row.update(import_error=reason, reconciliation_status="incomplete", management_supported=False,
                       nautilus=None, exposure_status="unknown")
            gaps.append(str(row.get("symbol", row.get("asset_id", "Unidentified position"))) + ": " + reason)
            positions.append(row)
            continue
        native = native_by_symbol.pop(row["symbol"], None)
        reason, cost_reason = row.get("import_error"), None
        if not reason and native is None:
            reason = "Position is not present in the Nautilus cache"
        if not reason:
            if not native_account_id or native.get("account_id") != native_account_id:
                reason = "Native position account identity is unavailable or differs"
            actual = Decimal(native["quantity"])
            expected = broker_position_quantity(row)
            signed = -actual if str(native["side"]) == "SHORT" else actual
            if signed != expected or str(native["side"]) not in {"LONG", "SHORT"}:
                reason = "Native position quantity/direction differs from broker observation"
            average = native.get("avg_px_open")
            if average is None:
                cost_reason = "Native average cost unavailable; broker cost remains authoritative"
            elif Decimal(str(average)) != Decimal(str(row["avg_entry_price"])):
                cost_reason = "Reported native average cost differs from broker average cost"
            if average is not None and row.get("cost_basis") is not None:
                from .linked_orders import contract_multiplier
                multiplier = contract_multiplier(row)
                if signed * Decimal(str(average)) * multiplier != Decimal(str(row["cost_basis"])):
                    cost_reason = cost_reason or "Reported broker cost basis differs from native quantity × average"
        if cost_reason:
            reporting_gaps.append(row["symbol"] + ": " + cost_reason)
        row.update(source_import_error=source.get("import_error"), native_comparison_gap=reason, native_cost_comparison_gap=cost_reason,
                   reconciliation_status="incomplete" if reason else "reconciled",
                   import_error=reason, nautilus=native, management_supported=False)
        if reason:
            gaps.append(row["symbol"] + ": " + reason)
        positions.append(row)
    positions_reconciled = bool(observed.get("account_at")) and not observed.get("error") and not native_by_symbol and all(p["reconciliation_status"] == "reconciled" for p in positions)
    if native_by_symbol:
        gaps.append("Native positions remain which the complete broker position response reports absent")
    def venue_id(order):
        binding = order.get("venue_order_id_binding") or {}
        return order.get("venue_order_id") or (binding.get("venue_order_id")
            if order.get("status") in {"SUBMITTED", "PENDING_CANCEL", "PENDING_UPDATE"}
            and binding.get("source") == "native_cache_venue_order_index"
            and binding.get("client_order_id") == order.get("client_order_id") else None)
    by_id = {str(venue_id(o)): o for o in native_orders}
    for source in observed.get("orders", []):
        package = source.get("package_terms")
        if source.get("package_parent_id"):
            parent = next((row for row in orders if row.get("id") == source["package_parent_id"]), {})
            reason = parent.get("import_error") or (None if parent.get("package_mapping") else "Actual package parent control mapping is unavailable")
            orders.append({**source, "nautilus": None, "management_supported": False, "import_error": reason,
                "reconciliation_status": "incomplete" if reason else "reconciled", "package_leg_observation": True,
                "economics_basis": "Actual leg executions only; parent control is not a leg order"})
            if reason:
                gaps.append(source["id"] + ": " + reason)
            continue
        if not package and (source.get("asset_class") not in {"us_equity", "us_option"} or source.get("order_class") not in {None, "", "simple", "bracket", "oto", "oco"}):
            reason = source.get("import_error") or "Unsupported broker order retained; commitment is unknown"
            orders.append({**source, "import_error": reason, "reconciliation_status": "incomplete",
                           "management_supported": False, "nautilus": None, "exposure_status": "unknown", "cash_commitment": None})
            gaps.append(str(source.get("id", "Unidentified order")) + ": " + reason)
            continue
        row, native = dict(source), by_id.pop(source["id"], None)
        expected_instrument = package["instrument_id"] if package else row.get("symbol", "") + ".ALPACA"
        if package and native is not None:
            native = {**native, "package_control": source["package_control"]}
        reason, cost_reason = row.get("import_error"), None
        if not reason and native is None:
            reason = "Open order is not present in the Nautilus cache"
        binding = (native or {}).get("account_binding") or {}
        bound = (binding.get("account_id") == native_account_id and binding.get("client_id") == "ALPACA"
                 and binding.get("venue") == "ALPACA" and binding.get("event_ids")
                 and binding.get("source") == "native_order_events_and_execution_client")
        account_matches = bound if native is not None and "account_binding" in native else (native or {}).get("account_id") == native_account_id
        if not reason and (not native_account_id or not account_matches
                           or native.get("instrument_id") != expected_instrument
                           or venue_id(native) != row.get("id")
                           or not row.get("client_order_id") or native.get("client_order_id") != row.get("native_client_order_id", row["client_order_id"])):
            reason = "Native order account/instrument/client/venue identity is unavailable or differs"
        offset = Decimal(str((row.get("native_replacement_quantity_binding") or {}).get("ancestor_filled_quantity", "0")))
        if not reason and (Decimal(native["quantity"]) + offset != Decimal(row["qty"])
                           or Decimal(native["filled_qty"]) + offset != Decimal(row["filled_qty"])):
            reason = "Native order quantities differ from broker observation"
        expected_status = {"new": "ACCEPTED", "held": "ACCEPTED", "done_for_day": "ACCEPTED", "accepted_for_bidding": "ACCEPTED",
                           "pending_new": "SUBMITTED", "pending_replace": "PENDING_UPDATE"}.get(row.get("status"), str(row.get("status", "")).upper())
        if expected_status == "PARTIALLY_FILLED" and row.get("native_replacement_quantity_binding") and Decimal(row["filled_qty"]) == offset:
            expected_status = "ACCEPTED"
        if row.get("status") == "done_for_day" and Decimal(row["filled_qty"]) > offset:
            expected_status = "PARTIALLY_FILLED"
        expected_tif = {"opg": "AT_THE_OPEN", "cls": "AT_THE_CLOSE"}.get(row.get("time_in_force"), str(row.get("time_in_force", "")).upper())
        if not reason:
            from .linked_orders import broker_session
            try:
                if package and "atomic_option_package" not in (native.get("tags") or []):
                    reason = "Native spread control marker differs"
                if row.get("asset_class") == "us_option" and not package and "option_intent:" + str(row.get("position_intent")) not in (native.get("tags") or []):
                    reason = "Native option intent differs from broker observation"
                if ("extended_hours" in (native.get("tags") or [])) != ((package["session"] if package else broker_session(row)) == "extended"):
                    reason = "Native session eligibility differs from broker observation"
            except ValueError as exc:
                reason = str(exc)
        authorized_pending, before = False, {}
        command = next((c for c in (commands or {}).values() if row["id"] in c.get("broker_order_ids", [])
                        and c.get("account_id") == broker_id and c.get("instrument_id") == expected_instrument
                        and c.get("native_client_order_id", c.get("client_order_id")) == (native or {}).get("client_order_id")), {})
        action = command.get("pending_action") or {}
        transition, event = action.get("native_transition") or {}, (native or {}).get("pending_event") or {}
        before = transition.get("before") or {}
        try:
            authorized_pending = bool(native_epoch and transition.get("native_epoch") == native_epoch and action.get("state") == "authorized"
                and action.get("actor") and action.get("broker_order_id") == row["id"]
                and action.get("kind") in {"replace", "cancel"} and event.get("id")
                and event.get("type") == ("OrderPendingUpdate" if action["kind"] == "replace" else "OrderPendingCancel")
                and native.get("status") == ("PENDING_UPDATE" if action["kind"] == "replace" else "PENDING_CANCEL")
                and before.get("status") == expected_status and expected_status in {"SUBMITTED", "ACCEPTED", "PARTIALLY_FILLED"}
                and event.get("prior_ids") == transition.get("event_ids")
                and int(event["ts_event"]) >= int(datetime.fromisoformat(action["intent_at"]).timestamp() * 1_000_000_000)
                and (not action.get("expires_at") or datetime.fromisoformat(action["expires_at"]) > datetime.now(UTC)))
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            authorized_pending = False
        if not reason and (native.get("side") != ("BUY" if package else row["side"].upper())
                           or native.get("type") != native_type(row["type"])
                           or native.get("status") != expected_status and not authorized_pending or native.get("time_in_force") != expected_tif):
            reason = "Native order side/type/status/TIF differs from broker observation"
        if not reason:
            if row.get("type") == "trailing_stop":
                try:
                    offset, unit = native_trail({"order_type": "TRAILING_STOP_MARKET", "quantity": row["qty"], "side": row["side"].upper(),
                        "time_in_force": row["time_in_force"].upper(), "trail_price": row.get("trail_price"), "trail_percent": row.get("trail_percent")})
                    if Decimal(str(native.get("trailing_offset"))) != offset or native.get("trailing_offset_type") != unit:
                        reason = "Native initial trailing distance differs from broker observation"
                    if (row.get("stop_price") is None) != (native.get("trigger_price") is None):
                        reason = "Native or broker current trailing trigger is unavailable"
                except (ValueError, TypeError, ArithmeticError):
                    reason = "Native or broker trailing distance is unavailable or unsupported"
            expected_price, actual_price = row.get("limit_price"), native.get("price")
            if (expected_price is None) != (actual_price is None):
                reason = "Native or broker order price is unavailable"
            elif expected_price is not None and Decimal(str(expected_price)) != Decimal(str(actual_price)):
                reason = "Native limit price differs from broker observation"
            if row.get("stop_price") is not None:
                if native.get("trigger_price") is None:
                    reason = "Native stop trigger is unavailable"
                elif Decimal(str(row["stop_price"])) != Decimal(str(native["trigger_price"])):
                    reason = "Native stop trigger differs from broker observation"
            if row.get("filled_avg_price") is not None:
                average = native.get("avg_px")
                if average is None or Decimal(str(average)) != Decimal(str(row["filled_avg_price"])):
                    cost_reason = "Reported native filled average price is unavailable or differs from broker observation"
        if cost_reason:
            reporting_gaps.append(row["id"] + ": " + cost_reason)
        row.update(source_import_error=source.get("import_error"), native_comparison_gap=reason, native_cost_comparison_gap=cost_reason,
                   reconciliation_status="incomplete" if reason else "reconciled",
                   import_error=reason, nautilus=native, management_supported=False)
        if authorized_pending and not reason:
            row["binding_native"] = before
        if reason:
            gaps.append(row["id"] + ": " + reason)
        orders.append(row)
    orders_reconciled = bool(observed.get("account_at")) and not observed.get("error") and not by_id and all(o["reconciliation_status"] == "reconciled" for o in orders)
    if by_id:
        gaps.append("Native open orders remain which the current broker response reports absent")
    broker_cash = (observed.get("account") or {}).get("cash")
    projection = observed.get("balance_projection")
    margin_basis = (native_balance or {}).get("account_type") == "MARGIN"
    if margin_basis:
        try:
            source, derived = projection["source_fields"], projection["derived"]
            if (projection["version"] != "alpaca-paper-equity-initial-v1" or projection["currency"] != "USD"
                    or projection["calculate_account_state"] is not False or native_balance["calculate_account_state"] is not False
                    or projection.get("source_receipt") != observed.get("source_receipts", {}).get("account")
                    or any(Decimal(str(source[key])) != Decimal(str(observed["account"][key])) for key in
                        ("cash", "equity", "initial_margin", "maintenance_margin", "options_buying_power"))
                    or Decimal(derived["total"]) != Decimal(str(source["equity"]))
                    or Decimal(derived["locked"]) != Decimal(str(source["initial_margin"]))
                    or Decimal(derived["free"]) != Decimal(str(source["equity"])) - Decimal(str(source["initial_margin"]))
                    or any(Decimal(str(native_balance[key])) != Decimal(derived[key]) for key in ("total", "locked", "free"))
                    or native_balance["currency"] != "USD"
                    or native_balance["reported_margin"]["currency"] != "USD" or projection["reported_margin"]["currency"] != "USD"
                    or Decimal(native_balance["reported_margin"]["initial"]) != Decimal(str(source["initial_margin"]))
                    or Decimal(native_balance["reported_margin"]["maintenance"]) != Decimal(str(source["maintenance_margin"]))
                    or Decimal(str(projection["reported_margin"]["initial"])) != Decimal(str(source["initial_margin"]))
                    or Decimal(str(projection["reported_margin"]["maintenance"])) != Decimal(str(source["maintenance_margin"]))):
                raise ValueError()
        except (ValueError, KeyError, TypeError, ArithmeticError):
            gaps.append("Native declared margin projection and actual same-receipt account facts are unavailable or differ")
    elif native_cash is None or broker_cash is None or Decimal(native_cash) != Decimal(broker_cash):
        gaps.append("Native cash and broker cash are unavailable or differ")
    if observed.get("error"):
        gaps.append(observed["error"])
    return {"status": "incomplete" if gaps else "reconciled", "gaps": list(dict.fromkeys(gaps)),
            "reporting_gaps": reporting_gaps,
            "cost_comparison_basis": "Exact reported decimal values; no tolerance or cost-agreement claim. Broker cost remains authoritative; cost discrepancies are separate from exact account, quantity and order checks.",
            "positions_reconciled": positions_reconciled, "orders_reconciled": orders_reconciled,
            "observed_at": observed.get("account_at"), **history_scope(observed),
            "positions": positions, "orders": orders,
            "unsupported_exposure": observed.get("unsupported_exposure"), "option_lifecycle": observed.get("option_lifecycle", []),
            "fills": observed.get("fills", []), "broker_cash": broker_cash, "native_cash": native_cash,
            "native_balance": native_balance, "balance_projection": projection,
            "balance_comparison_basis": "Declared equity/initial requirement projection; not cash or spendable funds" if margin_basis else "Existing native CASH versus actual broker cash",
            "market_value_basis": "Broker reported; no same-feed native valuation comparison is established",
            "scope": "Native account, quantity, declared balance and order comparison; reported cost discrepancies are separate. Market valuation and full fee history are not verified"}
