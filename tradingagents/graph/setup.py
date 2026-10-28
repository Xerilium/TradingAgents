import logging
from collections import Counter
from collections.abc import Iterable
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import (
    create_aggressive_debator,
    create_bear_researcher,
    create_bull_researcher,
    create_conservative_debator,
    create_fundamentals_analyst,
    create_market_analyst,
    create_neutral_debator,
    create_news_analyst,
    create_portfolio_manager,
    create_research_manager,
    create_sentiment_analyst,
    create_trader,
)
from tradingagents.agents.state import AgentState

from .analyst_execution import build_analyst_execution_plan
from .conditional_logic import ConditionalLogic

logger = logging.getLogger(__name__)

# Every target a shared conditional router can return. Each edge driven by the
# router maps all of them, so a fall-through return (e.g. under prompt/i18n/
# refactor drift in the speaker labels) can never hit a missing path_map entry
# and crash LangGraph mid-run (#1088).
DEBATE_PATH_MAP = {
    "Bull Researcher": "Bull Researcher",
    "Bear Researcher": "Bear Researcher",
    "Research Manager": "Research Manager",
}
RISK_ANALYSIS_PATH_MAP = {
    "Aggressive Analyst": "Aggressive Analyst",
    "Conservative Analyst": "Conservative Analyst",
    "Neutral Analyst": "Neutral Analyst",
    "Portfolio Manager": "Portfolio Manager",
}


def _tools_or_done(state) -> str:
    """Route an analyst's turn: run its tool calls, or finish with its report."""
    return "tools" if state["messages"][-1].tool_calls else END


def _analyst_graph(spec, agent, max_tool_rounds: int, workflow):
    """One analyst as a graph of its own: the model and its tools, on a private message history.

    It exports its report and, for the market analyst, its verified snapshot.
    Its tool calls never reach the other analysts' private messages. After
    ``max_tool_rounds`` rounds of tool calls it is told to write its report, and
    that turn ends it whatever it answers, so a model that keeps calling tools
    cannot run the graph into its recursion limit (#1420).
    """
    outputs = {spec.report_key: str}
    if spec.key == "market":
        outputs["verified_market_snapshot"] = str
    output = TypedDict(f"{spec.key.capitalize()}Report", outputs)
    graph = StateGraph(AgentState, output_schema=output)
    graph.add_node("agent", agent)
    graph.add_edge(START, "agent")
    if not spec.tools:
        graph.add_edge("agent", END)
        return graph.compile()

    def calls(messages):
        return [call["name"] for m in messages for call in (getattr(m, "tool_calls", None) or [])]

    def rounds(messages) -> int:
        return sum(1 for m in messages if getattr(m, "tool_calls", None)
                   and not str(getattr(m, "id", "")).startswith("required-"))

    def more_or_wrap_up(state) -> str:
        return "wrap_up" if rounds(state["messages"]) >= max_tool_rounds else "agent"

    def wrap_up(state):
        repeated = ", ".join(f"{name} x{n}" for name, n in Counter(calls(state["messages"])).most_common())
        logger.warning("%s used its %d tool rounds (%s); asking for its report",
                       spec.agent_node, max_tool_rounds, repeated)
        return agent({**state, "messages": [*state["messages"], HumanMessage(workflow.text("wrap_up"))]})

    graph.add_node("tools", ToolNode(list(spec.tools), handle_tool_errors=True))
    graph.add_node("wrap_up", wrap_up)
    graph.add_conditional_edges("agent", _tools_or_done, ["tools", END])
    graph.add_conditional_edges("tools", more_or_wrap_up, ["agent", "wrap_up"])
    graph.add_edge("wrap_up", END)
    return graph.compile()


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        conditional_logic: ConditionalLogic,
        max_tool_rounds: int,
        supplemental_tools: Iterable[BaseTool] | None = None,
        social_screen_factory=None,
        exclude_fred=False,
        workflow=None,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.conditional_logic = conditional_logic
        self.max_tool_rounds = max_tool_rounds
        self.supplemental_tools = tuple(supplemental_tools or ())
        self.social_screen_factory = social_screen_factory
        self.exclude_fred = exclude_fred
        self.bundle = workflow

    def setup_graph(
        self, selected_analysts=("market", "social", "news", "fundamentals"), memory_node=None
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Sentiment analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
            memory_node: Node that settles past decisions and returns the run's
                ``past_context``. It runs alongside the analysts.
        """
        plan = build_analyst_execution_plan(selected_analysts, self.supplemental_tools)
        if self.exclude_fred:
            from dataclasses import replace
            plan = replace(plan, specs=[replace(spec, tools=tuple(t for t in spec.tools if t.name != "get_macro_indicators")) for spec in plan.specs])

        definition = self.bundle.definition
        tiers = {"fast": self.quick_thinking_llm, "deep": self.deep_thinking_llm}
        specs = {spec.key: spec for spec in plan.specs}
        factories = {
            "market": lambda llm, spec: create_market_analyst(llm, tools=spec.tools, workflow=self.bundle),
            "social": lambda llm, spec: create_sentiment_analyst(llm, screen_factory=self.social_screen_factory, workflow=self.bundle),
            "news": lambda llm, spec: create_news_analyst(llm, tools=spec.tools, workflow=self.bundle),
            "fundamentals": lambda llm, spec: create_fundamentals_analyst(llm, tools=spec.tools, workflow=self.bundle),
            "bull": lambda llm, _: create_bull_researcher(llm, workflow=self.bundle),
            "bear": lambda llm, _: create_bear_researcher(llm, workflow=self.bundle),
            "research_manager": lambda llm, _: create_research_manager(llm, workflow=self.bundle),
            "trader": lambda llm, _: create_trader(llm, workflow=self.bundle),
            "aggressive": lambda llm, _: create_aggressive_debator(llm, workflow=self.bundle),
            "conservative": lambda llm, _: create_conservative_debator(llm, workflow=self.bundle),
            "neutral": lambda llm, _: create_neutral_debator(llm, workflow=self.bundle),
            "portfolio_manager": lambda llm, _: create_portfolio_manager(llm, workflow=self.bundle),
        }
        workflow = StateGraph(AgentState)
        active = set()
        for name, node in definition["nodes"].items():
            handler = node["handler"]
            if handler in {"market", "social", "news", "fundamentals"} and handler not in specs:
                continue
            if handler == "memory":
                if memory_node is None:
                    continue
                agent = memory_node
            else:
                spec = specs.get(handler)
                agent = factories[handler](tiers[node["tier"]], spec)
                if spec is not None:
                    agent = _analyst_graph(spec, agent, self.max_tool_rounds, self.bundle)
            workflow.add_node(name, agent)
            active.add(name)

        routers = {"research_debate": self.conditional_logic.should_continue_debate,
                   "risk_debate": self.conditional_logic.should_continue_risk_analysis}
        for edge in definition["edges"]:
            origin = edge["from"]
            if isinstance(origin, list):
                origin = [name for name in origin if name in active]
                if not origin:
                    continue
            elif origin != "START" and origin not in active:
                continue
            origin = START if origin == "START" else origin
            if "router" in edge:
                workflow.add_conditional_edges(origin, routers[edge["router"]], {
                    outcome: END if target == "END" else target for outcome, target in edge["paths"].items()
                })
            else:
                target = edge["to"]
                if target not in active and target != "END":
                    continue
                workflow.add_edge(origin, END if target == "END" else target)

        return workflow
