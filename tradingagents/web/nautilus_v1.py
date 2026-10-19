"""Official v1 Python client interfaces over the shared read-only Alpaca adapter."""
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.events import OrderPendingCancel, OrderPendingUpdate
from nautilus_trader.config import (CacheConfig, LiveDataClientConfig,
    LiveExecClientConfig, LiveExecEngineConfig, LoggingConfig, TradingNodeConfig)
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.live.factories import LiveDataClientFactory, LiveExecClientFactory
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import ClientId, TraderId
from nautilus_trader.trading.strategy import Strategy as NativeStrategy

DataClientFactory, ExecutionClientFactory = LiveDataClientFactory, LiveExecClientFactory


class MarketDataClient(LiveMarketDataClient):
    def __init__(self, *, loop, name, config, msgbus, cache, clock, venue):
        super().__init__(loop, ClientId(name), venue, msgbus, cache, clock, InstrumentProvider(), config)

    cache = property(lambda self: self._cache)
    clock = property(lambda self: self._clock)

    def _handle_instrument(self, instrument):
        self._handle_data(instrument)

    async def _subscribe_quote_ticks(self, command):
        await self._subscribe_quotes(command)

    async def _subscribe_trade_ticks(self, command):
        await self._subscribe_trades(command)

    async def _unsubscribe_quote_ticks(self, command):
        await self._unsubscribe_quotes(command)

    async def _unsubscribe_trade_ticks(self, command):
        await self._unsubscribe_trades(command)


class ExecutionClient(LiveExecutionClient):
    def __init__(self, *, loop, name, config, msgbus, cache, clock, venue, account_id,
                 account_type, oms_type, base_currency):
        super().__init__(loop, ClientId(name), venue, oms_type, account_type, base_currency,
                         InstrumentProvider(), msgbus, cache, clock, config)
        self._set_account_id(account_id)

    cache = property(lambda self: self._cache)
    clock = property(lambda self: self._clock)
    client_id = property(lambda self: self.id)

    def calculate_commission(self, instrument, last_qty, last_px, liquidity_side):
        return self._calculate_commission(instrument, last_qty, last_px, liquidity_side)

    async def generate_mass_status(self, lookback_mins=None):
        return await self._generate_mass_status(lookback_mins)

    async def generate_order_status_report(self, command):
        return await self._generate_order_status_report(command)

    async def generate_order_status_reports(self, command):
        return await self._generate_order_status_reports(command)

    async def generate_position_status_reports(self, command):
        return await self._generate_position_status_reports(command)

    async def generate_fill_reports(self, command):
        return await self._generate_fill_reports(command)

    def generate_order_denied(self, order, reason):
        super().generate_order_denied(order.strategy_id, order.instrument_id,
                                     order.client_order_id, reason, self._clock.timestamp_ns())

    def generate_order_submitted(self, order, ts_event=None):
        super().generate_order_submitted(order.strategy_id, order.instrument_id,
                                        order.client_order_id, self._clock.timestamp_ns() if ts_event is None else ts_event)

    def generate_observed_pending(self, order, venue_id, state, ts_event):
        event_type = {"PENDING_CANCEL": OrderPendingCancel, "PENDING_UPDATE": OrderPendingUpdate}[state]
        self._send_order_event(event_type(self.trader_id, order.strategy_id, order.instrument_id,
            order.client_order_id, venue_id, self.account_id, UUID4(), ts_event,
            self._clock.timestamp_ns(), reconciliation=True))

    def generate_order_accepted(self, order, venue_id, ts_event):
        super().generate_order_accepted(order.strategy_id, order.instrument_id,
                                       order.client_order_id, venue_id, ts_event)

    def generate_order_canceled(self, order, venue_id, ts_event):
        super().generate_order_canceled(order.strategy_id, order.instrument_id,
                                       order.client_order_id, venue_id, ts_event)

    def generate_order_expired(self, order, venue_id, ts_event):
        super().generate_order_expired(order.strategy_id, order.instrument_id,
                                      order.client_order_id, venue_id, ts_event)

    def generate_order_rejected(self, order, reason, ts_event, due_post_only):
        super().generate_order_rejected(order.strategy_id, order.instrument_id,
                                       order.client_order_id, reason, ts_event, due_post_only)

    def generate_order_cancel_rejected(self, order, venue_id, reason, ts_event):
        super().generate_order_cancel_rejected(order.strategy_id, order.instrument_id,
                                              order.client_order_id, venue_id, reason, ts_event)

    def generate_order_modify_rejected(self, order, venue_id, reason, ts_event):
        super().generate_order_modify_rejected(order.strategy_id, order.instrument_id,
                                              order.client_order_id, venue_id, reason, ts_event)

    def generate_order_updated(self, order, venue_id, quantity, price, trigger_price, is_quote_quantity, ts_event, *, venue_order_id_modified=False):
        super().generate_order_updated(order.strategy_id, order.instrument_id, order.client_order_id,
            venue_id, quantity, price, trigger_price, ts_event, is_quote_quantity=is_quote_quantity, venue_order_id_modified=venue_order_id_modified)

    def generate_order_filled(self, order, venue_id, position_id, trade_id, quantity, price,
                              currency, commission, liquidity_side, ts_event):
        if commission is None:
            raise ValueError("v1 native OrderFilled requires resolved Money and fee provenance")
        super().generate_order_filled(order.strategy_id, order.instrument_id, order.client_order_id,
            venue_id, position_id, trade_id, order.side, order.order_type, quantity, price,
            currency, commission, liquidity_side, ts_event)


class Strategy(NativeStrategy):
    def subscribe_quotes(self, instrument):
        self.subscribe_quote_ticks(instrument)

    def subscribe_trades(self, instrument):
        self.subscribe_trade_ticks(instrument)

    def unsubscribe_quotes(self, instrument):
        self.unsubscribe_quote_ticks(instrument)

    def unsubscribe_trades(self, instrument):
        self.unsubscribe_trade_ticks(instrument)


def build_node(data_factory, exec_factory, observer, loop):
    config = TradingNodeConfig(trader_id=TraderId("TRADINGAGENTS-001"), timeout_connection=150.0,
        cache=CacheConfig(database=None),
        logging=LoggingConfig(log_colors=False, print_config=False),
        exec_engine=LiveExecEngineConfig(generate_missing_orders=False, load_cache=False,
            reconciliation=False, inflight_check_interval_ms=0, snapshot_orders=False, snapshot_positions=False),
        data_clients={"ALPACA": LiveDataClientConfig()}, exec_clients={"ALPACA": LiveExecClientConfig()})
    node = TradingNode(config=config, loop=loop)
    node.add_data_client_factory("ALPACA", data_factory)
    node.add_exec_client_factory("ALPACA", exec_factory)
    node.build()
    node.trader.add_strategy(observer)
    return node
