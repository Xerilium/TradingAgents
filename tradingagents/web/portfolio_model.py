"""One joint, advisory allocation from saved research and dated reference prices."""

import json
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, create_model

from tradingagents.default_config import build_default_config
from tradingagents.llm_clients.factory import create_tier_client
from tradingagents.workflows import WorkflowBundle, bundled_files


class Allocation(BaseModel):
    symbol: str
    weight: Decimal = Field()
    rationale: str = Field()
    entry_conditions: str = Field()


class JointPortfolio(BaseModel):
    allocations: list[Allocation] = Field()
    cash_rationale: str = Field()


def capital_amount(value):
    if isinstance(value, bool):
        raise ValueError("Model capital must be a positive finite amount")
    try:
        amount = Decimal(str(value))
        valid = amount.is_finite() and amount > 0 and amount == amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        valid = False
    if not valid:
        raise ValueError("Model capital must be positive, finite and expressed in cents")
    return amount


def model_portfolio(config, inputs, capital, workflow=None):
    workflow = workflow or WorkflowBundle.from_files(bundled_files())
    allocation_schema = create_model(
        "Allocation", __base__=Allocation,
        weight=(Decimal, Field(description=workflow.text("allocation_weight"))),
        rationale=(str, Field(description=workflow.text("allocation_rationale"))),
        entry_conditions=(str, Field(description=workflow.text("allocation_entry_conditions"))),
    )
    portfolio_schema = create_model(
        "JointPortfolio", __base__=JointPortfolio,
        allocations=(list[allocation_schema], Field(description=workflow.text("joint_allocations"))),
        cash_rationale=(str, Field(description=workflow.text("joint_cash_rationale"))),
    )
    evidence = json.dumps({"model_capital": str(capital), "starting_model_holdings": [],
                           "eligible_research": inputs}, ensure_ascii=False)
    if len(evidence) > 120_000:
        raise ValueError("Saved evidence exceeds the joint synthesis limit of 120,000 characters; no model call made and no candidates truncated")
    settings = {**build_default_config(), **config, "deep_think_provider": config["llm_provider"],
                "deep_think_backend_url": config.get("backend_url")}
    client = create_tier_client(settings, "deep")
    response = client.get_llm().with_structured_output(portfolio_schema, include_raw=True).invoke([
        SystemMessage(content=(
            workflow.text("joint_portfolio"))),
        HumanMessage(content=evidence),
    ])
    if response.get("parsing_error") or not isinstance(response.get("parsed"), portfolio_schema):
        raise ValueError(f"Joint portfolio structured response failed: {response.get('parsing_error') or 'missing allocation'}")
    proposed = response["parsed"]
    prices = {row["symbol"]: Decimal(str(row["reference"]["price"])) for row in inputs}
    seen, rows, total_weight, spent = set(), [], Decimal(0), Decimal(0)
    for allocation in proposed.allocations:
        symbol, weight = allocation.symbol, allocation.weight
        if symbol not in prices or symbol in seen:
            raise ValueError(f"Unknown or duplicate portfolio symbol: {symbol}")
        if not weight.is_finite() or weight < 0 or weight > 1:
            raise ValueError(f"Invalid allocation weight for {symbol}")
        if not allocation.rationale.strip() or not allocation.entry_conditions.strip():
            raise ValueError(f"Missing rationale or entry conditions for {symbol}")
        seen.add(symbol)
        total_weight += weight
        quantity = int((capital * weight / prices[symbol]).to_integral_value(rounding=ROUND_DOWN))
        value = quantity * prices[symbol]
        spent += value
        rows.append({**allocation.model_dump(mode="json"), "shares": quantity,
                     "reference_value": str(value), "reference": next(r["reference"] for r in inputs if r["symbol"] == symbol)})
    if seen != set(prices) or total_weight > 1 or spent > capital:
        raise ValueError("Joint allocation omitted symbols, exceeded 100% weights or exceeded model capital")
    if not proposed.cash_rationale.strip():
        raise ValueError("Joint allocation omitted the cash rationale")
    return {"allocations": rows, "capital": str(capital), "reference_value": str(spent),
            "cash": str(capital - spent), "target_cash_weight": str(1 - total_weight),
            "cash_rationale": proposed.cash_rationale, "provider": client.get_provider_name(),
            "model": client.model, "response_metadata": getattr(response.get("raw"), "response_metadata", {})}
