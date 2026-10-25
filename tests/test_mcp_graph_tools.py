"""Supplemental research tools travel through both analyst binding and execution."""

import unittest
from unittest.mock import patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from pydantic import Field

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import setup, trading_graph
from tradingagents.graph.analyst_execution import (
    ANALYST_NODE_SPECS,
    build_analyst_execution_plan,
)
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator


class ResearchProbeModel(BaseChatModel):
    bindings: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "supplemental-tool-probe"

    def bind_tools(self, tools, **kwargs):
        self.bindings.append(tuple(tools))
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            message = AIMessage(content=f"Research evidence: {messages[-1].content}")
        else:
            message = AIMessage(content="", tool_calls=[{
                "name": "maenifold_research", "args": {"query": "NVDA"}, "id": "research-1",
            }])
        return ChatResult(generations=[ChatGeneration(message=message)])


def research_tool(calls):
    def research(query: str) -> str:
        calls.append(query)
        return "verified research context"

    return StructuredTool.from_function(
        research, name="maenifold_research", description="Read research context."
    )


class SupplementalGraphToolsTests(unittest.TestCase):
    def test_setup_binds_and_executes_the_same_tools_for_each_analyst(self):
        calls = []
        extra = research_tool(calls)
        model = ResearchProbeModel()
        assembled = []
        original = setup._analyst_graph

        def capture(spec, agent, max_tool_rounds):
            graph = original(spec, agent, max_tool_rounds)
            assembled.append((spec, graph))
            return graph

        graph_setup = setup.GraphSetup(
            model, model, ConditionalLogic(), max_tool_rounds=3, supplemental_tools=[extra]
        )
        with patch.object(setup, "_analyst_graph", side_effect=capture):
            graph_setup.setup_graph(["market", "news", "fundamentals"])

        state = Propagator().create_initial_state("NVDA", "2026-01-09")
        for spec, graph in assembled:
            with self.subTest(analyst=spec.key):
                result = graph.invoke(state)
                self.assertIn("verified research context", result[spec.report_key])
                self.assertEqual(model.bindings[-1], spec.tools)
                self.assertEqual(spec.tools[:-1], ANALYST_NODE_SPECS[spec.key].tools)
                self.assertIs(spec.tools[-1], extra)
        self.assertEqual(calls, ["NVDA", "NVDA", "NVDA"])

    def test_default_plan_is_unchanged_and_native_tool_objects_are_preserved(self):
        for spec in build_analyst_execution_plan(ANALYST_NODE_SPECS).specs:
            self.assertIs(spec, ANALYST_NODE_SPECS[spec.key])

    def test_sentiment_retains_its_existing_direct_fetch_flow(self):
        spec = build_analyst_execution_plan(["social"], [research_tool([])]).specs[0]
        self.assertEqual(spec.tools, ())

    def test_duplicate_supplemental_names_are_rejected(self):
        extra = research_tool([])
        with self.assertRaisesRegex(ValueError, "unique names"):
            build_analyst_execution_plan(["market"], [extra, extra])

    def test_supplemental_tools_cannot_replace_any_native_tool(self):
        native = ANALYST_NODE_SPECS["market"].tools[0]
        with self.assertRaisesRegex(ValueError, "distinct from native"):
            build_analyst_execution_plan(["news"], [native])

    def test_graph_forwards_supplemental_tools(self):
        extra = research_tool([])
        with patch.object(trading_graph, "create_tier_client"), \
                patch.object(trading_graph, "TradingMemoryLog"), \
                patch.object(trading_graph.os, "makedirs"), \
                patch.object(trading_graph, "GraphSetup") as graph_setup:
            graph = trading_graph.TradingAgentsGraph(
                selected_analysts=["market"], config=dict(DEFAULT_CONFIG), supplemental_tools=[extra]
            )
        self.assertEqual(graph_setup.call_args.kwargs["supplemental_tools"], (extra,))


if __name__ == "__main__":
    unittest.main()
