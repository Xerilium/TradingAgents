"""Validated, run-local definitions for the existing LangGraph research handlers."""

from copy import deepcopy
from importlib.resources import files as package_files
from pathlib import PurePosixPath
from string import Formatter

import yaml


class _UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    "mapping keys must be scalar", key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    f"duplicate key {key!r}", key_node.start_mark,
                )
            result[key] = self.construct_object(value_node, deep=deep)
        return result


ANALYSTS = {"market", "social", "news", "fundamentals"}
HANDLERS = {"market", "social", "news", "fundamentals", "memory", "bull", "bear",
            "research_manager", "trader", "aggressive", "conservative", "neutral", "portfolio_manager"}
# Each prompt key has a fixed set of runtime bindings. Editable YAML cannot
# expand these bindings; the corresponding handler supplies them in code.
PROMPT_VARIABLES = {
    'aggressive_debator': frozenset(('evidence_conservative_analyst_latest_argument', 'evidence_debate_history', 'evidence_fundamentals_report', 'evidence_market_research_report', 'evidence_neutral_analyst_latest_argument', 'evidence_news_report', 'evidence_sentiment_report', 'evidence_trader_investment_plan', 'get_verified_market_context_from_state', 'instrument_context', 'portfolio_context')),
    'allocation_entry_conditions': frozenset(()),
    'allocation_rationale': frozenset(()),
    'allocation_weight': frozenset(()),
    'analyst_wrapper': frozenset(('current_date', 'instrument_context', 'system_message', 'tool_names')),
    'bear_researcher': frozenset(('evidence_debate_history', 'evidence_fundamentals_report', 'evidence_market_research_report', 'evidence_news_report', 'evidence_opposing_analyst_latest_argument', 'evidence_sentiment_report', 'fundamentals_label', 'get_verified_market_context_from_state', 'instrument_context', 'target_label', 'target_label_2')),
    'bull_researcher': frozenset(('evidence_debate_history', 'evidence_fundamentals_report', 'evidence_market_research_report', 'evidence_news_report', 'evidence_opposing_analyst_latest_argument', 'evidence_sentiment_report', 'fundamentals_label', 'get_verified_market_context_from_state', 'instrument_context', 'target_label')),
    'conservative_debator': frozenset(('evidence_aggressive_analyst_latest_argument', 'evidence_debate_history', 'evidence_fundamentals_report', 'evidence_market_research_report', 'evidence_neutral_analyst_latest_argument', 'evidence_news_report', 'evidence_sentiment_report', 'evidence_trader_investment_plan', 'get_verified_market_context_from_state', 'instrument_context', 'portfolio_context')),
    'desk_exclude_fred': frozenset(()),
    'desk_execution_policy': frozenset(()),
    'desk_historical_quote': frozenset(()),
    'desk_quote_context': frozenset(('observation',)),
    'fundamentals_analyst': frozenset(('get_language_instruction', 'research_memory_guidance')),
    'fundamentals_analyst_etf': frozenset(('get_language_instruction', 'research_memory_guidance')),
    'fundamentals_review_etf': frozenset(()),
    'fundamentals_review_tools': frozenset(()),
    'fundamentals_review_stock': frozenset(()),
    'joint_allocations': frozenset(()),
    'joint_cash_rationale': frozenset(()),
    'joint_portfolio': frozenset(()),
    'market_analyst': frozenset(('get_language_instruction', 'research_memory_guidance')),
    'neutral_debator': frozenset(('evidence_aggressive_analyst_latest_argument', 'evidence_conservative_analyst_latest_argument', 'evidence_debate_history', 'evidence_fundamentals_report', 'evidence_market_research_report', 'evidence_news_report', 'evidence_sentiment_report', 'evidence_trader_investment_plan', 'get_verified_market_context_from_state', 'instrument_context', 'portfolio_context')),
    'news_analyst': frozenset(('asset_label', 'get_language_instruction', 'research_memory_guidance')),
    'no_external_tools': frozenset(()),
    'portfolio_lessons': frozenset(('evidence',)),
    'portfolio_manager': frozenset(('NO_EXTERNAL_TOOLS', 'evidence_debate_history', 'evidence_research_manager_investment_plan', 'evidence_trader_transaction_proposal', 'get_language_instruction', 'get_verified_market_context_from_state', 'instrument_context', 'lessons_line', 'portfolio_context')),
    'portfolio_manager_desk': frozenset(('NO_EXTERNAL_TOOLS', 'evidence_debate_history', 'evidence_research_manager_investment_plan', 'evidence_trader_transaction_proposal', 'get_language_instruction', 'get_verified_market_context_from_state', 'instrument_context', 'lessons_line', 'portfolio_context')),
    'research_manager': frozenset(('NO_EXTERNAL_TOOLS', 'evidence_debate_history', 'get_portfolio_context_from_state', 'get_verified_market_context_from_state', 'instrument_context', 'policy')),
    'research_manager_desk': frozenset(('NO_EXTERNAL_TOOLS', 'evidence_debate_history', 'get_portfolio_context_from_state', 'get_verified_market_context_from_state', 'instrument_context', 'policy')),
    'schema_DeskPortfolioDecision_executive_summary': frozenset(()),
    'schema_DeskPortfolioDecision_rating': frozenset(()),
    'schema_DeskResearchPlan_recommendation': frozenset(()),
    'schema_DeskResearchPlan_strategic_actions': frozenset(()),
    'schema_DeskTraderProposal_position_sizing': frozenset(()),
    'schema_PortfolioDecision_executive_summary': frozenset(()),
    'schema_PortfolioDecision_investment_thesis': frozenset(()),
    'schema_PortfolioDecision_price_target': frozenset(()),
    'schema_PortfolioDecision_rating': frozenset(()),
    'schema_PortfolioDecision_time_horizon': frozenset(()),
    'schema_ResearchPlan_rationale': frozenset(()),
    'schema_ResearchPlan_recommendation': frozenset(()),
    'schema_ResearchPlan_strategic_actions': frozenset(()),
    'schema_SentimentReport_confidence': frozenset(()),
    'schema_SentimentReport_narrative': frozenset(()),
    'schema_SentimentReport_overall_band': frozenset(()),
    'schema_SentimentReport_overall_score': frozenset(()),
    'schema_TraderProposal_action': frozenset(()),
    'schema_TraderProposal_entry_price': frozenset(()),
    'schema_TraderProposal_position_sizing': frozenset(()),
    'schema_TraderProposal_reasoning': frozenset(()),
    'schema_TraderProposal_stop_loss': frozenset(()),
    'sentiment_analyst': frozenset(('character', 'end_date', 'get_language_instruction', 'news_block', 'reddit_block', 'start_date', 'stocktwits_block', 'ticker', 'value')),
    'sentiment_reddit_crypto': frozenset(()),
    'sentiment_reddit_crypto_specific': frozenset(('subreddit',)),
    'sentiment_reddit_stock': frozenset(()),
    'sentiment_wrapper': frozenset(('NO_EXTERNAL_TOOLS', 'current_date', 'instrument_context', 'system_message')),
    'shared_called_tools': frozenset(('calls', 'said')),
    'shared_crypto': frozenset(()),
    'shared_duplicate_filing': frozenset(('digest', 'response_id')),
    'shared_etf': frozenset(()),
    'shared_evidence_reference': frozenset(('label',)),
    'shared_evidence_wrapper': frozenset(('label', 'text')),
    'shared_historical_identity': frozenset(('label', 'name', 'trade_date')),
    'shared_instrument': frozenset(('instrument_label', 'ticker')),
    'shared_language': frozenset(('lang',)),
    'shared_memory_base': frozenset(()),
    'shared_memory_build_context': frozenset(()),
    'shared_memory_final': frozenset(()),
    'shared_memory_find_similar': frozenset(()),
    'shared_memory_no_graph': frozenset(()),
    'shared_memory_read': frozenset(()),
    'shared_memory_search': frozenset(()),
    'shared_memory_thinking': frozenset(()),
    'shared_memory_tool_instruction': frozenset(('instruction', 'name')),
    'shared_memory_tools': frozenset(()),
    'shared_memory_unavailable': frozenset(()),
    'shared_opponent_opening': frozenset(('opponent',)),
    'shared_portfolio_holdings_missing': frozenset(()),
    'shared_portfolio_missing': frozenset(()),
    'shared_report_absent': frozenset(('source',)),
    'shared_request_inputs': frozenset(()),
    'shared_resolved_identity': frozenset(('details',)),
    'shared_snapshot': frozenset(('digest',)),
    'shared_snapshot_missing': frozenset(()),
    'shared_tool_returned': frozenset(('name', 'response_id')),
    'shared_tools_spent': frozenset(()),
    'trader_grounding': frozenset(()),
    'trader_grounding_desk': frozenset(()),
    'trader_report_section': frozenset(('evidence',)),
    'trader_system': frozenset(('NO_EXTERNAL_TOOLS', 'get_language_instruction', 'grounding')),
    'trader_system_desk': frozenset(('NO_EXTERNAL_TOOLS', 'get_language_instruction', 'grounding')),
    'trader_user': frozenset(('company_name', 'evidence_research_investment_plan', 'get_verified_market_context_from_state', 'instrument_context', 'portfolio_context', 'report_section')),
    'trader_user_desk': frozenset(('company_name', 'evidence_research_investment_plan', 'get_verified_market_context_from_state', 'instrument_context', 'portfolio_context', 'report_section')),
    'wrap_up': frozenset(()),
}


def bundled_files():
    root = package_files("tradingagents").joinpath("workflow_assets")
    def collect(folder, prefix=""):
        result = {}
        for item in folder.iterdir():
            name = f"{prefix}{item.name}"
            if item.is_dir():
                result.update(collect(item, name + "/"))
            elif item.is_file():
                result[name] = item.read_text(encoding="utf-8")
        return result
    return collect(root)


def _path(value):
    if not isinstance(value, str) or "\\" in value:
        raise ValueError(f"workflow.yaml: invalid prompt path {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or not value or any(p in (".", "..") for p in value.split("/")) or ":" in value:
        raise ValueError(f"workflow.yaml: invalid prompt path {value!r}")
    return value


class WorkflowBundle:
    """Immutable snapshot of a validated workflow and every referenced prompt."""

    def __init__(self, source, definition):
        self._files = dict(source)
        self._definition = deepcopy(definition)

    @property
    def definition(self):
        return deepcopy(self._definition)

    @property
    def files(self):
        return dict(self._files)

    @classmethod
    def from_files(cls, source):
        if not isinstance(source, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in source.items()):
            raise ValueError("Workflow files must be a mapping of file names to text")
        for name in source:
            _path(name)
        if "workflow.yaml" not in source:
            raise ValueError("workflow.yaml: file is missing")
        try:
            definition = yaml.load(source["workflow.yaml"], Loader=_UniqueSafeLoader)
        except yaml.YAMLError as exc:
            raise ValueError(f"workflow.yaml: {exc}") from exc
        if not isinstance(definition, dict):
            raise ValueError("workflow.yaml: expected a mapping")
        analysts = definition.get("analysts")
        if not isinstance(analysts, list) or not analysts or any(not isinstance(a, str) or a not in ANALYSTS for a in analysts) or len(set(analysts)) != len(analysts):
            raise ValueError("workflow.yaml: analysts must be a nonempty list of unique known analysts")
        limits = definition.get("limits")
        if not isinstance(limits, dict):
            raise ValueError("workflow.yaml: limits must be a mapping")
        for name in ("max_debate_rounds", "max_risk_discuss_rounds", "max_tool_rounds", "max_recur_limit"):
            if type(limits.get(name)) is not int or limits[name] < 1:
                raise ValueError(f"workflow.yaml: limits.{name} must be a positive integer")
        if 2 * limits["max_tool_rounds"] + 2 >= limits["max_recur_limit"]:
            raise ValueError("workflow.yaml: max_recur_limit must exceed twice max_tool_rounds plus two")
        nodes = definition.get("nodes")
        if not isinstance(nodes, dict) or not nodes:
            raise ValueError("workflow.yaml: nodes must be a nonempty mapping")
        handlers = []
        for name, node in nodes.items():
            if not isinstance(name, str) or name in ("START", "END", "__start__", "__end__") or not isinstance(node, dict) or not isinstance(node.get("handler"), str) or node.get("handler") not in HANDLERS:
                raise ValueError(f"workflow.yaml: unknown handler for node {name!r}")
            if node["handler"] != "memory" and node.get("tier") not in ("fast", "deep"):
                raise ValueError(f"workflow.yaml: node {name!r} needs tier fast or deep")
            handlers.append(node["handler"])
        if set(handlers) != HANDLERS or len(handlers) != len(HANDLERS):
            raise ValueError("workflow.yaml: each registered handler must appear exactly once")
        edges = definition.get("edges")
        if not isinstance(edges, list) or not edges:
            raise ValueError("workflow.yaml: edges must be a nonempty list")
        routing = {}
        direct_edges = set()
        for edge in edges:
            if not isinstance(edge, dict) or set(edge) - {"from", "to", "router", "paths"}:
                raise ValueError("workflow.yaml: invalid edge")
            origins = edge.get("from")
            origins = origins if isinstance(origins, list) else [origins]
            if not origins or any(not isinstance(n, str) or (n not in nodes and n != "START") for n in origins):
                raise ValueError(f"workflow.yaml: invalid edge origin {origins!r}")
            if len(set(origins)) != len(origins) or (len(origins) > 1 and "START" in origins):
                raise ValueError("workflow.yaml: invalid join origins")
            if "router" in edge:
                if "to" in edge:
                    raise ValueError("workflow.yaml: a conditional edge cannot also have a direct destination")
                if len(origins) != 1 or not isinstance(edge["router"], str) or edge["router"] not in ("research_debate", "risk_debate") or not isinstance(edge.get("paths"), dict):
                    raise ValueError("workflow.yaml: invalid conditional edge")
                expected = ({"Bull Researcher", "Bear Researcher", "Research Manager"} if edge["router"] == "research_debate" else
                            {"Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"})
                if set(edge["paths"]) != expected or any(not isinstance(n, str) or n not in nodes for n in edge["paths"].values()):
                    raise ValueError("workflow.yaml: conditional paths must map every router outcome to a known node")
                expected_handlers = ({"Bull Researcher": "bull", "Bear Researcher": "bear", "Research Manager": "research_manager"}
                                     if edge["router"] == "research_debate" else
                                     {"Aggressive Analyst": "aggressive", "Conservative Analyst": "conservative",
                                      "Neutral Analyst": "neutral", "Portfolio Manager": "portfolio_manager"})
                allowed_origins = {"bull", "bear"} if edge["router"] == "research_debate" else {"aggressive", "conservative", "neutral"}
                if origins[0] not in nodes or nodes[origins[0]]["handler"] not in allowed_origins or any(
                    nodes[target]["handler"] != expected_handlers[outcome] for outcome, target in edge["paths"].items()
                ):
                    raise ValueError("workflow.yaml: debate routers must use their registered participants and termination handler")
            elif "paths" in edge or not isinstance(edge.get("to"), str) or (edge.get("to") not in nodes and edge.get("to") != "END"):
                raise ValueError(f"workflow.yaml: invalid edge destination {edge.get('to')!r}")
            if "router" not in edge:
                target = edge["to"]
                identity = (tuple(sorted(origins)), target)
                if identity in direct_edges:
                    raise ValueError("workflow.yaml: duplicate direct edge")
                direct_edges.add(identity)
                if "START" in origins and target != "END" and nodes[target]["handler"] not in ANALYSTS | {"memory"}:
                    raise ValueError(f"workflow.yaml: {target} cannot start before research inputs")
                if target != "END":
                    handler = nodes[target]["handler"]
                    if handler in {"research_manager", "portfolio_manager"}:
                        raise ValueError(f"workflow.yaml: {target} must be reached by its debate router")
                    if handler == "trader" and (len(origins) != 1 or origins[0] not in nodes or nodes[origins[0]]["handler"] != "research_manager"):
                        raise ValueError("workflow.yaml: Trader requires the Research Manager's plan")
            for origin in origins:
                kind = "conditional" if "router" in edge else "direct"
                previous = routing.setdefault(origin, set())
                if previous and (kind == "conditional" or "conditional" in previous):
                    raise ValueError(f"workflow.yaml: ambiguous routing from {origin}")
                previous.add(kind)
        # Existing handlers consume state produced by specific stages. The
        # graph may select either initial debate speaker, but cannot bypass a
        # join, start a second debate branch, or invoke a stage twice.
        by_handler = {node["handler"]: name for name, node in nodes.items()}
        branches = {by_handler[h] for h in ANALYSTS | {"memory"}}
        starts = set()
        joins = []
        manager_edges = []
        risk_entries = []
        finish_edges = []
        routers_seen = set()
        for edge in edges:
            origins = edge["from"] if isinstance(edge["from"], list) else [edge["from"]]
            if "router" in edge:
                routers_seen.add(nodes[origins[0]]["handler"])
                continue
            target = edge["to"]
            if origins == ["START"] and target in branches:
                starts.add(target)
            elif set(origins) == branches and target in {by_handler["bull"], by_handler["bear"]}:
                joins.append(target)
            elif origins == [by_handler["research_manager"]] and target == by_handler["trader"]:
                manager_edges.append(target)
            elif origins == [by_handler["trader"]] and target in {by_handler["aggressive"], by_handler["conservative"], by_handler["neutral"]}:
                risk_entries.append(target)
            elif origins == [by_handler["portfolio_manager"]] and target == "END":
                finish_edges.append(target)
            else:
                raise ValueError("workflow.yaml: connection bypasses a required research stage or debate join")
        if starts != branches or len(joins) != 1 or len(manager_edges) != 1 or len(risk_entries) != 1 or len(finish_edges) != 1:
            raise ValueError("workflow.yaml: each analyst branch and required stage needs one connection")
        if routers_seen != {"bull", "bear", "aggressive", "conservative", "neutral"}:
            raise ValueError("workflow.yaml: each debate participant needs its bounded router")
        # Validate the active graph without constructing or executing it. Memory
        # is optional in the desk, so validate both forms of the graph.
        for include_memory in (False, True):
            active = {name for name, node in nodes.items()
                      if (node["handler"] not in ANALYSTS or node["handler"] in analysts)
                      and (node["handler"] != "memory" or include_memory)}
            adjacency = {name: set() for name in active | {"START", "END"}}
            unconditional = {name: set() for name in adjacency}
            outgoing = set()
            for edge in edges:
                origins = edge["from"] if isinstance(edge["from"], list) else [edge["from"]]
                origins = [name for name in origins if name == "START" or name in active]
                if not origins:
                    continue
                targets = list(edge["paths"].values()) if "router" in edge else [edge["to"]]
                targets = [target for target in targets if target == "END" or target in active]
                if not targets:
                    continue
                for origin in origins:
                    if "router" in edge and origin in outgoing:
                        raise ValueError(f"workflow.yaml: duplicate routing from {origin}")
                    adjacency[origin].update(targets)
                    if "router" not in edge:
                        unconditional[origin].update(targets)
                    outgoing.add(origin)
            def reachable(start, graph):
                seen, pending = set(), [start]
                while pending:
                    node = pending.pop()
                    if node not in seen:
                        seen.add(node)
                        pending.extend(graph[node] - seen)
                return seen
            def check_cycles(node, visiting, complete):
                if node in visiting:
                    raise ValueError("workflow.yaml: unconditional edges cannot form a cycle")
                if node in complete:
                    return
                visiting.add(node)
                for target in unconditional[node]:
                    check_cycles(target, visiting, complete)
                visiting.remove(node)
                complete.add(node)
            complete = set()
            for node in unconditional:
                check_cycles(node, set(), complete)
            reverse = {name: set() for name in adjacency}
            for origin, targets in adjacency.items():
                for target in targets:
                    reverse[target].add(origin)
            if not active <= reachable("START", adjacency) or not active <= reachable("END", reverse):
                raise ValueError("workflow.yaml: every enabled node must be reachable from START and able to reach END")
        prompts = definition.get("prompts")
        if not isinstance(prompts, dict) or set(prompts) != set(PROMPT_VARIABLES):
            raise ValueError("workflow.yaml: prompts must contain every registered prompt key")
        for key, ref in prompts.items():
            ref = _path(ref)
            if ref not in source:
                raise ValueError(f"{ref}: referenced prompt file is missing")
            try:
                fields = {field for _, field, _, _ in Formatter().parse(source[ref]) if field is not None}
                for _, field, spec, conversion in Formatter().parse(source[ref]):
                    if field is not None and (not field.isidentifier() or spec or conversion):
                        raise ValueError(f"{ref}: only simple named placeholders are supported")
            except ValueError as exc:
                raise ValueError(f"{ref}: invalid template: {exc}") from exc
            unknown = fields - PROMPT_VARIABLES[key]
            if unknown:
                raise ValueError(f"{ref}: unsupported variables: {', '.join(sorted(unknown))}")
        return cls(source, definition)

    def render(self, key, **variables):
        ref = self._definition["prompts"][key]
        try:
            return self._files[ref].format(**variables)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{ref}: cannot render prompt: {exc}") from exc

    def template(self, key):
        """Return a validated template for one render by LangChain."""
        return self._files[self._definition["prompts"][key]]

    def text(self, key):
        return self.render(key)
