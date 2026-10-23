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
from tradingagents.agents.post_screen import jev_screen
from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.structured import (
    NO_EXTERNAL_TOOLS,
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


def create_sentiment_analyst(llm, *, screen_factory=None):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches news + StockTwits + Reddit data, injects them into the
    prompt as structured blocks, and produces a structured sentiment
    report via structured output (with a free-text fallback for providers
    that do not support it).
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        # Pre-fetch all three sources. Each fetcher degrades gracefully and
        # returns a string (no exceptions surface from here), so the LLM
        # always sees something — either real data or a clear placeholder.
        news_block = get_news.func(ticker, start_date, end_date)
        # Acquire the smaller Reddit sample first, then use the remaining shared
        # post allowance for StockTwits. Both feeds remain represented.
        post_limit = get_config().get("social_screen_max_posts", 100)
        reddit_posts = []

        def collect_reddit(posts):
            reddit_posts.extend(posts)
            return [True] * len(posts), ""

        subreddits = subreddits_for(ticker)
        reddit_block = fetch_reddit_posts(
            ticker, subreddits, start_date=start_date, end_date=end_date,
            screen=collect_reddit, limit=max(1, post_limit - 1),
        )
        # Pass the analysis window so a historical run trims social posts to it
        # instead of leaking today's chatter into a backtest (#1220).
        screen = screen_factory(ticker, "stocktwits", instrument_context=instrument_context) if screen_factory else jev_screen(ticker)
        stocktwits_block = fetch_stocktwits_messages(
            ticker, limit=max(1, post_limit - len(reddit_posts)), start_date=start_date, end_date=end_date, screen=screen
        )
        screen = screen_factory(ticker, "reddit", instrument_context=instrument_context) if screen_factory else screen
        if screen:
            _, note = screen(reddit_posts)
            reddit_block = note + "\n\n" + reddit_block

        system_message = _build_system_message(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            news_block=news_block,
            stocktwits_block=stocktwits_block,
            reddit_block=reddit_block,
            subreddits=subreddits,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Report what your tools support; another agent decides the trade."
                    # No tool-calling here: the data is pre-fetched into the
                    # prompt, so tool-range wording would only invite a
                    # hallucinated tool call (#1130).
                    " Today's date is {current_date}; treat it as 'now' for all analysis. {instrument_context}"
                    " " + NO_EXTERNAL_TOOLS +
                    "\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = prompt.format_messages(messages=state["messages"])

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
        character = "r/wallstreetbets is often contrarian/exuberant; r/stocks more measured; r/investing longer-term"
    elif len(subreddits) > len(CRYPTO_SUBREDDITS):
        character = f"r/{subreddits[0]} leans toward the coin's holders; r/CryptoCurrency and r/CryptoMarkets are broader"
    else:
        character = "r/CryptoCurrency and r/CryptoMarkets are broad crypto communities"
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on three complementary data sources that have already been collected for you.

## Data sources (pre-fetched, in this prompt)

### News headlines — Yahoo Finance, past 7 days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

### StockTwits messages — retail-trader social platform indexed by cashtag
Fast-moving signal. Each message carries a user-labeled sentiment tag (Bullish / Bearish / no-label) plus the message body.

<start_of_stocktwits>
{stocktwits_block}
<end_of_stocktwits>

### Reddit posts — {", ".join(f"r/{sub}" for sub in subreddits)} (past 7 days)
Community discussion, without vote or comment counts. Subreddit character matters ({character}).

<start_of_reddit>
{reddit_block}
<end_of_reddit>

## How to analyze this data (best practices)

1. **Keep user tags and classifier sentiment separate.** StockTwits Bullish/Bearish/no-label tags are user-provided labels. Laya stance counts come from its classified subset of fetched posts; the displayed posts may be a different sample. State each signal's own numerator and denominator, including classified, unscreened and retained counts. Do not subtract, reconcile or equate these counts. Different totals or labels between classifier output and user tags are not a data-quality inconsistency. For example, one Laya bearish post plus 19 unscreened posts can coexist with ten user Bullish tags, zero Bearish tags and ten unlabelled posts. Unscreened does not mean neutral. Relevance uncertainty means retained evidence, not confirmed irrelevance. A screening budget limit means the fetched posts remain available for your reading; it is not a source outage. Read bodies and user tags independently, and explain differences in coverage without inventing contradictions. The older "Screened by Jev" summary also describes classifier output separately from user tags. Sample size matters: calculate a user-tag ratio using tagged posts only and disclose unlabelled posts and limited coverage.

2. **Look for cross-source divergences.** If news framing is bearish but StockTwits is overwhelmingly bullish, that mismatch is itself a signal — it can mean retail is leaning into a thesis the news flow hasn't caught up to (or vice versa, that retail is chasing while institutions are cautious).

3. **Read every supplied post for substance.** Classifier labels are fallible annotations, including confident predictions. Their counts measure model output, not market sentiment; never use those counts as directional evidence. Derive the sentiment assessment from the original authors' text and user tags, separate quoted opponents from the author's own opinion, and explicitly correct misclassified examples. Do not infer engagement absent vote or comment counts.
Match each individual classifier-label claim to the source:text_sha256 ID in the supplied annotation mapping and original post. Cite that ID when discussing a classification; never assign an aggregate label to a particular post. Keep the recorded label separate from your interpretation. Without a matching annotation, the individual label is unknown.

4. **Distinguish opinion from event.** A news headline ("Nvidia announces $500M Corning deal") is an event; a StockTwits post ("buying NVDA, this is going to moon") is opinion. Both are inputs but should be weighted differently in your conclusions.

5. **Identify recurring narrative themes.** What topic keeps coming up across sources? That's the dominant narrative driving current sentiment.

6. **Be honest about data limits.** If StockTwits returned only a handful of messages, or one or more sources returned an "<unavailable>" placeholder, the sentiment read is less robust — flag this explicitly in the `confidence` field and the narrative. If the sources are silent on a given subreddit, say so.

7. **Identify catalysts and risks** that emerge across sources — news of upcoming earnings, product launches, competitive threats, macro headlines, etc.

8. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals and technicals, not as a price call.

## Output fields

Fill the following fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. Use Mixed when sources point in clearly different directions; Neutral only when all sources are genuinely silent.
- **overall_score**: A number from 0 (maximally bearish) to 10 (maximally bullish); 5 is neutral. Keep it consistent with overall_band.
- Explain the score's evidence and weighting. It is an analyst judgment, not a calibrated probability. When classifier stances are mostly unclear, read the full posts, state any corrected interpretations, and avoid unsupported decimal precision.
- **confidence**: low / medium / high, based on data quality and sample size.
- **narrative**: Full source-by-source breakdown, divergences, dominant narrative themes, catalysts and risks, and a markdown summary table of key sentiment signals (direction, source, supporting evidence).

{get_language_instruction()}"""
