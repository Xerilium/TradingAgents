"""Bounded quote refresh and deterministic research handoff; no network."""
import asyncio
import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.test_mcp_gateway import _allow_event_loop_pipe  # noqa: F401
from tests.test_paper_service import BrokerFake, ScriptedGraph, desk  # noqa: F401
from tradingagents.integrations.maenifold import GatewayRateLimited
from tradingagents.web.service import DeskService, normalize_quotes, research_quote_context


class QuotesBroker(BrokerFake):
    async def aexecute(self, domain, command, parameters):
        return self.execute(domain, command, parameters)


def test_refresh_is_shared_bounded_and_does_not_refresh_account(tmp_path):
    broker = QuotesBroker()
    service = DeskService(tmp_path, gateway=broker)
    try:
        service.refresh()
        service.quotes_next_refresh = 0
        broker.calls.clear()
        refreshed = service.refresh_quotes()
        assert refreshed['quotes']['META']['price'] == 100
        assert refreshed['quotes_updated_at']
        assert [call[1] for call in broker.calls] == ['get_clock', 'get_stock_snapshot']
        for _ in range(10):
            service.refresh_quotes()
        assert len(broker.calls) == 2
        service.refresh_lock.acquire()
        try:
            service.quotes_next_refresh = 0
            service.refresh_quotes()
            assert len(broker.calls) == 2
        finally:
            service.refresh_lock.release()
    finally:
        service.close()


@pytest.mark.parametrize('failure', ['timeout', '429'])
def test_failed_refresh_preserves_prices_and_blocks_followups(tmp_path, monkeypatch, failure):
    broker = QuotesBroker()
    service = DeskService(tmp_path, gateway=broker)
    try:
        service.refresh()
        previous = copy.deepcopy(service._book()['quotes'])
        service.quotes_next_refresh = 0
        async def fail(coro, timeout):
            assert timeout == 45
            coro.close()
            raise TimeoutError() if failure == 'timeout' else GatewayRateLimited(900)
        monkeypatch.setattr(asyncio, 'wait_for', fail)
        with pytest.raises((ValueError, GatewayRateLimited)):
            service.refresh_quotes()
        assert service._book()['quotes'] == previous
        calls = len(broker.calls)
        with pytest.raises(GatewayRateLimited):
            service.refresh_quotes()
        assert len(broker.calls) == calls
    finally:
        service.close()


def test_research_context_has_observed_quote_and_excludes_historical_future_data():
    broker = QuotesBroker()
    raw = broker.execute('alpaca', 'get_stock_snapshot', {'symbols': 'META'})
    market = {'quotes': normalize_quotes(raw), 'clock': {'is_open': True}, 'updated_at': 'captured'}
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    context = research_quote_context('META', today, market)
    assert '"price": 100' in context and '"valid_two_sided_quote": true' in context
    raw['META']['latestQuote']['ap'] = 0
    market['quotes'] = normalize_quotes(raw)
    assert market['quotes']['META']['invalid_quote']
    assert '"valid_two_sided_quote": false' in research_quote_context('META', today, market)
    historical = research_quote_context('META', '2020-01-01', market)
    assert 'omitted for historical analysis' in historical and '100' not in historical


def test_closed_session_reference_is_separate_from_execution_freshness(monkeypatch):
    from tradingagents.web import service as service_module
    fixed = datetime.fromisoformat('2026-10-16T02:00:00+00:00')
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz)
    monkeypatch.setattr(service_module, 'datetime', Clock)
    quote = {'price': 100, 'bid': 99, 'ask': 101, 'invalid_quote': False,
             'timestamp': '2026-10-15T20:00:00Z', 'quote_timestamp': '2026-10-15T20:00:00Z'}
    market = {'quotes': {'META': quote}, 'clock': {'is_open': False,
              'timestamp': '2026-10-15T22:00:00Z', 'next_open': '2026-10-16T13:30:00Z'}}
    context = service_module.research_quote_context('META', '2026-10-15', market)
    assert '"reference_label": "market-closed reference"' in context
    assert '"fresh_for_execution": false' in context
    assert '"valid_two_sided_quote": false' in context
    quote['timestamp'] = quote['quote_timestamp'] = '2026-10-14T20:00:00Z'
    context = service_module.research_quote_context('META', '2026-10-15', market)
    assert '"reference_label": "older reference; session unverified"' in context


def test_research_worker_passes_and_persists_quote_context(desk):  # noqa: F811 - imported pytest fixture
    service, _ = desk
    received = []
    class CapturingGraph(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            received.append(initial['instrument_context'])
            yield from super().stream_run(initial, **kwargs)
    service.graph_factory = CapturingGraph
    service.start_run(['AAPL'])
    service.executor.run_next()
    result = service.state()['runs'][0]['results'][0]
    assert result['status'] == 'completed'
    assert '"symbol": "AAPL"' in received[0] and '"price": 100' in received[0]
    assert result['quote_context'] in received[0]
