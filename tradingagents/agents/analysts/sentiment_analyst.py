"""Sentiment analyst: one sentiment report from three sources.

The node fetches its sources before calling the model and puts them in the
prompt, so the model reports on data it was given rather than inventing posts:

  1. News headlines: Yahoo Finance
  2. StockTwits messages: the cashtag stream, with Bullish/Bearish tags
  3. Reddit posts: r/wallstreetbets, r/stocks, r/investing, or crypto communities for a crypto pair

Each source is trimmed to the analysis window. The paper desk injects Maenifold
Laya screening; other callers can use Jev with a TypeSafe key (see post_screen).
These feeds serve recent items
and are not archived, so a historical run's sentiment inputs are not
point-in-time.

The report is a SentimentReport through structured output where the provider
supports it and free text otherwise, so the band, score and confidence header
reads the same across providers.
"""

from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.prompt_evidence import EvidencePrompt
from tradingagents.agents.post_screen import jev_screen
from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.agents.tools import get_news
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.vendors.reddit import (
    CRYPTO_SUBREDDITS,
    DEFAULT_SUBREDDITS,
    fetch_reddit_posts,
    subreddits_for,
)
from tradingagents.dataflows.vendors.stocktwits import fetch_stocktwits_messages


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm, *, screen_factory=None, workflow):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches news + StockTwits + Reddit data, injects them into the
    prompt as structured blocks, and produces a structured sentiment
    report via structured output (with a free-text fallback for providers
    that do not support it).
    """
    structured_llm = bind_structured(llm, SentimentReport, 'Sentiment Analyst', workflow=workflow)

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state, workflow)

        # Pre-fetch all three sources. Each fetcher degrades gracefully and
        # returns a string (no exceptions surface from here), so the LLM
        # always sees something — either real data or a clear placeholder.
        news_block = get_news.func(ticker, start_date, end_date)
        # Acquire the smaller Reddit sample first, then use the remaining shared
        # post allowance for StockTwits. Both feeds remain represented.
        post_limit = get_config().get("social_screen_max_posts", 100)
        reddit_posts = []
        reddit_acquisition = {}

        def collect_reddit(posts):
            reddit_posts.extend(posts)
            return [True] * len(posts), ""

        subreddits = subreddits_for(ticker)
        reddit_block = fetch_reddit_posts(
            ticker, subreddits, start_date=start_date, end_date=end_date,
            screen=collect_reddit, limit=max(1, post_limit - 1),
            on_acquisition=reddit_acquisition.update,
        )
        # Pass the analysis window so a historical run trims social posts to it
        # instead of leaking today's chatter into a backtest (#1220).
        screen = screen_factory(ticker, "stocktwits", instrument_context=instrument_context) if screen_factory else jev_screen(ticker)
        if screen is not None and hasattr(screen, "separate_decisions"):
            screen.separate_decisions = True
        stocktwits_block = fetch_stocktwits_messages(
            ticker, limit=max(1, post_limit - len(reddit_posts)), start_date=start_date, end_date=end_date, screen=screen
        )
        stocktwits_decisions = getattr(screen, "decision_context", None)
        screen = screen_factory(ticker, "reddit", instrument_context=instrument_context) if screen_factory else screen
        if screen is not None and hasattr(screen, "separate_decisions"):
            screen.separate_decisions = True
        if screen:
            if screen_factory:
                screen.acquisition = reddit_acquisition
            _, note = screen(reddit_posts)
            reddit_block = note + "\n\n" + reddit_block

        reddit_decisions = getattr(screen, "decision_context", None)
        evidence = EvidencePrompt(workflow)
        if stocktwits_decisions:
            evidence.add("StockTwits classifier decisions", stocktwits_decisions, compressible=False)
        if reddit_decisions:
            evidence.add("Reddit classifier decisions", reddit_decisions, compressible=False)
        system_message = _build_system_message(
            workflow=workflow,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            news_block=evidence.add('news headlines', news_block),
            stocktwits_block=evidence.add('StockTwits messages', stocktwits_block),
            reddit_block=evidence.add('Reddit posts', reddit_block),
            subreddits=subreddits,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    workflow.template('sentiment_wrapper'),
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(NO_EXTERNAL_TOOLS=workflow.text('no_external_tools'))
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = [*prompt.format_messages(messages=state["messages"]), *evidence.messages("")[1:]]

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
        )

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    workflow,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
    subreddits: tuple[str, ...] = DEFAULT_SUBREDDITS,
) -> str:
    """Assemble the sentiment-analyst system message with structured data blocks."""
    if subreddits == DEFAULT_SUBREDDITS:
        character = workflow.text('sentiment_reddit_stock')
    elif len(subreddits) > len(CRYPTO_SUBREDDITS):
        character = workflow.render('sentiment_reddit_crypto_specific', subreddit=subreddits[0])
    else:
        character = workflow.text('sentiment_reddit_crypto')
    return workflow.render('sentiment_analyst', ticker=ticker, start_date=start_date, end_date=end_date, news_block=news_block, stocktwits_block=stocktwits_block, value=', '.join((f'r/{sub}' for sub in subreddits)), character=character, reddit_block=reddit_block, get_language_instruction=get_language_instruction(workflow))
