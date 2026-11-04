"""Read-only visual projection of a validated desktop workflow bundle."""
from tradingagents.workflows import ANALYSTS


# Primary and conditional agent-specific prompts. Shared prompts remain in the
# file list; this mapping is a navigation aid, not a full dependency graph.
PROMPTS = {
    "market": ("market_analyst", "analyst_wrapper", "wrap_up"),
    "social": ("sentiment_analyst", "sentiment_wrapper", "sentiment_reddit_stock", "sentiment_reddit_crypto", "sentiment_reddit_crypto_specific"),
    "news": ("news_analyst", "analyst_wrapper", "wrap_up"),
    "fundamentals": ("fundamentals_analyst", "fundamentals_analyst_etf", "fundamentals_review_etf", "fundamentals_review_stock", "fundamentals_review_tools", "analyst_wrapper", "wrap_up"),
    "bull": ("bull_researcher",), "bear": ("bear_researcher",),
    "research_manager": ("research_manager", "research_manager_desk"),
    "trader": ("trader_system", "trader_system_desk", "trader_user", "trader_user_desk", "trader_grounding", "trader_grounding_desk", "trader_report_section"),
    "aggressive": ("aggressive_debator",), "conservative": ("conservative_debator",),
    "neutral": ("neutral_debator",), "portfolio_manager": ("portfolio_manager", "portfolio_manager_desk", "portfolio_lessons"),
}


# Curated navigation aids, not an assembled prompt or exhaustive dependency graph.
INSTRUMENT = (
    ("shared_instrument", "Instrument identity context."),
    ("shared_historical_identity", "Used for a historical date when a name is available."),
    ("shared_resolved_identity", "Used when identity details are available."),
    ("shared_etf", "Used for ETF instruments."),
    ("shared_crypto", "Used for crypto instruments."),
)
LANGUAGE = (("shared_language", "Used when the configured output language is not English."),)
SNAPSHOT = (
    ("shared_snapshot", "Used when a verified market snapshot matches the run."),
    ("shared_snapshot_missing", "Used when the matching verified snapshot is unavailable."),
)
PORTFOLIO = (
    ("shared_portfolio_missing", "Used when neither portfolio context nor desk policy is supplied."),
    ("shared_portfolio_holdings_missing", "Used when desk policy is supplied without portfolio context."),
)
EVIDENCE = (
    ("shared_evidence_reference", "References evidence included in a separate message."),
    ("shared_evidence_wrapper", "Wraps supplied evidence in a separate message."),
)
DEBATE = (
    ("shared_opponent_opening", "Used when the opponent has not yet spoken."),
    ("shared_report_absent", "Used when an analyst report is empty."),
)
ANALYST_TURN = tuple((key, description) for key, description in (
    ("shared_memory_base", "Research memory guidance."),
    ("shared_memory_tools", "Research memory tool guidance."),
    ("shared_memory_build_context", "Guidance when BuildContext is available."),
    ("shared_memory_find_similar", "Guidance when FindSimilarConcepts is available."),
    ("shared_memory_search", "Guidance when SearchMemories is available."),
    ("shared_memory_read", "Guidance when ReadMemory is available."),
    ("shared_memory_thinking", "Guidance when SequentialThinking is available."),
    ("shared_memory_tool_instruction", "Wraps guidance for an available memory tool."),
    ("shared_memory_no_graph", "Used when BuildContext is unavailable."),
    ("shared_memory_unavailable", "Used when no search, read, or BuildContext tool is available."),
    ("shared_memory_final", "Closing research memory guidance."),
    ("shared_request_inputs", "Used when requesting required analyst inputs."),
    ("shared_duplicate_filing", "Used when projecting repeated filing evidence."),
    ("shared_tools_spent", "Used on the final turn after tool rounds are spent."),
    ("shared_called_tools", "Used when rendering tool calls as text."),
    ("shared_tool_returned", "Used when rendering tool responses as text."),
))
SCHEMA_FIELDS = {
    "social": {"SentimentReport": ("overall_band", "overall_score", "confidence", "narrative")},
    "research_manager": {"ResearchPlan": ("recommendation", "rationale", "strategic_actions"),
                         "DeskResearchPlan": ("recommendation", "strategic_actions")},
    "trader": {"TraderProposal": ("action", "reasoning", "entry_price", "stop_loss", "position_sizing"),
               "DeskTraderProposal": ("position_sizing",)},
    "portfolio_manager": {"PortfolioDecision": ("rating", "executive_summary", "investment_thesis", "price_target", "time_horizon"),
                          "DeskPortfolioDecision": ("rating", "executive_summary")},
}


def _prompt_groups(handler, keys, bindings):
    shared = INSTRUMENT + LANGUAGE
    if handler in ("market", "news", "fundamentals"):
        shared += ANALYST_TURN
    if handler in ("bull", "bear", "aggressive", "conservative", "neutral"):
        shared += DEBATE
    if handler not in ANALYSTS:
        shared += SNAPSHOT + EVIDENCE
    if handler in ("research_manager", "trader", "aggressive", "conservative", "neutral", "portfolio_manager"):
        shared += PORTFOLIO
    if handler in ("social", "research_manager", "trader", "portfolio_manager"):
        shared += (("no_external_tools", "Used on the structured-output path without external tools."),)
    schema = []
    for owner, fields in SCHEMA_FIELDS.get(handler, {}).items():
        for field in fields:
            condition = "Desk policy variant." if owner.startswith("Desk") else "Base schema; inherited unless overridden by the desk variant."
            schema.append((f"schema_{owner}_{field}", f"{owner}.{field}: {condition}"))
    def entries(items):
        return [{"key": key, "file": bindings[key], "description": description} for key, description in items]
    return {
        "agent": entries((key, "Agent-specific prompt or conditional variant.") for key in keys),
        "shared": entries(shared),
        "schema": entries(schema),
    }


def _label(value):
    # Numeric Mermaid entities make quotes, markup, directives and newlines
    # inert while keeping arbitrary user-defined names visible as text.
    return ''.join(c if c.isalnum() or c == ' ' else f'#{ord(c)};' for c in str(value))


def project_workflow(bundle):
    definition = bundle.definition
    nodes, edges, limits = definition['nodes'], definition['edges'], definition['limits']
    selected = set(definition['analysts'])
    active = {name: node for name, node in nodes.items()
              if node['handler'] != 'memory' and (node['handler'] not in ANALYSTS or node['handler'] in selected)}
    ids = {name: f'n{i}' for i, name in enumerate(active)}
    by_handler = {node['handler']: name for name, node in active.items()}
    lines = ['flowchart TD']
    metadata = {}

    def synthetic(node_id, name, caption, shape='rect'):
        metadata[node_id] = {'name': name, 'handler': None, 'tier': None, 'prompt_keys': [],
                             'prompt_files': [], 'synthetic': True, 'caption': caption}
        label = _label(name)
        lines.append(f'  {node_id}{{"{label}"}}' if shape == 'diamond' else f'  {node_id}["{label}"]')

    synthetic('start', 'Start', 'Visual boundary; not an executable agent.')
    synthetic('join', 'Analyst reports join', 'Visual representation of the selected analyst branches joining.')
    for name, node in active.items():
        handler, tier = node['handler'], node.get('tier')
        keys = list(PROMPTS.get(handler, ()))
        caption = f'{tier.capitalize()} model tier.' if tier else ''
        if handler in ANALYSTS:
            caption += f" Up to {limits['max_tool_rounds']} tool rounds."
        metadata[ids[name]] = {'name': name, 'handler': handler, 'tier': tier, 'prompt_keys': keys,
                               'prompt_files': [definition['prompts'][key] for key in keys],
                               'prompt_groups': _prompt_groups(handler, keys, definition['prompts']),
                               'synthetic': False, 'caption': caption.strip()}
        lines.append(f'  {ids[name]}["{_label(name)} ({_label(tier)})"]')

    # The validated direct edges identify branch join, first speakers and
    # managers. Memory is omitted because the desktop does not supply it.
    for edge in edges:
        if 'router' in edge:
            continue
        origin, target = edge['from'], edge['to']
        if origin == 'START' and target in active:
            lines.append(f'  start --> {ids[target]}')
        elif isinstance(origin, list):
            for name in origin:
                if name in active:
                    lines.append(f'  {ids[name]} --> join')
            lines.append(f'  join --> {ids[target]}')
        elif origin in active and target in active:
            lines.append(f'  {ids[origin]} --> {ids[target]}')

    # ConditionalLogic routes from each recognized speaker to the next. The
    # validated path maps bind these router outcomes to the YAML node names.
    # Rotate the cycle to the first participant selected by each direct edge.
    outcome_for_handler = {'bull': 'Bull Researcher', 'bear': 'Bear Researcher',
                           'aggressive': 'Aggressive Analyst', 'conservative': 'Conservative Analyst',
                           'neutral': 'Neutral Analyst'}
    next_handler = {'bull': 'bear', 'bear': 'bull', 'aggressive': 'conservative',
                    'conservative': 'neutral', 'neutral': 'aggressive'}
    router_edges = {edge['from']: edge for edge in edges if 'router' in edge}
    join_edge = next(edge for edge in edges if isinstance(edge['from'], list))
    trader_name = by_handler['trader']
    risk_entry = next(edge for edge in edges if edge.get('from') == trader_name and 'to' in edge)
    for router, first, limit_key, finish_outcome in (
            ('research_debate', join_edge['to'], 'max_debate_rounds', 'Research Manager'),
            ('risk_debate', risk_entry['to'], 'max_risk_discuss_rounds', 'Portfolio Manager')):
        sequence = [first]
        while True:
            current = sequence[-1]
            edge = router_edges[current]
            following = edge['paths'][outcome_for_handler[next_handler[nodes[current]['handler']]]]
            if following == first:
                break
            sequence.append(following)
        for current, following in zip(sequence, sequence[1:]):
            lines.append(f'  {ids[current]} --> {ids[following]}')
        rounds = limits[limit_key]
        diamond = 'research_round' if router == 'research_debate' else 'risk_round'
        synthetic(diamond, f'{"Research" if router == "research_debate" else "Risk"} debate rounds: limit {rounds}',
                  'Round summary; runtime checks count after each turn. Speaker-label fallback can route differently.',
                  'diamond')
        lines.append(f'  {ids[sequence[-1]]} --> {diamond}')
        lines.append(f'  {diamond} -->|Yes| {ids[first]}')
        lines.append(f"  {diamond} -->|No| {ids[router_edges[sequence[-1]]['paths'][finish_outcome]]}")

    synthetic('decision', 'Final decision', 'Visual representation of the portfolio manager output; not a separate agent.')
    synthetic('boundary_end', 'End', 'Visual boundary; not an executable agent.')
    lines.append(f"  {ids[by_handler['portfolio_manager']]} --> decision")
    lines.append('  decision --> boundary_end')
    return {'mermaid': '\n'.join(lines), 'nodes': metadata}
