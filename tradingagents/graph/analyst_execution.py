from collections.abc import Iterable
from dataclasses import dataclass, replace

from langchain_core.tools import BaseTool

from tradingagents.agents.analysts import fundamentals_analyst, market_analyst, news_analyst


@dataclass(frozen=True)
class AnalystNodeSpec:
    key: str
    agent_node: str
    report_key: str
    tools: tuple = ()


@dataclass(frozen=True)
class AnalystExecutionPlan:
    specs: list[AnalystNodeSpec]


ANALYST_NODE_SPECS: dict[str, AnalystNodeSpec] = {
    "market": AnalystNodeSpec(
        key="market",
        agent_node="Market Analyst",
        report_key="market_report",
        tools=market_analyst.TOOLS,
    ),
    "social": AnalystNodeSpec(
        # Saved configs select this analyst as "social". It fetches its
        # sources before calling the model, so it has no tools.
        key="social",
        agent_node="Sentiment Analyst",
        report_key="sentiment_report",
    ),
    "news": AnalystNodeSpec(
        key="news",
        agent_node="News Analyst",
        report_key="news_report",
        tools=news_analyst.TOOLS,
    ),
    "fundamentals": AnalystNodeSpec(
        key="fundamentals",
        agent_node="Fundamentals Analyst",
        report_key="fundamentals_report",
        tools=fundamentals_analyst.TOOLS,
    ),
}


def build_analyst_execution_plan(
    selected_analysts: Iterable[str],
    supplemental_tools: Iterable[BaseTool] | None = None,
) -> AnalystExecutionPlan:
    """Use the same native and supplemental tools for model binding and execution.

    Supplemental tools are for research. The caller is responsible for keeping
    broker mutations out of this collection. Native tools retain their injected
    symbol and date parameters; supplements cannot replace them by name.
    """
    extras = tuple(supplemental_tools or ())
    names = [tool.name for tool in extras]
    native_names = {tool.name for spec in ANALYST_NODE_SPECS.values() for tool in spec.tools}
    if len(names) != len(set(names)) or native_names.intersection(names):
        raise ValueError("supplemental tools must have unique names distinct from native tools")
    specs: list[AnalystNodeSpec] = []
    for analyst_key in selected_analysts:
        spec = ANALYST_NODE_SPECS.get(analyst_key)
        if spec is None:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        specs.append(replace(spec, tools=(*spec.tools, *extras)) if spec.tools and extras else spec)

    if not specs:
        raise ValueError("at least one analyst must be selected")

    return AnalystExecutionPlan(specs=specs)


