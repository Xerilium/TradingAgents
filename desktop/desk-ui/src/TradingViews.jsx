import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Accordion, AccordionDetails, AccordionSummary, Alert, Autocomplete, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel,
  Grid, Link, MenuItem, Stack, Tab, Tabs, TextField, Typography} from '@mui/material';
import {useDesk} from './DeskContext.jsx';
import {Page, Evidence, DataTable, money, number, dateTime, Status} from './ui.jsx';
import {InstrumentChart} from './ResearchMarkets.jsx';

const TERMINAL = ['filled', 'canceled', 'cancelled', 'rejected', 'expired', 'replaced'];
const PREVIEW_MS = 300000;
const pct = v => number(v) === null ? 'Unavailable' : `${Number(v).toFixed(2)}%`;
const text = v => v === null || v === undefined || v === '' ? 'Unavailable' : String(v);
const arr = v => Array.isArray(v) ? v : [];
// The command store keeps commands, approvals, basket groups and option instructions as dicts keyed by id.
const vals = v => Array.isArray(v) ? v : v && typeof v === 'object' ? Object.values(v) : [];

function Field({label, value, onChange, ...rest}) {
  return <TextField size="small" fullWidth label={label} value={value ?? ''} onChange={event => onChange(event.target.value)} {...rest}/>;
}
function Pick({label, value, onChange, options, ...rest}) {
  return <TextField select size="small" fullWidth label={label} value={value ?? ''} onChange={event => onChange(event.target.value)} {...rest}>
    {options.map(o => Array.isArray(o) ? <MenuItem key={o[0]} value={o[0]}>{o[1]}</MenuItem> : <MenuItem key={o} value={o}>{o}</MenuItem>)}
  </TextField>;
}
function Fact({label, value}) {
  return <Box><Typography variant="caption" color="text.secondary">{label}</Typography><Typography>{value}</Typography></Box>;
}
function Section({title, children, actions, fill = false}) {
  return <Stack spacing={1.5} sx={{p: 2, border: 1, borderColor: 'divider', borderRadius: 1, minWidth: 0,
    ...(fill && {height: '100%', minHeight: 0, '& > *': {flexShrink: 0}})}}>
    <Stack direction="row"   useFlexGap  spacing={1} sx={{justifyContent: "space-between", alignItems: "center", flexWrap: "wrap"}}>
      <Typography variant="h2" sx={{fontSize: 18}}>{title}</Typography>{actions}</Stack>
    {children}
  </Stack>;
}
const Notice = ({severity = 'warning', children}) => <Alert severity={severity}>{children}</Alert>;

// Shared derived account facts. Coverage is known only when the broker observation is verified and reconciled.
function useFacts() {
  const {state} = useDesk();
  return useMemo(() => {
    const nautilus = state?.nautilus || {}, connection = state?.connection || {}, commands = state?.commands || {};
    const investor = state?.investor || {}, data = commands.data || {};
    const reasons = [];
    if (commands.execution_enabled !== true) reasons.push('Browse-only: order execution is not enabled.');
    if (connection.connected !== true || connection.account_verified !== true) reasons.push('Broker account is not connected and verified.');
    if (nautilus.status !== 'connected') reasons.push(`Nautilus is ${nautilus.status ?? 'unavailable'}.`);
    if (nautilus.account?.trading_blocked) reasons.push('The broker account is trading blocked.');
    if (data.new_orders_blocked) reasons.push('New orders are blocked.');
    if (nautilus.reconciliation?.status !== 'reconciled') reasons.push('Broker account is not reconciled.');
    else if (data.recovery_required) reasons.push(`Recovery required: ${text(data.recovery_reason)}`);
    const exposureKnown = connection.account_verified === true && nautilus.status === 'connected' && nautilus.reconciliation?.status === 'reconciled';
    const coverage = kind => exposureKnown && connection.connected === true && state?.broker_observation?.[`${kind}_complete`] === true;
    return {reasons, exposureKnown, coverage, nautilus, connection, commands, investor, data};
  }, [state]);
}

function Ledger() {
  const {state} = useDesk();
  const f = useFacts(), a = state?.account || {};
  const positions = arr(state?.positions), pl = positions.map(p => number(p.unrealized_intraday_pl));
  const todayKnown = f.coverage('positions') && positions.length > 0 && pl.every(v => v !== null);
  const open = arr(state?.orders).filter(o => !TERMINAL.includes(String(o.status).toLowerCase())).length;
  return <Grid container spacing={2}>
    {[['Equity', money(a.equity)], ['Cash', money(a.cash)], ['Buying power', money(a.buying_power)], ['Long value', money(a.long_market_value)],
      ['Open orders', f.coverage('orders') ? open : 'UNKNOWN'],
      ['Today P/L', todayKnown ? money(pl.reduce((s, v) => s + v, 0)) : positions.length === 0 && f.coverage('positions') ? money(0) : 'Unavailable'],
    ].map(([label, value]) => <Grid key={label} size={{xs: 6, md: 2}}><Fact label={label} value={value}/></Grid>)}
    {f.reasons.length > 0 && <Grid size={12}><Notice>{f.reasons.join(' ')} Values shown are retained observations.</Notice></Grid>}
  </Grid>;
}

/* ---------------------------------------------------------------- SPY */

function fundValid(fund) {
  const b = fund?.budget;
  if (!fund || !Number.isInteger(fund.revision) || !Array.isArray(fund.plans) || !b || typeof b.active !== 'boolean') return false;
  if (!['policy_floor_usd', 'required_reserve_usd', 'cash_usd', 'equity_usd', 'shortfall_usd', 'investable_sleeve_usd'].every(k => number(b[k]) !== null && Number(b[k]) >= 0)) return false;
  if (b.active ? number(b.spending_reserve_usd) === null || number(b.authored_reserve_usd) === null : b.spending_reserve_usd !== null || b.authored_reserve_usd !== null) return false;
  if (!(number(b.spendable_cash_usd) !== null || b.spendable_cash_usd === null && typeof b.spendable_cash_error === 'string')) return false;
  return Boolean(b.account_at && b.account_observation_started_at);
}
const previewValid = p => p && typeof p.as_of === 'string' && Array.isArray(p.trades) && Array.isArray(p.deferred) && Array.isArray(p.policy_blockers) &&
  Number.isInteger(p.positions) && Number.isInteger(p.total) && Number.isInteger(p.policy_revision) && (p.already_completed === undefined || Number.isInteger(p.already_completed) && p.already_completed >= 0);

const FUND_FIELDS = [['monthly_net_withdrawal_usd', 'Monthly net withdrawal / USD'], ['reserve_months', 'Reserve months'],
  ['tax_provision_usd', 'Tax provision / USD'], ['trading_cushion_usd', 'Trading cushion / USD']];

function FundPlan() {
  const {state, api, act, refresh} = useDesk();
  const investor = state?.investor, fund = investor?.fund_plans, account = state?.nautilus?.account?.id;
  const current = arr(fund?.plans).find(p => p.account_id === fund?.current_account_id) ?? fund?.current;
  const seed = useMemo(() => ({account_id: fund?.current_account_id, generation: state?.store_generation, server: state?.server_instance_id, investor: investor?.revision,
    fund: fund?.revision, plan: current?.revision ?? 0}), [fund, current, investor, state?.store_generation]);
  const [base, setBase] = useState(null);
  const [draft, setDraft] = useState(null);
  useEffect(() => { // seed once, never overwrite a user's draft from polling
    if (!draft && fund && fundValid(fund)) {
      setBase(seed);
      setDraft({status: current?.status ?? 'inactive', ...Object.fromEntries(FUND_FIELDS.map(([k]) => [k, current?.[k] ?? '']))});
    }
  }, [draft, fund, seed, current]);
  if (!fund) return <Notice severity="info">Fund plan is not loaded.</Notice>;
  if (!fundValid(fund)) return <Notice>The fund plan contract is invalid or incomplete; planning is unavailable.</Notice>;
  const b = fund.budget, drifted = base && JSON.stringify(base) !== JSON.stringify(seed);
  const set = k => v => setDraft(d => ({...d, [k]: v}));
  const save = () => act('fund-plan-save', '/api/investor', {action: 'fund_plan_save', account_id: base.account_id, store_generation: base.generation,
    expected_revision: base.investor, fund_plans_revision: base.fund, plan_revision: base.plan, status: draft.status,
    ...Object.fromEntries(FUND_FIELDS.map(([k]) => [k, draft[k] === '' ? null : draft[k]]))}).catch(() => {});
  const reload = async () => { await api('/api/investor'); await refresh({fresh: true}); setDraft(null); };
  const missing = draft?.status === 'active' && FUND_FIELDS.some(([k]) => draft[k] === '');
  return <Section title="Fund plan">
    <Grid container spacing={2}>
      {[['Investable sleeve', money(b.investable_sleeve_usd)], ['Required reserve', money(b.required_reserve_usd)], ['Policy floor', money(b.policy_floor_usd)],
        ['Spendable cash', b.spendable_cash_usd === null ? b.spendable_cash_error : money(b.spendable_cash_usd)], ['Shortfall', money(b.shortfall_usd)],
        ['Account observed', dateTime(b.account_at)]].map(([l, v]) => <Grid key={l} size={{xs: 6, md: 2}}><Fact label={l} value={v}/></Grid>)}
    </Grid>
    {draft && <Grid container spacing={2}>
      <Grid size={{xs: 12, md: 3}}><Pick label="Plan" value={draft.status} onChange={set('status')} options={[['inactive', 'Planning only'], ['active', 'Apply reserve']]}/></Grid>
      {FUND_FIELDS.map(([k, l]) => <Grid key={k} size={{xs: 12, md: 3}}><Field label={l} value={draft[k]} onChange={set(k)}/></Grid>)}
    </Grid>}
    {drifted && <Notice>The account or a revision changed since this draft was loaded. Reload the plan before saving.</Notice>}
    {missing && <Notice>An applied reserve needs all four fields.</Notice>}
    <Stack direction="row" spacing={1}>
      <Button variant="contained" disabled={!draft || drifted || missing || !account} onClick={save}>Save plan revision</Button>
      <Button onClick={() => reload().catch(() => {})}>Reload plan</Button>
    </Stack>
    <Typography variant="body2" color="text.secondary">A material change pauses automatic trading and discards any rebalance preview.</Typography>
  </Section>;
}

function RunProgress({run}) {
  if (!run) return <Notice severity="info">No rebalance run has been recorded.</Notice>;
  const c = run.batch_counts || {};
  const keys = ['admitted', 'native_queued', 'transport_started', 'sent', 'working', 'filled', 'expired', 'rejected', 'unknown', 'not_sent'];
  const sessionEnded = run.status === 'blocked' && run.message === 'The approved regular session ended. Preview again before submitting.';
  return <Section title={sessionEnded ? 'Previous session ended' : 'Latest run'}>
    <Stack direction="row" spacing={2} useFlexGap   sx={{flexWrap: "wrap", alignItems: "center"}}>
      <Status value={sessionEnded ? 'Session ended' : run.status}/><Typography>Session {text(run.session)} · as of {text(run.as_of)}</Typography>
      <Typography>Run progress {text(run.completed)} of {text(run.total)}{run.limited ? ' (limited)' : ''}</Typography>
    </Stack>
    {run.message && <Typography>{run.message}</Typography>}
    <Grid container spacing={2}>{keys.map(k => <Grid key={k} size={{xs: 4, md: 1.2}}><Fact label={k.replaceAll('_', ' ')} value={text(c[k])}/></Grid>)}</Grid>
    {arr(run.deferred).length > 0 && <DataTable rows={run.deferred} getRowId={d => JSON.stringify(d.terms)} empty="None"
      columns={[{id: 'terms', label: 'Deferred trade', value: r => `${text(r.terms?.side)} ${text(r.terms?.quantity)} ${text(r.terms?.symbol)}`},
        {id: 'reasons', label: 'Reasons', value: r => arr(r.reasons).join('; ') || null}]}/>}
    <Typography variant="body2" color="text.secondary">Run progress describes this run only; it is separate from current holdings and each command's broker outcome.</Typography>
  </Section>;
}

export function SpyReview() {
  const {state, api, refresh} = useDesk();
  const f = useFacts();
  const schedule = state?.investor?.spy_rebalance;
  const [captured, setCaptured] = useState(null); // {preview, identity, at}
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (!captured) return undefined; const t = setInterval(() => setNow(Date.now()), 15000); return () => clearInterval(t); }, [captured]);
  const fund = state?.investor?.fund_plans, account = schedule?.eligible_account_id;
  const identity = useMemo(() => JSON.stringify([state?.server_instance_id, state?.store_generation, state?.nautilus?.account?.id, state?.nautilus?.connection_session,
    fund?.revision, state?.investor?.data?.policy?.revision]), [state, fund]);
  const eligible = Boolean(account) && (!schedule?.account_id || schedule.account_id === account) && state?.investor?.broker_transport_enabled === true && fundValid(fund) &&
    fund.current_account_id === account;
  const stale = captured && (captured.identity !== identity || now - captured.at > PREVIEW_MS || state?.nautilus?.account?.id !== account);
  const preview = captured && !stale ? captured.preview : null;
  const run = schedule?.run;
  const body = (action, extra = {}) => ({action, rebalance_revision: schedule.revision, account_id: account, dedicated: action === 'spy_rebalance_enable', ...extra});
  const request = async (action, extra) => {
    setBusy(action); setMessage('');
    try { const r = await api('/api/investor', body(action, extra)); await refresh({fresh: true}).catch(() => {}); return r; } finally { setBusy(''); }
  };
  const previewRun = async action => {
    const at = Date.now(), id = identity;
    try {
      const result = await request(action, {});
      const p = result?.preview ?? result;
      if (!previewValid(p)) { setCaptured(null); setMessage('The preview was malformed, so it is unavailable and submission is disabled.'); return; }
      setCaptured({preview: p, identity: id, at});
    } catch (e) { setCaptured(null); setMessage(e.message); }
  };
  const submit = async () => {
    const token = captured.preview.submit_token;
    try {
      const r = await request('spy_rebalance_submit', {submit_token: token});
      setMessage(r?.message || 'Submission request accepted. Check the latest run and per-command outcomes.');
      setCaptured(null);
    } catch (e) {
      if (e.spyPreviewNotQueued) setMessage(`Nothing was queued; the preview is retained. ${e.message}`);
      else { setCaptured(null); setMessage(`Submission result is unknown: ${e.message} Check the latest run, orders and fills before previewing again.`); }
    }
  };
  const simple = action => request(action).then(r => setMessage(r?.message || '')).catch(e => setMessage(e.message));
  if (!schedule) return <Notice severity="info">SPY rebalance state is not loaded.</Notice>;
  const canSubmit = Boolean(preview?.submit_token) && f.reasons.length === 0 && !schedule.in_progress && !busy;
  const trades = arr(preview?.trades);
  const offerRemaining = run && (run.status === 'blocked' || run.status === 'submitted' && arr(run.deferred).length > 0);
  return <Stack spacing={2}>
    <Section title="Automatic trading" actions={<Status value={schedule.enabled ? 'enabled' : 'paused'}/>}>
      <Typography variant="body2">Automatic trading is separate from this manual review.</Typography>
      <Stack direction="row" spacing={1}>
        {schedule.enabled ? <Button disabled={Boolean(busy)} onClick={() => simple('spy_rebalance_pause')}>Pause automatic trading</Button>
          : <Button variant="contained" disabled={!eligible || Boolean(busy)} onClick={() => simple('spy_rebalance_enable')}>Enable automatic trading</Button>}
        <Button disabled={Boolean(busy)} onClick={() => simple('spy_rebalance_check')}>Check now</Button>
      </Stack>
    </Section>
    <RunProgress run={run}/>
    <Section title="Rebalance review">
      {!eligible && <Notice>Preview is unavailable until an eligible account, broker transport and a valid fund plan are present.</Notice>}
      {f.reasons.length > 0 && <Notice>Submission is blocked: {f.reasons.join(' ')}</Notice>}
      <Stack direction="row" spacing={1} useFlexGap  sx={{flexWrap: "wrap"}}>
        <Button variant="contained" disabled={!eligible || Boolean(busy)} onClick={() => previewRun('spy_rebalance_preview')}>1. Preview next rebalance</Button>
        {offerRemaining && <Button disabled={!eligible || Boolean(busy)} onClick={() => previewRun('spy_rebalance_preview_remaining')}>Preview remaining</Button>}
        {run?.status === 'queued' && <Button color="warning" disabled={Boolean(busy)} onClick={() => simple('spy_rebalance_cancel')}>Cancel queued run</Button>}
      </Stack>
      {stale && <Notice>This preview is no longer current (account, session, fund plan, policy or age changed). Preview again.</Notice>}
      {message && <Notice severity="info">{message}</Notice>}
      {preview && <Stack spacing={1.5}>
        <Grid container spacing={2}>
          {[['As of', text(preview.as_of)], ['Quotes', dateTime(preview.quote_at)], ['Positions', `${preview.positions} of ${preview.total}`],
            ['Already completed', preview.already_completed], ['Target stocks', pct(preview.target_stock_pct)], ['Fund budget', money(preview.fund_budget)]]
            .map(([l, v]) => <Grid key={l} size={{xs: 6, md: 2}}><Fact label={l} value={v}/></Grid>)}
        </Grid>
        {preview.policy_blockers.length > 0 && <Notice>Policy blockers: {preview.policy_blockers.join('; ')}</Notice>}
        {preview.deferred.length > 0 && <Notice severity="info">{preview.deferred.length} trade(s) are deferred to a later preview.</Notice>}
        <DataTable rows={trades} getRowId={t => `${t.symbol}-${t.side}`} empty="No trades match."
          columns={[{id: 'symbol', label: 'Symbol'}, {id: 'side', label: 'Side'}, {id: 'quantity', label: 'Quantity', numeric: true},
            {id: 'order_type', label: 'Type'}, {id: 'limit_price', label: 'Limit', numeric: true, render: t => t.limit_price === null || t.limit_price === undefined ? '—' : money(t.limit_price)}]}/>
        <Notice severity="info">{state?.nautilus?.market_open === false ? 'The market is closed; submission queues this exact preview for the next session.' : 'Submission sends this exact preview once. The token is single-use.'}</Notice>
        <Button variant="contained" color="warning" disabled={!canSubmit} onClick={submit}>2. Submit this preview</Button>
      </Stack>}
    </Section>
  </Stack>;
}

export function SpyView() {
  const {state, page} = useDesk();
  return <Page title="SPY portfolio" subtitle="Dedicated SPY rebalance: review, submit and track.">
    {!state ? <Typography>Loading…</Typography> : <>
      <Ledger/>
      <SpyReview/>
      <FundPlan/>
      <Evidence title="Rebalance source details" data={page === 'spy' ? state.investor?.spy_rebalance : null}/>
    </>}
  </Page>;
}

/* ---------------------------------------------------------------- Dashboard */

function PositionsTable({onSelect, fill = false}) {
  const {state} = useDesk();
  const f = useFacts(), known = f.coverage('positions');
  const rows = arr(state?.positions);
  const pc = v => number(v) === null ? 'Unavailable' : pct(Number(v) * 100);
  return <Stack spacing={1} sx={fill ? {height: '100%', minHeight: 0, flex: 1, '& > .MuiAlert-root': {flexShrink: 0}} : undefined}>
    {!known && <Notice>Holdings are unverified or incomplete; rows are retained observations.</Notice>}
    <DataTable fill={fill} rows={rows} getRowId={p => p.symbol} onRowClick={onSelect} empty={known ? 'No open positions reported.' : 'Holdings unavailable or incomplete.'}
      columns={[{id: 'symbol', label: 'Symbol'}, {id: 'qty', label: 'Qty', numeric: true, render: p => text(p.qty)},
        {id: 'avail', label: 'Broker available', numeric: true, value: p => p.qty_available},
        {id: 'price', label: 'Last', numeric: true, value: p => p.current_price, render: p => money(p.current_price)},
        {id: 'day', label: 'Today P/L', numeric: true, value: p => p.unrealized_intraday_pl, render: p => `${money(p.unrealized_intraday_pl)} / ${pc(p.unrealized_intraday_plpc)}`},
        {id: 'upl', label: 'Total UPL %', numeric: true, value: p => number(p.unrealized_plpc) === null ? null : Number(p.unrealized_plpc) * 100, render: p => pc(p.unrealized_plpc)}]}/>
  </Stack>;
}

function OrdersTable() {
  const {state} = useDesk();
  const rows = arr(state?.orders);
  return <DataTable rows={rows} getRowId={o => o.id} empty="No orders reported."
    columns={[{id: 'symbol', label: 'Symbol'}, {id: 'side', label: 'Side'}, {id: 'qty', label: 'Qty', numeric: true, render: o => text(o.qty)},
      {id: 'type', label: 'Type', value: o => o.type ?? o.order_type}, {id: 'status', label: 'Status', render: o => <Status value={o.status}/>},
      {id: 'filled', label: 'Filled', numeric: true, value: o => o.filled_qty}]}/>;
}

const PERIOD_DAYS = {week: 7, month: 31, quarter: 92, half: 183};

// Saved raw daily bars for the selected stock, drawn with the maintained Lightweight Charts library through a React ref.
function DashboardChart({symbol, active}) {
  const {state, api} = useDesk();
  const host = React.useRef(null);
  const [period, setPeriod] = useState('month'), [history, setHistory] = useState(null), [error, setError] = useState('');
  const entries = Object.values(state?.market_history?.data?.entries || {}).filter(e => e.symbol === symbol && e.timeframe === '1Day');
  const entry = entries.sort((a, b) => String(b.captured_at).localeCompare(String(a.captured_at)))[0];
  const key = entry?.key;
  useEffect(() => {
    setHistory(null); setError('');
    if (!active || !symbol || !key) return undefined;
    const controller = new AbortController();
    api(`/api/market-history?symbol=${encodeURIComponent(symbol)}&timeframe=1Day&key=${encodeURIComponent(key)}`, undefined, {signal: controller.signal})
      .then(r => {
        if (r.symbol !== symbol || r.timeframe !== '1Day' || r.key !== key || !Array.isArray(r.bars)) throw new Error('The saved history does not match the selected stock.');
        setHistory(r);
      }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [active, symbol, key, api]);
  const bars = useMemo(() => arr(history?.bars).slice(-Math.round(PERIOD_DAYS[period] * 5 / 7) - 1), [history, period]);
  useEffect(() => {
    const library = window.LightweightCharts;
    if (!host.current || !library || bars.length === 0) return undefined;
    const time = t => typeof t === 'number' ? (t > 1e11 ? Math.floor(t / 1000) : t) : t;
    const chart = library.createChart(host.current, {autoSize: true, height: 320,
      layout: {background: {color: 'transparent'}, textColor: '#cdd6df'}, grid: {vertLines: {color: '#1f2b38'}, horzLines: {color: '#1f2b38'}}});
    const candles = chart.addSeries(library.CandlestickSeries, {upColor: '#3ecf8e', downColor: '#0b1722', borderUpColor: '#3ecf8e', borderDownColor: '#e5484d', wickUpColor: '#3ecf8e', wickDownColor: '#e5484d'});
    candles.setData(bars.map(b => ({time: time(b.t), open: Number(b.o), high: Number(b.h), low: Number(b.l), close: Number(b.c)})));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars]);
  if (!symbol) return <Typography>Select a stock in Watch.</Typography>;
  return <Stack spacing={1}>
    <Stack direction="row" spacing={1}  sx={{alignItems: "center"}}>
      <Typography variant="h3" sx={{fontSize: 16}}>{symbol} · saved daily bars</Typography>
      <Pick label="Period" value={period} onChange={setPeriod} options={Object.keys(PERIOD_DAYS)} sx={{maxWidth: 140}}/>
    </Stack>
    {!key && <Notice severity="info">No saved daily history for {symbol}. Collect it in Markets.</Notice>}
    {error && <Notice>{error}</Notice>}
    {!window.LightweightCharts && <Notice>Chart library unavailable; recorded bars are listed below.</Notice>}
    <Box ref={host} sx={{minHeight: bars.length ? 320 : 0}}/>
    {bars.length > 0 && <DataTable rows={[...bars].reverse()} getRowId={b => String(b.t)} empty=""
      columns={[{id: 't', label: 'Date', type: 'dateTime', value: b => typeof b.t === 'number' ? new Date(b.t > 1e11 ? b.t : b.t * 1000).toISOString() : b.t, render: b => String(b.t)}, {id: 'o', label: 'Open', numeric: true, render: b => text(b.o)}, {id: 'h', label: 'High', numeric: true, render: b => text(b.h)},
        {id: 'l', label: 'Low', numeric: true, render: b => text(b.l)}, {id: 'c', label: 'Close', numeric: true, render: b => text(b.c)}, {id: 'v', label: 'Volume', numeric: true, render: b => text(b.v)}]}/>}
  </Stack>;
}

export function DashboardView() {
  const {state, navigate, setSelectedSymbol, selectedSymbol, page} = useDesk();
  const [tab, setTab] = useState('watch');
  const f = useFacts();
  const open = useCallback(row => { setSelectedSymbol(row.symbol); }, [setSelectedSymbol]);
  const universe = arr(state?.config?.universe), quotes = state?.quotes || {}, held = new Set(arr(state?.positions).map(p => p.symbol));
  const watch = useMemo(() => universe.map(symbol => ({symbol, ...(quotes[symbol] || {})})), [universe, quotes]);
  const attention = [...f.reasons];
  const proposals = arr(f.investor.data?.proposals);
  const drafts = proposals.filter(p => p.status === 'draft' && !linked(state?.commands, p).length);
  if (drafts.length) attention.push(`${drafts.length} saved draft order(s) await review.`);
  if (state?.portfolio_model?.status === 'failed') attention.push('The latest model proposal failed.');
  const runs = arr(state?.runs), latest = symbol => runs.find(r => arr(r.symbols).includes(symbol));
  if (!state) return <Page title="Dashboard"><Typography>Loading…</Typography></Page>;
  return <Page tabbed title="Dashboard" subtitle="Account, holdings, orders and what needs attention.">
    <Ledger/>
    {attention.length > 0 ? <Notice>{attention.join(' ')}</Notice> : <Notice severity="success">Nothing needs attention.</Notice>}
    <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable">
      {[['watch', 'Watch'], ['chart', 'Chart'], ['research', 'Research'], ['positions', 'Positions'], ['orders', 'Orders']].map(([v, l]) => <Tab key={v} value={v} label={l}/>)}
    </Tabs>
    <Box role="tabpanel" hidden={tab !== 'watch'}><Stack spacing={1} sx={{height: '100%', minHeight: 0}}>
      <DataTable fill rows={watch} getRowId={r => r.symbol} onRowClick={open} selectedIds={new Set(selectedSymbol ? [selectedSymbol] : [])}
        empty="No stocks in the saved universe."
        columns={[{id: 'symbol', label: 'Symbol'}, {id: 'price', label: 'Last', numeric: true, render: r => money(r.price)},
          {id: 'held', label: 'Held', type: 'boolean', value: r => f.coverage('positions') ? held.has(r.symbol) : null, render: r => f.coverage('positions') ? held.has(r.symbol) ? 'Yes' : 'No' : 'Unknown'}]}/>
    </Stack></Box>
    <Box role="tabpanel" hidden={tab !== 'chart'}><DashboardChart symbol={selectedSymbol} active={page === 'overview' && tab === 'chart'}/></Box>
    <Box role="tabpanel" hidden={tab !== 'research'}><Stack spacing={1}>
      {selectedSymbol ? (latest(selectedSymbol) ? <Fact label={`Latest saved research for ${selectedSymbol}`} value={`${text(latest(selectedSymbol).id)} · ${dateTime(latest(selectedSymbol).created_at)}`}/>
        : <Typography>No saved research for {selectedSymbol}.</Typography>) : <Typography>Select a stock in Watch.</Typography>}
      <Button sx={{alignSelf: 'flex-start'}} onClick={() => navigate('research')}>Open Research</Button>
    </Stack></Box>
    <Box role="tabpanel" hidden={tab !== 'positions'}><PositionsTable fill onSelect={open}/></Box>
    <Box role="tabpanel" hidden={tab !== 'orders'}><Stack spacing={1}>
      <OrdersTable/>
      <DataTable rows={drafts} getRowId={p => p.id} empty="No saved drafts."
        columns={[{id: 't', label: 'Draft', value: p => `${text(p.terms?.side)} ${text(p.terms?.quantity)} ${text(p.terms?.symbol)} · revision ${p.revision}`},
          {id: 'open', label: '', render: p => <Button size="small" onClick={() => {setSelectedSymbol(p.terms?.symbol); navigate('orders', {tab: 'ticket', symbol: p.terms?.symbol, proposal_id: p.id, proposal_revision: p.revision, terms: p.terms});}}>Open exact draft</Button>}]}/>
    </Stack></Box>
  </Page>;
}

/* ---------------------------------------------------------------- Portfolio */

const UNITS = 1e8, TOTAL_UNITS = 100 * UNITS;
// Exact percent -> integer units with at most eight decimals, as the legacy allocation draft parsed it.
function allocationUnits(value) {
  const match = /^(\d+)(?:\.(\d{0,8}))?$/.exec(String(value ?? '').trim() || '0');
  if (!match) throw new Error('Enter allocation percentages with up to eight decimal places.');
  const n = Number(match[1]) * UNITS + Number((match[2] || '').padEnd(8, '0'));
  if (!Number.isSafeInteger(n) || n > TOTAL_UNITS) throw new Error('Each allocation must be between 0% and 100%.');
  return n;
}
const safeUnits = v => { try { return allocationUnits(v); } catch { return null; } };

function Allocations() {
  const {state, api, navigate, page} = useDesk();
  const universe = arr(state?.config?.universe);
  const asOf = state?.portfolio_model?.as_of;
  const [draft, setDraft] = useState({capital: '100000', start: '', end: '', fee: '', weights: {}, spy: null});
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [status, setStatus] = useState(''), [result, setResult] = useState(null);
  const symbols = draft.spy ? Object.keys(draft.spy.weights) : universe;
  const end = draft.end || (asOf ? String(asOf).slice(0, 10) : ''), start = draft.start || (end ? `${Number(end.slice(0, 4)) - 1}-12-31` : '');
  const parsed = symbols.map(s => safeUnits(draft.weights[s]));
  const bad = parsed.some(v => v === null);
  const total = parsed.reduce((s, v) => s + (v ?? 0), 0);
  const patch = p => setDraft(d => ({...d, ...p}));
  const load = async action => {
    try {
      const r = await api('/api/evaluations', {action});
      patch({spy: r, weights: {...r.weights}, start: '2025-12-31', end: '2026-11-04'}); setError('');
    } catch (e) { setError(e.message); }
  };
  const equal = () => {
    const each = Math.floor(TOTAL_UNITS / universe.length), rem = TOTAL_UNITS % universe.length;
    patch({spy: null, weights: Object.fromEntries(universe.map((s, i) => [s, ((each + (i < rem ? 1 : 0)) / UNITS).toFixed(8)]))});
  };
  const scenario = () => {
      if (bad) throw new Error('Enter allocation percentages with up to eight decimal places.');
      if (total > TOTAL_UNITS) throw new Error('Allocations exceed 100%.');
      if (!parsed.some(v => v > 0)) throw new Error('Allocate at least one stock before simulating.');
      if (!start || !end || start >= end) throw new Error('Choose a start date before the end date.');
      const model = {id: crypto.randomUUID(), name: draft.spy ? (draft.spy.weights.SGOV ? 'SPY holdings and SGOV' : 'SPY holdings') : 'Portfolio allocations',
        inputs: symbols.map(symbol => ({symbol})),
        result: {capital: draft.capital, allocations: symbols.map((symbol, i) => ({symbol, weight: (parsed[i] / TOTAL_UNITS).toFixed(10)})),
          target_cash_weight: ((TOTAL_UNITS - total) / TOTAL_UNITS).toFixed(10)}};
      if (draft.spy) model.holdings_source = draft.spy.action;
      return {action: 'portfolio_scenario', model, start, end, fee_usd: draft.fee};
  };
  const openScenario = () => {
    try { navigate('strategy', {...scenario(), kind: 'portfolio_scenario'}); }
    catch (failure) { setError(failure.message); }
  };
  const simulate = async () => {
    try {
      const request = scenario();
      setBusy(true); setError(''); setResult(null); setStatus('Preparing the simulation from saved daily prices…');
      let r = await api('/api/evaluations', request, {timeoutMs: 900000});
      while (r.status === 'collecting') {
        setStatus(r.message || 'Collecting saved daily prices…');
        request.collection = r.collection;
        await new Promise(resolve => setTimeout(resolve, 2000));
        r = await api('/api/evaluations', request, {timeoutMs: 900000});
      }
      setResult(r); setStatus(`Simulation ${r.id} · ${r.status}`);
    } catch (e) { setError(e.message); setStatus(''); } finally { setBusy(false); }
  };
  return <Section title="Portfolio allocations">
    <Typography variant="body2">Weights up to 8 decimals; unallocated capital stays in cash. The simulation runs on saved daily prices; it places no orders.</Typography>
    {draft.spy && <Notice severity="info">{text(draft.spy.source)} · holdings as of {text(draft.spy.as_of)}</Notice>}
    {error && <Notice>{error}</Notice>}
    <Grid container spacing={1}>
      <Grid size={{xs: 6, md: 3}}><Field label="Capital / USD" value={draft.capital} onChange={v => patch({capital: v})} type="number"/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="Start date" value={start} onChange={v => patch({start: v})} type="date" slotProps={{inputLabel: {shrink: true}}}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="End date" value={end} onChange={v => patch({end: v})} type="date" slotProps={{inputLabel: {shrink: true}}}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="Fee per order / USD" value={draft.fee} onChange={v => patch({fee: v})} type="number"/></Grid>
    </Grid>
    <Stack direction="row" spacing={1} useFlexGap  sx={{flexWrap: "wrap"}}>
      <Button variant="contained" disabled={busy || page !== 'portfolio'} onClick={simulate}>Run historical simulation</Button>
      <Button disabled={busy} onClick={openScenario}>Open allocation setup in Strategy Lab</Button>
      <Button onClick={() => load('spy_year_start_stocks')}>Load year-start SPY weights (100% stocks)</Button>
      <Button onClick={() => load('spy_year_start')}>Load year-start SPY weights (90% stocks)</Button>
      <Button onClick={() => load('spy_october')}>Load October SPY weights</Button>
      {draft.spy ? <Button onClick={() => patch({spy: null, weights: {}})}>Use saved list</Button> : <>
        <Button onClick={equal} disabled={!universe.length}>Equal weight</Button><Button onClick={() => patch({weights: {}})}>Clear weights</Button></>}
    </Stack>
    <Typography color={total > TOTAL_UNITS || bad ? 'error' : 'text.primary'} role="status">
      {bad ? 'A weight is not a valid percentage.' : `Allocated ${(total / UNITS).toFixed(8)}% · cash target ${((TOTAL_UNITS - total) / UNITS).toFixed(8)}%`}</Typography>
    {status && <Typography role="status">{status}</Typography>}
    {result && <Stack direction="row" spacing={1}><Evidence title="Simulation result" data={result}/>
      <Button onClick={() => navigate('strategy', {tab: 'simulations', view: 'results', simulation_id: result.id})}>Open in Strategy Lab</Button></Stack>}
    <DataTable rows={symbols} getRowId={s => s} empty="No stocks in the saved universe."
      columns={[{id: 's', label: 'Stock', value: s => s}, {id: 'w', label: 'Allocation %', numeric: true, value: s => draft.weights[s],
        render: s => <TextField size="small" type="number" value={draft.weights[s] ?? ''} disabled={Boolean(draft.spy)} slotProps={{htmlInput: {min: 0, max: 100, step: 0.00000001, 'aria-label': `${s} allocation percent`}}}
          onChange={e => setDraft(d => ({...d, weights: {...d.weights, [s]: e.target.value}}))}/>}]}/>
  </Section>;
}


function ProposedModel() {
  const {state, act} = useDesk();
  const m = state?.portfolio_model, r = m?.result;
  const [capital, setCapital] = useState('10000'), [asOf, setAsOf] = useState('');
  const running = ['queued', 'running'].includes(m?.status);
  const start = () => act('portfolio-model', '/api/portfolio-model', {request_id: crypto.randomUUID(), capital, as_of: asOf || null}).catch(() => {});
  return <Section title="Model proposal">
    <Typography variant="body2">One joint synthesis of eligible latest research and cached dated prices. Session-only: it creates no baskets, orders or approvals.</Typography>
    <Grid container spacing={2}>
      <Grid size={{xs: 12, md: 3}}><Field label="Model capital / USD" value={capital} onChange={setCapital} type="number"/></Grid>
      <Grid size={{xs: 12, md: 3}}><Field label="Price date (optional)" value={asOf} onChange={setAsOf} type="date" slotProps={{inputLabel: {shrink: true}}}/></Grid>
      <Grid size={{xs: 12, md: 3}}><Button variant="contained" disabled={running || !(Number(capital) > 0)} onClick={start}>Generate proposal</Button></Grid>
    </Grid>
    {m && <Stack direction="row" spacing={2}  sx={{alignItems: "center"}}><Status value={m.status}/><Typography>{text(m.provider)} {text(m.model)} · as of {text(m.as_of)}</Typography></Stack>}
    {m?.error && <Notice severity="error">{text(m.error)}</Notice>}
    {arr(m?.exclusions).length > 0 && <Notice severity="info">{m.exclusions.length} research input(s) were excluded; see source details.</Notice>}
    {r && <>
      <Grid container spacing={2}>
        {[['Capital', money(r.capital)], ['Reference value', money(r.reference_value)], ['Cash', money(r.cash)], ['Target cash', number(r.target_cash_weight) === null ? 'Unavailable' : pct(Number(r.target_cash_weight) * 100)]]
          .map(([l, v]) => <Grid key={l} size={{xs: 6, md: 3}}><Fact label={l} value={v}/></Grid>)}
      </Grid>
      <DataTable rows={arr(r.allocations)} getRowId={a => a.symbol} empty="No allocations."
        columns={[{id: 'symbol', label: 'Symbol'}, {id: 'weight', label: 'Weight %', numeric: true, value: a => number(a.weight) === null ? null : Number(a.weight) * 100, render: a => number(a.weight) === null ? 'Unavailable' : pct(Number(a.weight) * 100)},
          {id: 'shares', label: 'Shares', numeric: true, render: a => text(a.shares)},
          {id: 'ref', label: 'Reference', numeric: true, value: a => a.reference?.price, render: a => `${money(a.reference?.price)}${a.reference?.stale ? ' (stale)' : ''}`},
          {id: 'last', label: 'Last vs reference', numeric: true, value: a => {
            const last = number(state?.quotes?.[a.symbol]?.price), ref = number(a.reference?.price);
            return last === null || ref === null || ref === 0 ? null : (last / ref - 1) * 100;
          }, render: a => {
            const last = number(state?.quotes?.[a.symbol]?.price), ref = number(a.reference?.price);
            return last === null || ref === null || ref === 0 ? 'Unavailable' : pct((last / ref - 1) * 100);
          }},
          {id: 'why', label: 'Rationale', value: a => a.rationale}]}/>
      {r.cash_rationale && <Typography>{r.cash_rationale}</Typography>}
      <Evidence title="Bindings, trace and exclusions" data={{inputs: m.inputs, exclusions: m.exclusions, system_prompt: r.system_prompt}}/>
    </>}
  </Section>;
}

function Holdings() {
  const {api, page} = useDesk();
  const [message, setMessage] = useState('');
  const exportCsv = async () => {
    try {
      const rec = await api('/api/reporting');
      const r = await api('/api/reporting', {action: 'export_csv', kind: 'holdings', symbols: [], expected_revision: rec.revision});
      const url = URL.createObjectURL(new Blob([r.csv], {type: 'text/csv'}));
      const a = document.createElement('a'); a.href = url; a.download = r.filename || 'holdings.csv'; a.click(); URL.revokeObjectURL(url);
      setMessage('Export ready.');
    } catch (e) { setMessage(e.message); }
  };
  return <Stack spacing={1} sx={{height: '100%', minHeight: 0}}>
    <PositionsTable fill onSelect={undefined}/>
    <Stack direction="row" spacing={1} sx={{alignItems: "center", flexShrink: 0}}><Button onClick={exportCsv} disabled={page !== 'portfolio'}>Export holdings CSV</Button><Typography>{message}</Typography></Stack>
  </Stack>;
}

function Tile({label, metric, field, benchmarkOnly}) {
  const calculable = benchmarkOnly ? metric?.benchmark_price_return_calculable === true : metric?.calculable === true;
  const value = calculable ? number(metric?.[field]) : null;
  const reasons = arr(metric?.readiness_reasons).length ? metric.readiness_reasons : [metric?.reason].filter(Boolean);
  return <Stack spacing={0.5} sx={{p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1, height: '100%'}}>
    <Typography variant="caption" color="text.secondary">{label}</Typography>
    <Typography variant="h3" sx={{fontSize: 20}}>{value === null ? 'Unavailable' : pct(value * 100)}</Typography>
    <Typography variant="body2">{benchmarkOnly ? 'Benchmark-only price return; does not establish excess or strategy return.' : metric?.available === true ? 'Calculated from covered inputs' : calculable ? 'Unsupported source method' : 'Not calculable'}</Typography>
    <Typography variant="body2">{metric?.provisional === true ? 'Provisional' : metric?.provisional === false ? 'Not provisional' : 'Provisional status unreported'}</Typography>
    <Typography variant="body2" color="text.secondary">{reasons.join('; ') || 'No readiness reason recorded.'}</Typography>
  </Stack>;
}

function Plot({points, returns}) {
  const data = points.map(p => ({v: number(returns ? p.broker_profit_loss_pct : p.equity), t: p.timestamp})).filter(p => p.v !== null);
  if (data.length < 2) return <Notice severity="info">Not enough saved {returns ? 'return' : 'equity'} observations. Missing observations are not estimated.</Notice>;
  const w = 800, h = 280, L = 12, R = 100, T = 20, B = 32, lo = Math.min(...data.map(p => p.v)), hi = Math.max(...data.map(p => p.v));
  const pad = Math.max((hi - lo) * .1, returns ? 0.0001 : 1), min = lo - pad, max = hi + pad;
  const x = i => L + i / (data.length - 1) * (w - L - R), y = v => T + (max - v) / (max - min) * (h - T - B);
  const fmt = v => returns ? pct(v * 100) : money(v), day = t => new Date(t * 1000).toISOString().slice(0, 10);
  return <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={returns ? 'Broker-reported P/L fraction' : 'Broker-reported account equity'} style={{width: '100%', maxHeight: 320}}>
    {[0, .5, 1].map(fr => { const v = min + (max - min) * fr; return <g key={fr}><line x1={L} x2={w - R} y1={y(v)} y2={y(v)} stroke="#1f2b38"/><text x={w - R + 8} y={y(v) + 4} fill="#cdd6df" fontSize="11">{fmt(v)}</text></g>; })}
    <path d={data.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.v)}`).join(' ')} fill="none" stroke="#3ecf8e" strokeWidth="2"/>
    <text x={L} y={h - 5} fill="#cdd6df" fontSize="11">{day(data[0].t)}</text><text x={w - R} y={h - 5} textAnchor="end" fill="#cdd6df" fontSize="11">{day(data.at(-1).t)}</text>
  </svg>;
}

function Performance({active}) {
  const {api} = useDesk();
  const [record, setRecord] = useState(null), [error, setError] = useState(''), [id, setId] = useState(''), [saved, setSaved] = useState(null), [loading, setLoading] = useState(false);
  const [view, setView] = useState('equity'), [symbols, setSymbols] = useState(''), [message, setMessage] = useState('');
  const loadRecords = useCallback(() => api('/api/reporting').then(r => { setRecord(r); setError(''); }).catch(e => setError(e.message)), [api]);
  useEffect(() => { if (active && !record) loadRecords(); }, [active, record, loadRecords]);
  const open = async () => {
    setLoading(true); setSaved(null); setError('');
    try {
      const data = await api(`/api/reporting/collections/${encodeURIComponent(id)}`);
      if (data.id !== id) throw new Error('History collection identity differs');
      setSaved(data);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };
  const exportCsv = async kind => {
    try {
      const r = await api('/api/reporting', {action: 'export_csv', kind, collection_id: id,
        ...(kind === 'activity' && symbols.trim() ? {symbols: symbols.toUpperCase().split(/[\s,]+/).filter(Boolean)} : {})});
      const url = URL.createObjectURL(new Blob([r.csv], {type: 'text/csv;charset=utf-8'}));
      const a = document.createElement('a'); a.href = url; a.download = r.filename || `${kind}.csv`; a.click(); URL.revokeObjectURL(url);
      setMessage(`${kind} export ready.`);
    } catch (e) { setMessage(e.message); }
  };
  const collections = arr(record?.data?.collections), points = arr(saved?.points), flows = arr(saved?.external_flows);
  return <Section title="Performance">
    <Typography variant="body2">Reads saved account-history intervals only; no broker history is collected here. Collect history in Journal.</Typography>
    {error && <Notice severity="error">{error} <Button size="small" onClick={loadRecords}>Retry saved reporting records</Button></Notice>}
    <Stack direction="row" spacing={1}  useFlexGap  sx={{alignItems: "center", flexWrap: "wrap"}}>
      <Box sx={{minWidth: 320}}><Pick label="Saved interval" value={id} onChange={v => {setId(v); setSaved(null);}}
        options={[['', 'Choose'], ...collections.map(c => [c.id, `${c.requested_start} to ${c.requested_end} · ${c.collected_at}`])]}/></Box>
      <Button variant="contained" disabled={!id || loading} onClick={open}>Open saved interval</Button>
      <Pick label="Chart" value={view} onChange={setView} options={[['equity', 'Equity'], ['returns', 'Returns']]} sx={{maxWidth: 150}}/>
    </Stack>
    {!record && !error && <Typography role="status">Loading saved account-history intervals…</Typography>}
    {record && collections.length === 0 && <Notice severity="info">No saved intervals. Collect account history in Journal to get started.</Notice>}
    {saved && <>
      <Grid container spacing={1}>
        {[['Time-weighted return', saved.time_weighted, 'return'], ['Modified Dietz estimate', saved.dietz, 'estimate'], ['Drawdown', saved.drawdown, 'value'],
          ['Benchmark price return', saved.benchmark_comparison, 'benchmark_price_return', true], ['Excess return', saved.benchmark_comparison, 'excess_return']]
          .map(([label, metric, field, b]) => <Grid key={label} size={{xs: 12, md: 4}}><Tile label={label} metric={metric} field={field} benchmarkOnly={b}/></Grid>)}
      </Grid>
      <Typography variant="body2">{view === 'returns' ? saved.raw_broker_percent_method || 'Broker-reported P/L fraction; no adjusted return inferred.' : `Broker-reported equity · ${saved.currency || 'Currency unavailable'}`}</Typography>
      {points.length < 2 ? <Notice severity="info">Needs at least two saved account-history observations.</Notice> : <Plot points={points} returns={view === 'returns'}/>}
      <Evidence title={`Recorded equity and P/L data (${points.length})`} data={points}/>
      <Typography variant="h3" sx={{fontSize: 16}}>External capital flows</Typography>
      <Typography variant="body2">Deposits and withdrawals are external capital; dividends and fees remain separate.</Typography>
      <DataTable rows={flows} getRowId={r => r.id ?? r.source_id ?? JSON.stringify(r)} empty="No external-flow records in this collection; completeness remains subject to its recorded method and coverage."
        columns={[{id: 'i', label: 'Source identity', value: r => r.id ?? r.source_id}, {id: 't', label: 'Time / date', type: 'dateTime', value: r => r.at ?? r.time ?? r.date},
          {id: 'a', label: 'Amount / currency', numeric: true, value: r => r.amount, render: r => `${text(r.amount)} ${r.currency ?? saved.currency ?? 'Currency unavailable'}`}]}/>
      <Evidence title="Source, calculation methods and coverage" data={saved}/>
      <Stack direction="row" spacing={1}  useFlexGap  sx={{alignItems: "center", flexWrap: "wrap"}}>
        <Field label="Activity export symbols (blank = full account)" value={symbols} onChange={setSymbols} sx={{maxWidth: 320}}/>
        {['holdings', 'activity', 'performance'].map(k => <Button key={k} onClick={() => exportCsv(k)}>Export {k} CSV</Button>)}
        <Typography>{message}</Typography>
      </Stack>
    </>}
  </Section>;
}

export function PortfolioView() {
  const {state, page} = useDesk();
  const [tab, setTab] = useState('positions');
  if (!state) return <Page title="Portfolio"><Typography>Loading…</Typography></Page>;
  return <Page tabbed title="Portfolio" subtitle="Holdings, allocations, model proposal and performance.">
    <Ledger/>
    <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable">
      {[['positions', 'Positions'], ['allocations', 'Allocations'], ['model', 'Model proposal'], ['performance', 'Performance']].map(([v, l]) => <Tab key={v} value={v} label={l}/>)}
    </Tabs>
    <Box role="tabpanel" hidden={tab !== 'positions'}><Holdings/></Box>
    <Box role="tabpanel" hidden={tab !== 'allocations'}><Allocations/></Box>
    <Box role="tabpanel" hidden={tab !== 'model'}><ProposedModel/></Box>
    <Box role="tabpanel" hidden={tab !== 'performance'}><Performance active={page === 'portfolio' && tab === 'performance'}/></Box>
  </Page>;
}

/* ---------------------------------------------------------------- Orders */

const emptyTicket = {id: undefined, symbol: '', side: '', quantity: '', order_type: 'LIMIT', limit_price: '', stop_price: '', time_in_force: 'DAY', session: 'regular', rationale: ''};
const clean = t => Object.fromEntries(Object.entries(t).filter(([, v]) => v !== '' && v !== undefined));
const EVIDENCE_SCOPES = ['history', 'news', 'corporate_actions', 'earnings', 'fundamentals', 'classification'];

function Ticket({active}) {
  const {state, api, act, refresh, page, selectedSymbol, navigation, clearNavigation} = useDesk();
  const investor = state?.investor, f = useFacts();
  const optionEnvelope = symbol => state?.nautilus?.market_data?.[symbol]?.option_contract || investor?.instruments?.[symbol]?.option_contract;
  const [ticket, setTicket] = useState(() => ({...emptyTicket, symbol: selectedSymbol || ''}));
  const [incoming, setIncoming] = useState(null);
  const [chartOpen, setChartOpen] = useState(false);
  const ticketDirty = useRef(false);
  const loadIntent = intent => {
    const {kind, symbol, terms, research, symbols} = intent;
    if (kind === 'option-package') {
      const underlying = optionEnvelope(arr(symbols)[0])?.raw?.underlying_symbol;
      if (!underlying) {
        setMessage('Observe the selected option contracts before preparing their package. The requested symbols have been retained.');
        setIncoming(intent);
        return;
      }
        setTicket({...emptyTicket, symbol: underlying, asset_class: 'us_option', order_class: 'mleg', execution_profile: '', currency: 'USD', side: 'BUY', order_type: 'LIMIT',
          net_direction: 'debit', session: 'regular', legs: arr(symbols).map((s, i) => ({id: `${Date.now()}-${i}`, symbol: s, position_intent: 'buy_to_open', side: 'BUY', ratio_qty: '1'}))});
    } else if (symbol) {
      setTicket({...emptyTicket, ...(terms || {}), symbol, research: research || null, quantity: terms?.quantity ?? terms?.qty ?? '', order_type: terms?.order_type || terms?.type || 'LIMIT'});
    }
    ticketDirty.current = false;
    setScopes(arr(terms?.decision_evidence_scopes)); setReason(''); setPreview(null); setIncoming(null);
  };
  useEffect(() => {
    const kind = navigation?.intent?.kind;
    if (!navigation || navigation.page !== 'orders' || (navigation.intent?.tab !== 'ticket' && kind !== 'option-ticket' && kind !== 'option-package')) return;
    if (ticketDirty.current) setIncoming(navigation.intent); else loadIntent(navigation.intent);
    clearNavigation(navigation.id);
  }, [navigation, clearNavigation]);
  const [reason, setReason] = useState(''), [scopes, setScopes] = useState([]);
  const [preview, setPreview] = useState(null), [message, setMessage] = useState('');
  const set = k => v => { ticketDirty.current = true; setTicket(t => ({...t, [k]: v})); setPreview(null); };
  const instrument = investor?.instruments?.[ticket.symbol];
  const profiles = investor?.option_execution_profiles || {};
  const isMleg = ticket.order_class === 'mleg';
  const optionContract = optionEnvelope(ticket.symbol);
  const type = ticket.order_type, held = vals(state?.positions).find(p => p.symbol === ticket.symbol && p.side === 'long' && number(p.qty) > 0);
  const replaceable = vals(state?.nautilus?.orders).filter(o => o.symbol === ticket.symbol &&
    ['new', 'accepted', 'partially_filled', 'pending_new', 'held', 'done_for_day'].includes(String(o.status).toLowerCase()) &&
    (investor?.broker_order_actions?.[o.id]?.replace_supported ?? investor?.broker_order_actions?.[o.id]?.supported));
  const target = ticket.replacement?.order_id ? replaceable.find(o => o.id === ticket.replacement.order_id) : null;
  const fixedLinked = !!(target && (target.group_parent_id || ['bracket', 'oto', 'oco'].includes(target.group_class)));
  const pickReplacement = id => {
    const o = replaceable.find(x => x.id === id);
    ticketDirty.current = true; setPreview(null);
    setTicket(t => o ? {...t, replacement: {order_id: id}, side: String(o.side).toUpperCase(), order_type: o.type === 'stop' ? 'STOP_MARKET' : String(o.type).toUpperCase(),
      stop_price: o.stop_price ?? '', quantity: o.qty ?? '', limit_price: o.limit_price ?? '', time_in_force: String(o.time_in_force || 'day').toUpperCase(), session: o.extended_hours ? 'extended' : 'regular', tp: '', sl: '', sll: '', trail_price: '', trail_percent: ''}
      : {...t, replacement: undefined});
  };
  const exitTicket = next => next.exitMode ? {...next,
    order_type: next.tp ? 'LIMIT' : next.sll ? 'STOP_LIMIT' : next.sl ? 'STOP_MARKET' : '',
    limit_price: next.tp || next.sll || '', stop_price: next.tp ? '' : next.sl || ''} : next;
  const setExit = k => v => {
    ticketDirty.current = true; setPreview(null);
    setTicket(t => exitTicket({...t, [k]: v}));
  };
  const seed = trailing => {
    ticketDirty.current = true; setPreview(null);
    setTicket(t => ({...emptyTicket, symbol: t.symbol, side: 'SELL', order_type: trailing ? 'TRAILING_STOP_MARKET' : '', exitMode: !trailing}));
  };
  const planned = [ticket.tp, ticket.sl, ticket.sll].some(v => v !== '' && v !== undefined);
  const wholeQty = /^(0|[1-9]\d{0,17})(\.0{1,9})?$/.test(String(ticket.quantity)) && number(ticket.quantity) > 0;
  const profile = profiles[ticket.execution_profile];
  const legs = arr(ticket.legs);
  const issue = (() => {
    if (isMleg) {
      if (!profile) return 'Choose an execution profile.';
      if (legs.length < 2 || legs.length > 4 || new Set(legs.map(l => l.symbol)).size !== legs.length) return 'A package needs 2 to 4 distinct option legs.';
      if (!wholeQty || legs.some(l => !/^[1-9]\d{0,17}$/.test(String(l.ratio_qty)))) return 'Units and leg ratios must be whole positive numbers.';
      const gcd = (a, b) => b ? gcd(b, a % b) : a;
      if (legs.map(l => Number(l.ratio_qty)).reduce(gcd) !== 1) return 'Leg ratios must be in lowest terms.';
      if (legs.some(l => !l.position_intent || !arr(profile.intents).includes(l.position_intent))) return 'Every leg needs an intent this profile allows.';
      const raw = l => optionEnvelope(l.symbol)?.raw;
      if (legs.some(l => raw(l)?.underlying_symbol !== ticket.symbol)) return 'Every leg needs an observed contract on this underlying.';
      if (profile.same_expiry && new Set(legs.map(l => raw(l)?.expiration_date)).size !== 1) return 'This profile requires one observed expiration on every leg.';
      if (type === 'LIMIT' && !(number(ticket.limit_price) !== null && number(ticket.limit_price) !== 0 && (number(ticket.limit_price) > 0) === (ticket.net_direction !== 'credit'))) return 'Enter a nonzero signed net price: positive for debit, negative for credit.';
      if (!arr(profile.order_types).includes(type) || !arr(profile.time_in_force).includes(ticket.time_in_force)) return 'The profile does not support this order type or duration.';
      return '';
    }
    if (optionContract) {
      const durations = arr(instrument?.option_order_profiles?.[type]);
      if (!ticket.position_intent) return 'Choose the option position intent.';
      if (!durations.length || !durations.includes(ticket.time_in_force)) return 'Order type or duration is not offered for this contract.';
      if (!/^[1-9]\d{0,17}(\.0{1,9})?$/.test(String(ticket.quantity))) return 'Contracts must be whole.';
      if (ticket.session === 'extended') return 'Options trade in the regular session only.';
    }
    if (type === 'STOP_MARKET' && ticket.side === 'BUY') return 'Stop-market buy orders are unavailable.';
    if (!type) return 'Enter an exit price to derive the order type.';
    if (type === 'TRAILING_STOP_MARKET') {
      if (ticket.side !== 'SELL' || !held || ticket.session === 'extended' || ticket.replacement || planned) return 'Trailing stops need a SELL of a held long position in the regular session.';
      if (!wholeQty) return 'Trailing stops need a whole share quantity.';
      if (!!ticket.trail_price === !!ticket.trail_percent) return 'Enter exactly one of a trail amount or a trail percent.';
    }
    if (ticket.session === 'extended') {
      if (type !== 'LIMIT' || planned || (String(ticket.quantity).includes('.') && ticket.time_in_force !== 'DAY')) return 'Extended session allows simple limit orders; fractional ones must be Day.';
      if (String(ticket.quantity).includes('.') && state?.nautilus?.market_data?.[ticket.symbol]?.session_eligibility?.fractional_eh_enabled !== true) return 'Fractional extended-session trading is not enabled for this symbol.';
    }
    if (planned && ticket.replacement) return 'A linked exit plan cannot be replaced.';
    if (ticket.sll && !ticket.sl) return 'Enter a stop trigger for the stop limit.';
    if (planned && ticket.side === 'BUY' && !['MARKET', 'LIMIT'].includes(type)) return 'Exit plans attach to market or limit buys.';
    return '';
  })();
  const terms = () => {
    const {tp, sl, sll, exitMode, legs: _l, ...rest} = ticket;
    const out = {...clean(rest), time_in_force: ticket.time_in_force || 'DAY', decision_evidence_scopes: scopes};
    if (isMleg) out.legs = legs.map(l => ({...l, side: l.position_intent.startsWith('buy') ? 'BUY' : 'SELL'}));
    if (type === 'MARKET' || type === 'STOP_MARKET' || type === 'TRAILING_STOP_MARKET') delete out.limit_price;
    if (!['STOP_MARKET', 'STOP_LIMIT'].includes(type)) delete out.stop_price;
    if (type === 'TRAILING_STOP_MARKET') { delete out.stop_price; } else { delete out.trail_price; delete out.trail_percent; }
    if (tp && sl) out.exit_plan = clean({take_profit: tp, stop_price: sl, stop_limit_price: sll});
    return out;
  };
  const copyFields = [];
  if (!isMleg) {
    if (!ticket.exitMode && ['LIMIT', 'STOP_LIMIT'].includes(type)) copyFields.push(['limit_price', 'Entry / existing order limit']);
    if (['STOP_MARKET', 'STOP_LIMIT'].includes(type)) copyFields.push(['stop_price', 'Existing stop trigger']);
    if (terms().exit_plan && ticket.session === 'regular' && !ticket.replacement)
      copyFields.push(['exit_plan.take_profit', 'Linked profit target'], ['exit_plan.stop_price', 'Linked protective trigger'], ['exit_plan.stop_limit_price', 'Linked protective stop limit']);
  }
  const applyChartCopy = (copy, {symbol}) => {
    const fields = copy.fields || {[copy.field]: copy.value};
    if (symbol !== ticket.symbol || !copy.price_ref || !copyFields.some(([key]) => key === copy.field) ||
        Object.keys(fields).some(field => !copyFields.some(([key]) => key === field))) {
      setMessage('The historical price destination no longer matches this ticket. Review it again.');
      return;
    }
    ticketDirty.current = true;
    setTicket(current => {
      const next = {...current};
      const exits = {'exit_plan.take_profit': 'tp', 'exit_plan.stop_price': 'sl', 'exit_plan.stop_limit_price': 'sll'};
      for (const [field, value] of Object.entries(fields))
        next[exits[field] || (next.exitMode && field === 'stop_price' ? 'sl' : field)] = value;
      next.price_references = [...arr(current.price_references).filter(ref =>
        !Object.keys(ref.fields || {[ref.destination]: null}).some(field => field in fields)), copy.price_ref];
      return exitTicket(next);
    });
    setPreview(null);
    setMessage('Historical price copied into the manual ticket. Preview and save its exact revision separately.');
  };
  const run = action => async () => {
    setMessage('');
    try {
      const r = await act(`proposal-${action}`, '/api/investor', {action, id: ticket.id, terms: terms(), reason, expected_revision: investor.revision});
      if (action === 'preview') setPreview(r?.preview ?? null);
      else { setPreview(null); if (action !== 'draft') setTicket(emptyTicket); }
    } catch { /* act reports the error */ }
  };
  const needs = ['stop_market', 'stop_limit'].includes(ticket.order_type.toLowerCase());
  const price = number(state?.quotes?.[ticket.symbol]?.price), qty = number(ticket.quantity), lim = number(ticket.limit_price);
  const notional = qty !== null && (lim ?? price) !== null ? qty * (lim ?? price) : null;
  const equity = number(state?.account?.equity);
  return <Section title="Order ticket">
    <Typography variant="body2">A local human proposal. Saving creates no broker order and grants no approval; approval and submission are separate steps.</Typography>
    {issue && <Notice>{issue}</Notice>}
    {ticket.symbol && !instrument?.supported && <Notice>{text(instrument?.limitation ?? 'No current eligible asset observation; preview and save are disabled.')}</Notice>}
    <Grid container spacing={2}>
      <Grid size={{xs: 6, md: 2}}><Field label="Symbol" value={ticket.symbol} onChange={v => set('symbol')(v.toUpperCase())}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Pick label="Side" disabled={fixedLinked || isMleg} value={ticket.side} onChange={v => { set('side')(v); setTicket(t => ({...t, tp: '', sl: '', sll: ''})); }} options={['BUY', 'SELL']}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Field label={isMleg ? 'Strategy units' : optionContract ? 'Contracts' : 'Shares'} disabled={fixedLinked} value={ticket.quantity} onChange={set('quantity')}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Pick label="Order type" disabled={fixedLinked || (isMleg && !!ticket.replacement)} value={ticket.order_type} onChange={set('order_type')}
        options={isMleg ? arr(profile?.order_types) : ['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT', 'TRAILING_STOP_MARKET']}/></Grid>
      {['LIMIT', 'STOP_LIMIT'].includes(type) && <Grid size={{xs: 6, md: 2}}><Field label={isMleg ? 'Net premium / USD (credit negative)' : 'Limit price / USD'} value={ticket.limit_price} onChange={set('limit_price')}/></Grid>}
      {needs && <Grid size={{xs: 6, md: 2}}><Field label="Stop trigger / USD" value={ticket.stop_price} onChange={set('stop_price')}/></Grid>}
      {type === 'TRAILING_STOP_MARKET' && <><Grid size={{xs: 6, md: 2}}><Field label="Trail amount / USD" value={ticket.trail_price} onChange={set('trail_price')}/></Grid>
        <Grid size={{xs: 6, md: 2}}><Field label="Trail percent" value={ticket.trail_percent} onChange={set('trail_percent')}/></Grid></>}
      {optionContract && !isMleg && <Grid size={{xs: 6, md: 2}}><Pick label="Position intent" value={ticket.position_intent || ''} onChange={v => { set('position_intent')(v); setTicket(t => ({...t, side: v === 'buy_to_open' ? 'BUY' : 'SELL', asset_class: 'us_option', currency: 'USD'})); }}
        options={[['', 'Choose'], ['buy_to_open', 'Buy to open'], ['sell_to_close', 'Sell to close']]}/></Grid>}
      {!optionContract && !isMleg && type !== 'TRAILING_STOP_MARKET' && !ticket.replacement && <>
        <Grid size={{xs: 6, md: 2}}><Field label="Take profit / USD" value={ticket.tp || ''} onChange={setExit('tp')}/></Grid>
        <Grid size={{xs: 6, md: 2}}><Field label="Exit stop / USD" value={ticket.sl || ''} onChange={setExit('sl')}/></Grid>
        <Grid size={{xs: 6, md: 2}}><Field label="Exit stop limit / USD" value={ticket.sll || ''} onChange={setExit('sll')}/></Grid></>}
      {replaceable.length > 0 && !isMleg && <Grid size={{xs: 12, md: 4}}><Pick label="Replace working order" value={ticket.replacement?.order_id || ''} onChange={pickReplacement}
        options={[['', 'New order'], ...replaceable.map(o => [o.id, `${o.side} ${o.qty} ${o.type} ${o.status}`])]}/></Grid>}
      {fixedLinked && <Grid size={12}><Notice severity="info">Linked order: side, quantity, type and duration are fixed; change prices only.</Notice></Grid>}
      <Grid size={12}><Stack direction="row" spacing={1}>
        <Button disabled={!f.exposureKnown || !held} onClick={() => seed(false)}>Prepare exit for held position</Button>
        <Button disabled={!f.exposureKnown || !held} onClick={() => seed(true)}>Prepare trailing stop for held position</Button>
        {!f.exposureKnown && <Typography variant="body2">Current reconciled holdings are required for position seeding.</Typography>}</Stack></Grid>
      <Grid size={{xs: 12, md: 4}}><Pick label="Order class" value={ticket.order_class || ''} onChange={v => setTicket(t => { ticketDirty.current = true; setPreview(null); return v === 'mleg' ? {...t, order_class: 'mleg', asset_class: 'us_option', session: 'regular', legs: t.legs || [], quantity: '', limit_price: ''} : (({order_class, execution_profile, legs: _l, net_direction, ...r}) => r)(t); })}
        options={[['', 'Single order'], ['mleg', 'Option package']]}/></Grid>
      {isMleg && <><Grid size={{xs: 6, md: 3}}><Pick label="Execution profile" disabled={!!ticket.replacement} value={ticket.execution_profile || ''} onChange={set('execution_profile')} options={[['', 'Choose'], ...Object.keys(profiles)]}/></Grid>
        <Grid size={{xs: 6, md: 3}}><Pick label="Net direction" value={ticket.net_direction || 'debit'} onChange={set('net_direction')} options={['debit', 'credit']}/></Grid>
        <Grid size={{xs: 12, md: 4}}><Pick label="Existing package to amend" value={ticket.replacement?.order_id || ''} onChange={id => {
          const existing = investor?.broker_order_actions?.[id]?.package_terms;
          ticketDirty.current = true; setPreview(null);
          setTicket(t => existing ? {...structuredClone(existing), replacement: {order_id: id}, rationale: '', research: null, decision_evidence_scopes: []} : {...t, replacement: undefined});
        }} options={[['', 'New package'], ...Object.entries(investor?.broker_order_actions || {}).filter(([, a]) => a.replace_supported && a.package_terms?.symbol === ticket.symbol)
          .map(([id, a]) => [id, `${id} · ${a.package_terms.order_type} ${a.package_terms.time_in_force}`])]}/></Grid>
        {ticket.replacement && <Grid size={12}><Notice severity="info">Contract, leg intent, ratios and order type are fixed. Save, obtain a fresh package approval, then use the separate Replace action.</Notice></Grid>}
        <Grid size={12}><Stack spacing={1}>{legs.map((l, i) => <Stack key={l.id} direction="row" spacing={1}>
          <Autocomplete disabled={!!ticket.replacement} sx={{minWidth: 240}} size="small"
            options={[...new Set([...Object.keys(investor?.instruments || {}), ...Object.keys(state?.nautilus?.market_data || {})])]
            .filter(symbol => optionEnvelope(symbol)?.raw?.underlying_symbol === ticket.symbol)}
            value={l.symbol || null} onChange={(_, symbol) => set('legs')(legs.map((x, j) => j === i ? {...x, symbol: symbol || ''} : x))}
            renderInput={params => <TextField {...params} label="Observed leg contract"/>}/>
          <Pick disabled={!!ticket.replacement} label="Intent" value={l.position_intent || ''} onChange={v => set('legs')(legs.map((x, j) => j === i ? {...x, position_intent: v} : x))} options={[['', 'Choose'], ...arr(profile?.intents)]}/>
          <Field disabled={!!ticket.replacement} label="Ratio" value={l.ratio_qty || ''} onChange={v => set('legs')(legs.map((x, j) => j === i ? {...x, ratio_qty: v} : x))}/>
          <Button disabled={!!ticket.replacement} onClick={() => set('legs')(legs.filter((_, j) => j !== i))}>Remove</Button></Stack>)}
          <Button disabled={!!ticket.replacement || legs.length >= 4} onClick={() => set('legs')([...legs, {id: crypto.randomUUID(), symbol: '', position_intent: '', ratio_qty: '1'}])}>Add leg</Button></Stack></Grid></>}
      <Grid size={{xs: 6, md: 2}}><Pick label="Duration" value={ticket.time_in_force} onChange={set('time_in_force')} options={[['DAY', 'Day'], ['GTC', 'Good till canceled']]}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Pick label="Session" value={ticket.session} onChange={set('session')} options={[['regular', 'Regular'], ['extended', 'Extended']]}/></Grid>
      <Grid size={12}><Field label="Optional order note" value={ticket.rationale} onChange={set('rationale')} multiline/></Grid>
    </Grid>
    <Typography variant="body2">Estimated notional {notional === null ? 'Unavailable' : money(notional)}{notional !== null && equity ? ` · ${pct(notional / equity * 100)} of equity` : ''}</Typography>
    <Stack direction="row" spacing={1} useFlexGap  sx={{flexWrap: "wrap"}}>{EVIDENCE_SCOPES.map(s => <FormControlLabel key={s} label={s.replaceAll('_', ' ')}
      control={<Checkbox size="small" checked={scopes.includes(s)} onChange={e => setScopes(c => e.target.checked ? [...c, s] : c.filter(x => x !== s))}/>}/>)}</Stack>
    <Field label="Optional revision note" value={reason} onChange={setReason} multiline/>
    <Stack direction="row" spacing={1} useFlexGap  sx={{flexWrap: "wrap"}}>
      <Button variant="contained" disabled={!instrument?.supported || !!issue} onClick={run('preview')}>1. Preview impact</Button>
      <Button disabled={!instrument?.supported || !!issue} onClick={run('draft')}>2. Save draft revision</Button>
      {ticket.id && <><Button color="warning" onClick={run('reject')}>Reject</Button><Button onClick={run('defer')}>Defer</Button>
        <Button onClick={() => {ticketDirty.current = false; setTicket(emptyTicket); setScopes([]); setReason(''); setPreview(null);}}>New proposal</Button></>}
    </Stack>
    {incoming && <Notice severity="info">An instrument or order draft is ready to open. Your current edits have been kept.
      <Button onClick={() => loadIntent(incoming)}>Replace ticket with requested draft</Button>
      <Button onClick={() => setIncoming(null)}>Keep current ticket</Button></Notice>}
    {message && <Notice severity="info">{message}</Notice>}
    {preview && <Evidence title="Impact preview" data={preview}/>}
    <Accordion expanded={chartOpen} onChange={(_, open) => setChartOpen(open)}>
      <AccordionSummary>Chart and historical price reference</AccordionSummary>
      <AccordionDetails><InstrumentChart symbol={ticket.symbol} active={active && page === 'orders' && chartOpen}
        copyTarget={{symbol: ticket.symbol, fields: copyFields, terms: terms(), expectedRevision: investor?.revision,
          instrumentId: instrument?.instrument_id, onApply: applyChartCopy}}/></AccordionDetails>
    </Accordion>
    <Proposals onOpen={p => {setTicket({...emptyTicket, ...p.terms, id: p.id, tp: p.terms?.exit_plan?.take_profit ?? '', sl: p.terms?.exit_plan?.stop_price ?? '', sll: p.terms?.exit_plan?.stop_limit_price ?? ''}); setReason(''); setScopes(arr(p.terms?.decision_evidence_scopes)); setPreview(null);}} f={f}/>
  </Section>;
}

function linked(commands, p) {
  if (!Number.isInteger(p?.revision) || typeof p.terms_sha256 !== 'string' || !p.terms_sha256 ||
      !p.terms?.account_id || !p.terms?.instrument_id) return [];
  return vals(commands?.data?.commands).filter(c => c.proposal_id === p.id && c.proposal_revision === p.revision && c.terms_sha256 === p.terms_sha256 &&
    c.account_id === p.terms?.account_id && c.instrument_id === p.terms?.instrument_id &&
    !['admitted_not_dispatched', 'not_sent'].includes(c.state));
}

function RecordedCommands({commands}) {
  const labels = {dispatch_intent: 'Submission requested', submitting: 'Submitting', outcome_unknown: 'Outcome unknown - reconcile',
    accepted: 'Working (accepted)', partially_filled: 'Working (partially filled)', cancel_pending: 'Cancellation pending',
    replace_pending: 'Replacement pending', filled: 'Filled', canceled: 'Canceled', rejected: 'Rejected', expired: 'Expired'};
  return <Stack spacing={1}>{commands.map(c => <Box key={c.id}>
    <Status value={labels[c.state] || 'Unrecognized command state - reconcile'}/>
    <Typography variant="caption" component="p">Command {c.id} · filled {text(c.filled_quantity)} · remaining {text(c.remaining_quantity)}</Typography>
    {(number(c.native_pending_commitment) > 0 || vals(c.native_deliveries).some(d => d?.status === 'conflict')) &&
      <Notice>Native confirmation remains unresolved. Review the existing command evidence; renewing approval does not resolve it.</Notice>}
    {c.pending_action && <Notice>An action on this existing order is pending. Reconcile its outcome before another action.</Notice>}
    {c.state === 'outcome_unknown' && <Notice>The broker outcome is unknown. Reconcile this existing order; do not submit it again.</Notice>}
  </Box>)}</Stack>;
}

function Proposals({onOpen, f}) {
  const {state} = useDesk();
  const proposals = arr(state?.investor?.data?.proposals);
  const [open, setOpen] = useState(null);
  return <Stack spacing={1}>
    <Typography variant="h3" sx={{fontSize: 16}}>Saved human proposals · {proposals.length}</Typography>
    <DataTable rows={proposals} getRowId={p => p.id} empty="No saved proposals."
      columns={[{id: 't', label: 'Terms', value: p => `${text(p.terms?.side)} ${text(p.terms?.quantity)} ${text(p.terms?.symbol)}`},
        {id: 'status', label: 'Recorded status for this exact revision', value: p => linked(state.commands, p).length ? linked(state.commands, p).map(c => c.state).join(' · ') : p.status, render: p => linked(state.commands, p).length ?
          <RecordedCommands commands={linked(state.commands, p)}/> : <Status value={p.status}/>},
        {id: 'rev', label: 'Revision', numeric: true, value: p => p.revision},
        {id: 'at', label: 'Updated', type: 'dateTime', value: p => p.updated_at, render: p => dateTime(p.updated_at)},
        {id: 'a', label: '', render: p => <Stack direction="row" spacing={1}>
          <Button size="small" onClick={() => onOpen(p)}>Open terms</Button>
          {p.status === 'draft' && !linked(state.commands, p).length &&
            <Button size="small" variant="contained" onClick={() => setOpen(p.id)}>Review & approve</Button>}</Stack>}]}/>
    {open && <ApprovalDialog key={open} proposalId={open} onClose={() => setOpen(null)} f={f}/>}
  </Stack>;
}

const AUTH_KEYS = ['account_max_age_seconds', 'quote_max_age_seconds', 'evidence_max_age_seconds', 'approval_max_age_seconds', 'max_execution_price', 'max_fees'];

function ApprovalDialog({proposalId, onClose, f}) {
  const {state, api, refresh, setError} = useDesk();
  const investor = state?.investor, proposal = arr(investor?.data?.proposals).find(p => p.id === proposalId);
  const identity = proposal ? JSON.stringify([state.server_instance_id, state.store_generation, state.nautilus?.connection_session, proposal.id, proposal.revision, proposal.terms_sha256, investor.data?.policy?.revision]) : '';
  const [captured] = useState(identity); // the review is bound to the exact state at open
  const [form, setForm] = useState(() => ({...Object.fromEntries(AUTH_KEYS.map(k => [k, ''])), note: ''}));
  const [busy, setBusy] = useState(false), [result, setResult] = useState(null), [message, setMessage] = useState('');
  const changed = identity !== captured;
  const commands = proposal ? linked(state.commands, proposal) : [];
  const replacing = proposal?.terms?.replacement?.order_id;
  const constraints = {...Object.fromEntries(AUTH_KEYS.filter(k => form[k] !== '').map(k => [k, form[k]])), ...(replacing && form.fee_cap !== undefined && form.fee_cap !== '' ? {working_order_fee_caps: {[replacing]: form.fee_cap}} : {})};
  const evaluation = result?.current_checks?.[proposalId] || result?.data?.proposals?.find(p => p.id === proposalId)?.risk_evaluation || investor?.current_checks?.[proposalId] || proposal?.risk_evaluation;
  const approve = async () => {
    if (commands.length) {setMessage('This exact revision already has an order command. Review its recorded outcome instead of renewing approval.'); return;}
    setBusy(true); setMessage('');
    try {
      const checked = await api('/api/investor', {action: 'review', id: proposal.id, proposal_revision: proposal.revision, policy_revision: investor.data.policy.revision,
        expected_revision: investor.revision, commands_revision: state.commands.revision, note: form.note, constraints,
        evaluation_binding_sha256: proposal.risk_evaluation?.binding_sha256, terms_sha256: proposal.terms_sha256});
      setResult(checked);
      const ev = checked.current_checks?.[proposal.id] || arr(checked.data?.proposals).find(p => p.id === proposal.id)?.risk_evaluation;
      if (!ev?.passed) throw new Error(arr(ev?.blockers).map(b => b.message ?? b).join('; ') || 'The impact review did not pass.');
      await api('/api/approvals', {action: 'approve', id: proposal.id, proposal_revision: proposal.revision, expected_revision: checked.revision,
        evaluation_binding_sha256: ev.binding_sha256, terms_sha256: proposal.terms_sha256, note: form.note, constraints});
      await refresh({fresh: true}).catch(() => {});
      setMessage('Approved. Approval does not submit; use Command lifecycle to submit explicitly.');
    } catch (e) { setError(e.message); setMessage(e.message); } finally { setBusy(false); }
  };
  return <Dialog open onClose={onClose} fullWidth maxWidth="md">
    <DialogTitle>Review and approve exact terms</DialogTitle>
    <DialogContent><Stack spacing={2} sx={{pt: 1}}>
      {!proposal && <Notice>This proposal no longer exists.</Notice>}
      {proposal && <Typography>{text(proposal.terms?.side)} {text(proposal.terms?.quantity)} {text(proposal.terms?.symbol)} · revision {proposal.revision}</Typography>}
      {commands.length > 0 && <><Notice>This exact saved revision already has an order command. No renewed approval is needed for the same order.</Notice><RecordedCommands commands={commands}/></>}
      {changed && <Notice>The proposal, policy or command state changed after this review opened. Close and reopen to review the current exact terms.</Notice>}
      {f.reasons.length > 0 && <Notice>{f.reasons.join(' ')}</Notice>}
      <Grid container spacing={2}>{AUTH_KEYS.map(k => <Grid key={k} size={{xs: 6, md: 4}}><Field label={k.replaceAll('_', ' ')} value={form[k]} onChange={v => setForm(s => ({...s, [k]: v}))}/></Grid>)}</Grid>
      <Field label="Approval note" value={form.note} onChange={v => setForm(s => ({...s, note: v}))} multiline/>
      {replacing && <Field label={`Fee ceiling for working order ${replacing} / USD`} value={form.fee_cap ?? ''} onChange={v => setForm(s => ({...s, fee_cap: v}))}/>}
      {investor?.approval_records_enabled !== true && <Notice>Approval records are not enabled; approval is unavailable.</Notice>}
      {evaluation && <Evidence title="Risk checks" data={evaluation}/>}
      {message && <Notice severity="info">{message}</Notice>}
    </Stack></DialogContent>
    <DialogActions><Button onClick={onClose}>Close</Button>
      <Button variant="contained" disabled={!proposal || changed || busy || commands.length > 0 || investor?.approval_records_enabled !== true} onClick={approve}>Run checks and approve</Button></DialogActions>
  </Dialog>;
}

// Authority binding: stable identity plus only the records the request relies on. Polling timestamps and sequences are excluded.
function snapshotOf(state, lookup) {
  const n = state?.nautilus || {};
  return JSON.stringify([state?.server_instance_id, state?.store_generation, n.connection_session, n.account?.id, n.native_epoch, n.status === 'connected',
    n.reconciliation?.status === 'reconciled', state?.connection?.connected === true, state?.connection?.account_verified === true, state?.commands?.execution_enabled === true,
    state?.investor?.data?.policy?.revision, lookup ? lookup(state) : null]);
}

function receiptLinks(command) {
  const found = new Map();
  const walk = v => {
    if (!v || typeof v !== 'object') return;
    if (v.path && /^[0-9a-f]{64}$/.test(v.sha256 || '')) found.set(v.sha256, v.path);
    Object.values(v).forEach(walk);
  };
  walk(command.native_receipts); walk(command.timeline);
  return [...found].map(([sha, path]) => <Typography key={sha} variant="body2">
    <Link href={`/api/commands/${encodeURIComponent(command.id)}/receipts/${sha}`} target="_blank" rel="noopener">Open saved receipt {path}</Link> · SHA-256 {sha}</Typography>);
}

// Every broker-path request is bound to the exact state it was captured from and never retried.
function useCommandSend(note) {
  const {state, api, refresh, setError} = useDesk();
  const [confirm, setConfirm] = useState(null), [receipt, setReceipt] = useState(null), [busy, setBusy] = useState(false);
  const latest = React.useRef(state);
  latest.current = state;
  const base = () => ({commands_revision: state.commands.revision, investor_revision: state.investor.revision});
  const stale = confirm && confirm.snapshot !== snapshotOf(state, confirm.lookup);
  // Global store revisions advance on harmless observation; the exact records are guarded above, so send the current optimistic-lock values.
  const fresh = (request, path) => {
    const {commands_revision, investor_revision, ...rest} = request, c = latest.current.commands.revision, i = latest.current.investor.revision;
    if (path === '/api/commands/reconcile') return rest;
    return path === '/api/approvals' ? {...rest, commands_revision: c, expected_revision: i} : {...rest, commands_revision: c, investor_revision: i};
  };
  const post = async (label, request, path = '/api/commands') => {
    setBusy(true);
    try {
      const r = await api(path, fresh(request, path));
      setReceipt({at: new Date().toISOString(), action: label, message: r?.message || 'Request accepted.', response: r});
      await refresh({fresh: true}).catch(() => {});
    } catch (e) { setError(`${e.message} No automatic retry; transport failure may leave the outcome unknown.`); }
    finally { setBusy(false); setConfirm(null); }
  };
  const ask = (label, request, terms, lookup, path = '/api/commands') => setConfirm({label, terms, lookup, path, request: {...base(), ...(note ? {note} : {}), ...request}, snapshot: snapshotOf(state, lookup)});
  const direct = (label, request) => post(label, {...base(), ...request});
  const reconcile = () => post('Refresh account and order status', {}, '/api/commands/reconcile');
  const dialog = <>
    {receipt && <Notice severity="info">{receipt.action}: {receipt.message} · {dateTime(receipt.at)}</Notice>}
    {receipt && <Evidence title="Receipt" data={receipt.response}/>}
    <Dialog open={Boolean(confirm)} onClose={() => setConfirm(null)} fullWidth maxWidth="md">
      <DialogTitle>Confirm {confirm?.label}</DialogTitle>
      <DialogContent><Stack spacing={1}><Typography>This sends the exact retained request once. No automatic retry.</Typography>
        {stale && <Notice>Account, command or connection state changed. Cancel and review again.</Notice>}
        {confirm?.terms && <Evidence title="Exact terms" data={confirm.terms}/>}
        {confirm && <Evidence title="Exact request" data={confirm.request}/>}</Stack></DialogContent>
      <DialogActions><Button onClick={() => setConfirm(null)}>Cancel</Button>
        <Button variant="contained" color="warning" disabled={stale || busy} onClick={() => post(confirm.label, confirm.request, confirm.path)}>Confirm</Button></DialogActions>
    </Dialog></>;
  return {ask, direct, reconcile, busy, dialog};
}

function BrokerOrderActions({c, order, f, ask, busy, canSend}) {
  const {state} = useDesk();
  const [sel, setSel] = useState(''), [rep, setRep] = useState('');
  const actions = f.investor.broker_order_actions || {}, states = f.commands.approval_states || {};
  const ids = c ? arr(c.broker_order_ids).filter(id => actions[id]?.cancel_supported || actions[id]?.replace_supported || actions[id]?.supported) : [order.id];
  const brokerId = ids.includes(sel) ? sel : ids[0], access = actions[brokerId] || {};
  const live = arr(state.nautilus?.orders).find(o => o.id === brokerId);
  const cancelOk = f.commands.execution_enabled === true && (access.cancel_supported ?? access.supported) === true;
  const replaceOk = canSend && (access.replace_supported ?? access.supported) === true;
  const symbol = c ? c.terms?.symbol : order.symbol;
  const approvalOpts = vals(f.data.approvals).filter(a => !f.data.revocations?.[a.id] && ['approved_awaiting_admission', 'admitted'].includes(states[a.id]) &&
    (!c || a.account_id === c.account_id) && a.terms?.symbol === symbol && a.terms?.replacement?.order_id === brokerId);
  const cmdOpts = c ? vals(f.data.commands).filter(o => o.id !== c.id && o.state === 'admitted_not_dispatched' && o.account_id === c.account_id && o.symbol === c.symbol && o.terms?.replacement?.order_id === brokerId) : [];
  const [kind, rid] = rep.split(':'), chosen = kind === 'approval' ? f.data.approvals?.[rid] : kind === 'command' ? f.data.commands?.[rid] : null;
  const grouped = live?.group_parent_id || ['bracket', 'oto', 'oco'].includes(live?.group_class);
  const lookup = s => [c && s.commands?.data?.commands?.[c.id], s.investor?.broker_order_actions?.[brokerId],
    (o => o && [o.status, o.qty, o.filled_qty, o.limit_price, o.stop_price, o.time_in_force])(arr(s.nautilus?.orders).find(o => o.id === brokerId)),
    kind === 'approval' ? [s.commands?.data?.approvals?.[rid], s.commands?.approval_states?.[rid], s.commands?.data?.revocations?.[rid]] : kind === 'command' ? s.commands?.data?.commands?.[rid] : null];
  const send = action => ask(`${action === 'cancel' ? 'Cancel' : 'Replace'} broker order ${brokerId}`,
    {action, ...(c ? {id: c.id} : {}), broker_order_id: brokerId, broker_order_version: access.order_version,
      ...(action === 'replace' ? (kind === 'approval' ? {replacement_approval_id: rid} : {replacement_command_id: rid}) : {})},
    {predecessor_command: c ?? null, observed_broker_order: live ?? null, replacement: chosen ?? null}, lookup);
  return <Stack spacing={1}>
    {!c && <Typography variant="body2">Imported broker order {text(order.id)} · {text(order.status)} · filled {text(order.filled_qty)}. It originated outside the app; no submission approval is claimed.</Typography>}
    {grouped && <Notice>Canceling a linked order asks Alpaca to cancel the remaining linked orders. Bracket and OCO exits support price-only changes with new exact approval; OTO replacement is unsupported.</Notice>}
    {live && <Typography variant="body2">Broker-reported session: {live.extended_hours === true ? 'Extended' : live.extended_hours === false ? 'Regular' : 'Unreported'}. A replacement cannot change the session.</Typography>}
    {!ids.length && <Typography variant="body2">{text(access.reason ?? 'No supported broker order identity is current.')}</Typography>}
    {access.replacement_reason && <Typography variant="body2">{access.replacement_reason}</Typography>}
    {c && ids.length > 1 && <Pick label="Broker order" value={brokerId ?? ''} onChange={v => {setSel(v); setRep('');}} options={ids}/>}
    <Pick label="Separately approved replacement" value={rep} onChange={setRep} disabled={!replaceOk}
      options={[['', 'Choose approved terms'], ...approvalOpts.map(a => [`approval:${a.id}`, `${text(a.terms?.side)} ${text(a.terms?.quantity)} ${text(a.terms?.order_type)} ${a.terms?.limit_price ? `limit ${a.terms.limit_price}` : ''} · revision ${a.proposal_revision}`]),
        ...cmdOpts.map(o => [`command:${o.id}`, `reserved command ${o.id} · ${text(o.terms?.quantity)}`])]}/>
    <Stack direction="row" spacing={1}>
      <Button size="small" color="warning" disabled={busy || !brokerId || !cancelOk} onClick={() => send('cancel')}>Cancel selected order</Button>
      <Button size="small" variant="contained" disabled={busy || !brokerId || !replaceOk || !chosen} onClick={() => send('replace')}>Replace with approved terms</Button>
    </Stack>
  </Stack>;
}

function Lifecycle() {
  const {state} = useDesk();
  const f = useFacts();
  const [note, setNote] = useState('');
  const {ask, direct, reconcile, busy, dialog} = useCommandSend(note);
  const approvals = vals(f.data.approvals), cmds = vals(f.data.commands), groups = vals(f.data.basket_executions);
  const byId = f.data.commands || {}, approvalById = f.data.approvals || {};
  const blocked = f.data.new_orders_blocked === true;
  const canSend = f.commands.execution_enabled === true && !blocked && !f.data.recovery_required && f.reasons.length === 0;
  const states = f.commands.approval_states || {};
  const submittable = a => (states[a.id] === 'approved_awaiting_admission' || states[a.id] === 'admitted' && cmds.some(c => c.approval_id === a.id && c.state === 'admitted_not_dispatched')) &&
    f.reasons.length === 0 && !f.data.recovery_required && !a.terms?.replacement;
  const resolvable = ['dispatch_intent', 'submitting', 'outcome_unknown', 'cancel_pending', 'replace_pending'];
  const imported =  arr(state.nautilus?.orders).filter(o => !cmds.some(c => arr(c.broker_order_ids).includes(o.id)));
  return <Section title="Approvals and commands">
    {f.reasons.length > 0 && <Notice>{f.reasons.join(' ')}</Notice>}
    <Stack direction="row" spacing={1}  sx={{alignItems: "center"}}>
      <Box sx={{flex: 1}}><Field label="Note for the next request (optional)" value={note} onChange={setNote}/></Box>
      <Button disabled={busy || (blocked ? !f.commands.review_enabled : false)} color={blocked ? 'primary' : 'warning'}
        onClick={() => direct(blocked ? 'Resume new orders' : 'Pause new orders', {action: 'block', blocked: !blocked})}>{blocked ? 'Resume new orders' : 'Pause new orders'}</Button>
      <Button disabled={busy} onClick={reconcile}>Refresh account and order status</Button>
    </Stack>
    <DataTable rows={approvals} getRowId={a => a.id} empty="No approvals."
      columns={[{id: 'id', label: 'Approval', value: a => `${text(a.terms?.side)} ${text(a.terms?.quantity)} ${text(a.terms?.symbol)}`},
        {id: 's', label: 'State', value: a => f.data.revocations?.[a.id] ? 'revoked' : states[a.id] ?? a.status, render: a => <Status value={f.data.revocations?.[a.id] ? 'revoked' : states[a.id] ?? a.status}/>},
        {id: 'act', label: '', render: a => <Stack direction="row" spacing={1}><Button size="small" variant="contained" disabled={!submittable(a) || busy}
          onClick={() => ask(`Submit ${a.terms?.symbol}`, {action: 'submit', approval_id: a.id}, {approval: a}, s => [s.commands?.data?.approvals?.[a.id], s.commands?.approval_states?.[a.id], s.commands?.data?.revocations?.[a.id]])}>Submit exact approval</Button>
          <Button size="small" color="warning" disabled={busy || f.investor.approval_records_enabled !== true || Boolean(f.data.revocations?.[a.id]) || states[a.id] === 'admitted' && cmds.some(c => c.approval_id === a.id && c.state !== 'admitted_not_dispatched')}
            onClick={() => ask(`Revoke approval for ${a.terms?.symbol}`, {action: 'revoke', approval_id: a.id}, {approval: a}, s => [s.commands?.data?.approvals?.[a.id], s.commands?.approval_states?.[a.id], s.commands?.data?.revocations?.[a.id]], '/api/approvals')}>Revoke approval</Button></Stack>}]}/>
    <DataTable rows={cmds} getRowId={c => c.id} empty="No commands."
      columns={[{id: 'c', label: 'Command', value: c => `${text(c.terms?.side)} ${text(c.terms?.quantity)} ${text(c.terms?.symbol)}`},
        {id: 's', label: 'State', value: c => c.state, render: c => <Status value={c.state}/>},
        {id: 'filled_quantity', label: 'Filled', numeric: true},
        {id: 'remaining_quantity', label: 'Remaining', numeric: true},
        {id: 'ev', label: 'Evidence', sortable: false, filterable: false, render: c => <Stack>{c.pending_action && <span>Pending {c.pending_action}</span>}
          {vals(c.native_deliveries).some(d => d?.status === 'conflict') && <span>Native delivery conflict</span>}
          {c.origin === 'external_broker' && <span>External broker order</span>}{receiptLinks(c)}</Stack>},
        {id: 'a', label: '', render: c => <Stack direction="row" spacing={1}>
          {c.state === 'admitted_not_dispatched' && <Button size="small" variant="contained" disabled={!canSend || busy}
            onClick={() => ask(`Submit ${c.terms?.symbol}`, {action: 'submit', id: c.id}, {command: c, approval: approvalById[c.approval_id]}, s => s.commands?.data?.commands?.[c.id])}>Submit admitted command</Button>}
          {['accepted', 'partially_filled'].includes(c.state) && <BrokerOrderActions c={c} f={f} ask={ask} busy={busy} canSend={canSend}/>}
          {resolvable.includes(c.state) && f.commands.review_enabled && <Button size="small" disabled={busy} onClick={() => ask(`Resolve ${c.terms?.symbol} as never dispatched`,
            {action: 'resolve_never_dispatched', id: c.id, operation: c.pending_action?.replace(/_pending$/, '') || 'submit'}, {command: c}, s => s.commands?.data?.commands?.[c.id])}>Resolve never dispatched</Button>}
        </Stack>}]}/>
    <Typography variant="h3" sx={{fontSize: 16}}>Imported broker orders</Typography>
    {imported.length === 0 && <Typography variant="body2">No imported broker orders.</Typography>}
    {imported.map(o => <Accordion key={o.id} disableGutters variant="outlined"><AccordionSummary>{`${text(o.side)} ${text(o.qty)} ${text(o.symbol)} · ${text(o.status)} · ${o.id}`}</AccordionSummary>
      <AccordionDetails><BrokerOrderActions order={o} f={f} ask={ask} busy={busy} canSend={canSend}/></AccordionDetails></Accordion>)}
    <Typography variant="h3" sx={{fontSize: 16}}>Retained basket groups</Typography>
    <DataTable rows={groups} getRowId={g => g.id} empty="No retained basket groups."
      columns={[{id: 'id', label: 'Group'}, {id: 's', label: 'State', value: g => g.state, render: g => <Status value={g.state}/>},
        {id: 'legs', label: 'Legs', value: g => arr(g.command_ids).map(id => `${text(byId[id]?.terms?.symbol)} ${text(byId[id]?.state)}`).join(' · ')},
        {id: 'a', label: '', render: g => <Stack direction="row" spacing={1}>
          <Button size="small" variant="contained" disabled={!canSend || busy || !['ready', 'running'].includes(g.state)}
            onClick={() => ask('Dispatch next basket leg', {action: 'basket_dispatch_next', id: g.id},
              {group: g, legs: arr(g.command_ids).map(id => ({command: byId[id], approval: approvalById[byId[id]?.approval_id], frozen_binding: arr(g.frozen_legs).find(l => l.approval_id === byId[id]?.approval_id)}))}, s => [s.commands?.data?.basket_executions?.[g.id], arr(g.command_ids).map(id => s.commands?.data?.commands?.[id])])}>Dispatch next leg</Button>
          <Button size="small" color="warning" disabled={busy || g.state === 'paused'} onClick={() => direct('Pause basket', {action: 'basket_control', id: g.id, paused: true})}>Pause</Button>
          <Button size="small" disabled={busy || g.state !== 'paused' || !f.commands.review_enabled} onClick={() => direct('Resume valid basket orders', {action: 'basket_control', id: g.id, paused: false})}>Resume valid basket orders</Button>
        </Stack>}]}/>
    {dialog}
  </Section>;
}


function Fills() {
  const {state} = useDesk();
  return <Section fill title="Fills and fees">
    <DataTable fill rows={arr(state?.fills)} getRowId={r => r.id ?? JSON.stringify(r)} empty="No fill records in the current observation."
      columns={[{id: 't', label: 'Time', type: 'dateTime', value: r => r.transaction_time || r.timestamp, render: r => dateTime(r.transaction_time || r.timestamp)}, {id: 's', label: 'Symbol', value: r => r.symbol},
        {id: 'side', label: 'Side'}, {id: 'q', label: 'Quantity', numeric: true, value: r => r.qty ?? r.quantity},
        {id: 'p', label: 'Fill price', numeric: true, value: r => r.price ?? r.fill_price, render: r => money(r.price ?? r.fill_price)},
        {id: 'c', label: 'Commission', numeric: true, value: r => r.commission, render: r => r.commission === null || r.commission === undefined ? 'Unknown' : text(r.commission)}]}/>
    <Typography variant="body2" color="text.secondary">Modeled native fees are not actual broker fees.</Typography>
  </Section>;
}

function Baskets() {
  const {state, act} = useDesk();
  const f = useFacts(), investor = state?.investor;
  const [targets, setTargets] = useState([{symbol: '', mode: 'quantity', value: '', order_type: 'LIMIT', limit_price: ''}]);
  const [meta, setMeta] = useState({reason: '', fee_per_leg: '', slippage_bps: ''});
  const [preview, setPreview] = useState(null);
  const edit = fn => { setTargets(fn); setPreview(null); };
  const setT = (i, k, v) => edit(t => t.map((x, j) => j === i ? {...x, [k]: v} : x));
  const send = action => async () => {
    try {
      const r = await act(`basket-${action}`, '/api/investor', {action, targets, ...meta, assumed_filled: [], expected_revision: investor.revision});
      if (action === 'basket_preview') setPreview(r?.preview ?? null); else setPreview(null);
    } catch { /* reported */ }
  };
  const baskets = arr(investor?.data?.baskets);
  const [review, setReview] = useState(null), [choice, setChoice] = useState({}), [dep, setDep] = useState({});
  const {ask, busy, dialog} = useCommandSend('');
  const reviewed = baskets.find(b => b.id === review);
  const legs = reviewed ? arr(reviewed.linked_proposal_ids).map(pid => {
    const options = vals(f.data.approvals).filter(a => a.proposal_id === pid && !f.data.revocations?.[a.id]);
    const approval = options.find(a => a.id === choice[`${reviewed.id}:${pid}`]) ?? options.at(-1);
    return {pid, proposal: arr(investor?.data?.proposals).find(p => p.id === pid), options, approval};
  }) : [];
  const canAdmit = Boolean(reviewed) && legs.length > 0 && legs.every(l => l.approval) && reviewed.impact_review_valid === true && f.commands.execution_enabled === true &&
    f.reasons.length === 0 && !busy;
  return <Section title="Human baskets">
    <Typography variant="body2">A basket is a set of local proposals. Saving grants no approval; each leg is approved and submitted separately.</Typography>
    {targets.map((t, i) => <Grid container spacing={1} key={i}>
      <Grid size={{xs: 6, md: 2}}><Field label="Symbol" value={t.symbol} onChange={v => setT(i, 'symbol', v.toUpperCase())}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Pick label="Mode" value={t.mode} onChange={v => setT(i, 'mode', v)} options={['quantity', 'weight']}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Field label="Value" value={t.value} onChange={v => setT(i, 'value', v)}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Pick label="Order type" value={t.order_type} onChange={v => setT(i, 'order_type', v)} options={['MARKET', 'LIMIT']}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Field label="Limit / USD" value={t.limit_price} onChange={v => setT(i, 'limit_price', v)} disabled={t.order_type === 'MARKET'}/></Grid>
      <Grid size={{xs: 6, md: 2}}><Button color="warning" onClick={() => edit(c => c.filter((_, j) => j !== i))}>Remove</Button></Grid>
    </Grid>)}
    <Button sx={{alignSelf: 'flex-start'}} onClick={() => edit(t => [...t, {symbol: '', mode: 'quantity', value: '', order_type: 'LIMIT', limit_price: ''}])}>Add target</Button>
    <Grid container spacing={1}>
      <Grid size={{xs: 12, md: 6}}><Field label="Reason" value={meta.reason} onChange={v => {setMeta(m => ({...m, reason: v})); }}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="Fee per leg / USD" value={meta.fee_per_leg} onChange={v => {setMeta(m => ({...m, fee_per_leg: v})); setPreview(null);}}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="Slippage / bps" value={meta.slippage_bps} onChange={v => {setMeta(m => ({...m, slippage_bps: v})); setPreview(null);}}/></Grid>
    </Grid>
    <Stack direction="row" spacing={1}>
      <Button variant="contained" onClick={send('basket_preview')}>1. Preview basket impact</Button>
      <Button disabled={!preview} onClick={send('basket_draft')}>2. Save basket draft</Button>
    </Stack>
    {preview && <Evidence title="Basket impact preview" data={preview}/>}
    <DataTable rows={baskets} getRowId={b => b.id} empty="No saved baskets."
      columns={[{id: 'id', label: 'Basket'}, {id: 's', label: 'Status', value: b => b.status, render: b => <Status value={b.status}/>},
        {id: 'r', label: 'Revision', numeric: true, value: b => b.revision},
        {id: 'v', label: 'Impact review', value: b => b.impact_review_valid ? 'Valid' : 'Needs review'},
        {id: 'a', label: '', render: b => <Button size="small" onClick={() => setReview(b.id)}>Review legs for admission</Button>}]}/>
    {f.reasons.length > 0 && <Notice>Leg admission is blocked: {f.reasons.join(' ')}</Notice>}
    {reviewed && <Stack spacing={1} sx={{p: 1, border: 1, borderColor: 'divider', borderRadius: 1}}>
      <Typography variant="h3" sx={{fontSize: 16}}>Admit basket {reviewed.id} revision {reviewed.revision}</Typography>
      {!reviewed.impact_review_valid && <Notice>The basket impact review is not valid; preview and save it again before admission.</Notice>}
      {legs.map((leg, i) => <Grid container spacing={1} key={leg.pid} sx={{alignItems: 'center'}}>
        <Grid size={{xs: 12, md: 3}}><Typography>{text(leg.proposal?.terms?.side)} {text(leg.proposal?.terms?.quantity)} {text(leg.proposal?.terms?.symbol)}</Typography></Grid>
        <Grid size={{xs: 12, md: 5}}><Pick label="Approval" value={leg.approval?.id ?? ''} onChange={v => setChoice(c => ({...c, [`${reviewed.id}:${leg.pid}`]: v}))}
          options={leg.options.map(a => [a.id, `${a.id.slice(0, 8)} · revision ${a.proposal_revision}`])}/></Grid>
        <Grid size={{xs: 12, md: 4}}>{i > 0 && <FormControlLabel label="Wait for previous leg" control={<Checkbox checked={Boolean(dep[`${reviewed.id}:${leg.pid}`])}
          onChange={e => setDep(d => ({...d, [`${reviewed.id}:${leg.pid}`]: e.target.checked}))}/>}/>}</Grid>
      </Grid>)}
      <Button variant="contained" color="warning" sx={{alignSelf: 'flex-start'}} disabled={!canAdmit}
        onClick={() => ask(`Admit and dispatch first leg of basket ${reviewed.id}`, {action: 'basket_dispatch_next', basket_id: reviewed.id, basket_revision: reviewed.revision,
          legs: legs.map((leg, i) => ({proposal_id: leg.pid, proposal_revision: leg.approval.proposal_revision, approval_id: leg.approval.id, terms_sha256: leg.approval.terms_sha256,
            depends_on: i > 0 && dep[`${reviewed.id}:${leg.pid}`] ? [legs[i - 1].pid] : []}))}, {basket: reviewed, legs: legs.map(l => ({proposal: l.proposal, approval: l.approval}))},
          s => [arr(s.investor?.data?.baskets).find(b => b.id === reviewed.id), legs.map(l => [arr(s.investor?.data?.proposals).find(p => p.id === l.pid), s.commands?.data?.approvals?.[l.approval.id], s.commands?.data?.revocations?.[l.approval.id]])])}>
        Admit and dispatch first leg</Button>
    </Stack>}
    {dialog}
  </Section>;
}

function OptionInstructions() {
  const {state, act, pending} = useDesk();
  const f = useFacts();
  const list = vals(f.data.option_instructions);
  const [form, setForm] = useState({symbol: '', kind: '', account_age: '', approval_age: '', note: ''});
  const [preview, setPreview] = useState(null), [message, setMessage] = useState('');
  const identity = JSON.stringify([form.symbol, form.kind, form.account_age, form.approval_age, state?.store_generation,
    state?.nautilus?.account?.id, state?.nautilus?.connection_session, state?.nautilus?.native_epoch]);
  const [previewId, setPreviewId] = useState(''), [reviews, setReviews] = useState({}), [acknowledged, setAcknowledged] = useState({});
  const busy = [...pending].some(key => key.startsWith('option-')), readOnly = state.browse_only === true;
  const valid = preview && previewId === identity;
  const matches = rec => rec.symbol === form.symbol && rec.kind === form.kind &&
    String(rec.constraints?.account_max_age_seconds ?? '') === form.account_age &&
    String(rec.constraints?.approval_max_age_seconds ?? '') === form.approval_age;
  const reviewed = rec => Boolean(matches(rec) && rec.review?.binding_sha256 &&
    reviews[rec.id]?.binding === rec.review.binding_sha256 && reviews[rec.id]?.identity === identity);
  const constraints = Object.fromEntries([['account_max_age_seconds', form.account_age], ['approval_max_age_seconds', form.approval_age]].filter(([, v]) => v !== ''));
  const body = (operation, extra) => ({action: 'option_instruction', operation, symbol: form.symbol, kind: form.kind, constraints, note: form.note,
    commands_revision: state.commands.revision, investor_revision: state.investor.revision, ...extra});
  const run = (operation, extra) => async () => {
    try {
      const r = await act(`option-${operation}`, '/api/commands', body(operation, extra));
      if (operation === 'preview') { setPreview(r?.option_preview ?? null); setPreviewId(identity); }
      else { setPreview(null); setMessage('Instruction prepared. Open its exact saved terms below, then review and approve separately.'); }
    } catch { /* reported */ }
  };
  const rowOp = async (rec, operation) => {
    if (!matches(rec)) { setMessage('Open the exact saved instruction terms before acting on it.'); return; }
    if (operation === 'approve' && !reviewed(rec)) { setMessage('Review the exact current saved instruction again before approving.'); return; }
    try {
      const result = await act(`option-${operation}-${rec.id}`, '/api/commands', {action: 'option_instruction', operation, instruction_id: rec.id,
        kind: form.kind, symbol: form.symbol, constraints: rec.constraints, note: form.note,
        reviewed_unknowns: Boolean(rec.review?.binding_sha256 && acknowledged[rec.id] === rec.review.binding_sha256),
        binding_sha256: operation === 'approve' ? reviews[rec.id].binding : undefined,
        commands_revision: state.commands.revision, investor_revision: state.investor.revision});
      if (operation === 'review') {
        const binding = result?.data?.option_instructions?.[rec.id]?.review?.binding_sha256;
        if (!binding) throw new Error('The saved instruction review was not returned. Reload and review its exact facts again.');
        setReviews(previous => ({...previous, [rec.id]: {binding, identity}}));
      } else setReviews(previous => ({...previous, [rec.id]: null}));
      setAcknowledged(previous => ({...previous, [rec.id]: null}));
      setMessage(`Instruction ${operation} recorded. No subsequent step was triggered automatically.`);
    } catch (failure) { setMessage(failure.message); }
  };
  return <Section title="Option instructions">
    <Typography variant="body2">Exercise or do-not-exercise instructions. Preview, prepare, review, approve and submit are separate steps.</Typography>
    {message && <Notice severity="info">{message}</Notice>}
    <Grid container spacing={1}>
      <Grid size={{xs: 6, md: 3}}><Field label="Contract symbol" value={form.symbol} onChange={v => setForm(s => ({...s, symbol: v.toUpperCase()}))}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Pick label="Instruction" value={form.kind} onChange={v => setForm(s => ({...s, kind: v}))} options={[['', 'Choose exact intent'], ['exercise', 'Exercise all available'], ['do_not_exercise', 'Request DNE']]}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="Account max age / s" value={form.account_age} onChange={v => setForm(s => ({...s, account_age: v}))}/></Grid>
      <Grid size={{xs: 6, md: 3}}><Field label="Approval max age / s" value={form.approval_age} onChange={v => setForm(s => ({...s, approval_age: v}))}/></Grid>
    </Grid>
    <Field label="Note" value={form.note} onChange={v => setForm(s => ({...s, note: v}))}/>
    <Stack direction="row" spacing={1}>
      <Button variant="contained" disabled={busy || !form.symbol || !form.kind} onClick={run('preview', {})}>1. Preview</Button>
      <Button disabled={busy || readOnly || !valid || arr(preview?.blockers).length > 0} onClick={run('prepare', {})}>2. Prepare</Button>
    </Stack>
    {preview && !valid && <Notice>The preview no longer matches the form or connection. Preview again.</Notice>}
    {valid && <Evidence title="Option preview" data={preview}/>}
    <DataTable rows={list} getRowId={r => r.id} empty="No option instructions."
      columns={[{id: 'sym', label: 'Instruction', value: r => `${text(r.kind)} ${text(r.symbol)}`}, {id: 's', label: 'State', value: r => r.state, render: r => <Status value={r.state}/>},
        {id: 'facts', label: 'Exact authority and history', sortable: false, filterable: false, render: r => <Evidence title={`${r.kind} ${r.symbol} · ${r.id}`} data={r}/>},
        {id: 'a', label: 'Separate actions', sortable: false, filterable: false, render: r => <Stack spacing={1}>
          <Button size="small" disabled={busy} onClick={() => {
            setForm({symbol: r.symbol, kind: r.kind, account_age: String(r.constraints?.account_max_age_seconds ?? ''),
              approval_age: String(r.constraints?.approval_max_age_seconds ?? ''), note: ''});
            setPreview(null); setReviews(previous => ({...previous, [r.id]: null}));
            setAcknowledged(previous => ({...previous, [r.id]: null}));
          }}>Open exact instruction</Button>
          {r.state === 'prepared' && <Button size="small" disabled={busy || readOnly || !matches(r)} onClick={() => rowOp(r, 'review')}>Review current exact facts</Button>}
          {r.state === 'prepared' && r.review && <FormControlLabel label="I reviewed this instruction's prior requests and unknown outcomes"
            control={<Checkbox checked={reviewed(r) && acknowledged[r.id] === r.review.binding_sha256}
              disabled={!reviewed(r) || busy} onChange={event => setAcknowledged(previous => ({...previous, [r.id]: event.target.checked ? r.review.binding_sha256 : null}))}/>}/>}
          {r.state === 'prepared' && r.review && <Button size="small" disabled={busy || readOnly || !reviewed(r) ||
            arr(r.review.blockers).length > 0 || arr(r.review.facts?.history).some(prior => prior.state === 'transport_unknown') && acknowledged[r.id] !== r.review.binding_sha256}
            onClick={() => rowOp(r, 'approve')}>Approve exact reviewed instruction</Button>}
          {r.state === 'approved' && <Button size="small" color="warning"
            disabled={busy || readOnly || !matches(r) || r.kind === 'exercise' && f.data.new_orders_blocked} onClick={() => rowOp(r, 'submit')}>Submit approved instruction</Button>}
          {r.state === 'transport_unknown' && !r.interlock_release && <Button size="small" disabled={busy || readOnly || !matches(r) || !form.note.trim()}
            onClick={() => rowOp(r, 'release_interlock')}>Release local interlock (note required)</Button>}
        </Stack>}]}/>
    <Typography variant="body2">These are full-position requests, not settlement or a retry of prior authority. Pause blocks exercise dispatch; separately approved DNE remains available. Releasing an interlock does not resolve an unknown outcome or authorize replay.</Typography>
  </Section>;
}

export function OrdersView() {
  const {state, navigation} = useDesk();
  const [tab, setTab] = useState('ticket');
  useEffect(() => {
    if (navigation?.page === 'orders' && (navigation.intent?.tab === 'ticket' || String(navigation.intent?.kind).startsWith('option-'))) setTab('ticket');
  }, [navigation]);
  if (!state) return <Page title="Orders"><Typography>Loading…</Typography></Page>;
  return <Page tabbed title="Orders" subtitle="Prepare, approve and submit orders as separate explicit steps.">
    <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable">
      {[['ticket', 'Ticket & Blotter'], ['fills', 'Fills & Fees'], ['baskets', 'Human Baskets'], ['spy', 'SPY Rebalance'], ['options', 'Option Instructions']]
        .map(([v, l]) => <Tab key={v} value={v} label={l}/>)}
    </Tabs>
    <Box role="tabpanel" hidden={tab !== 'ticket'}><Stack spacing={2}><Ticket active={tab === 'ticket'}/><Lifecycle/><Section title="Broker orders"><OrdersTable/></Section></Stack></Box>
    <Box role="tabpanel" hidden={tab !== 'fills'}><Fills/></Box>
    <Box role="tabpanel" hidden={tab !== 'baskets'}><Baskets/></Box>
    <Box role="tabpanel" hidden={tab !== 'spy'}><SpyReview/></Box>
    <Box role="tabpanel" hidden={tab !== 'options'}><OptionInstructions/></Box>
  </Page>;
}
