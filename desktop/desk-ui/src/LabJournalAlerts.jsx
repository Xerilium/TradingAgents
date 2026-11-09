import { useEffect, useMemo, useRef, useState } from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import Link from '@mui/material/Link';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useDesk } from './DeskContext.jsx';
import { DataTable, Evidence, Page, Status, dateTime, money, number, nativeReportColumns } from './ui.jsx';

const INDICATORS = ['close_50_sma', 'close_200_sma', 'close_10_ema', 'macd', 'macds', 'macdh', 'rsi', 'boll', 'boll_ub', 'boll_lb', 'atr', 'vwma', 'mfi'];
const METRICS = ['net_return_pct', 'total_pnl', 'max_drawdown_pct'];
const INTERVALS = ['1Min', '5Min', '15Min', '30Min', '1Hour', '1Day'];
const RULE_KINDS = ['price_above', 'price_below', 'movement', 'source_missing', 'source_stale', 'policy_condition', 'indicator', 'drawing'];
const RULE_SCOPES = ['quote', 'account', 'research', 'history', 'news', 'earnings', 'fundamentals', 'corporate_actions', 'classification', 'indicator', 'drawing'];
const blankAtom = () => ({ left: { kind: 'price', field: 'close' }, comparison: 'above', right: { kind: 'indicator', name: 'close_50_sma' } });
const blankStrategy = () => ({
  name: '', symbol: '', quantity: { kind: 'constant', value: '1', units: 'shares' },
  entry: { operator: 'ALL', atoms: [blankAtom()] },
  exit: { operator: 'ALL', atoms: [{ ...blankAtom(), comparison: 'below' }] },
  parameters: [],
});
const blankExecution = () => ({
  entry_order_type: 'MARKET', exit_order_type: 'MARKET', time_in_force: 'DAY',
  timing: 'native_ohlc_path_next_modeled_open', pending_entry_exit: 'cancel_then_exit_actual_position',
  brackets: 'native_full_oto', limit_price: null, stop_price: null, exit_plan: null,
});
const blankExperiment = () => ({
  history_key: '', benchmark_history_key: '', start_at: '', end_at: '', starting_cash: '',
  decision_basis: 'hindsight_scenario',
  window: { mode: 'rolling', train_sessions: '126', validation_sessions: '21', gap_sessions: '1', oos_sessions: '21', step_sessions: '21' },
  search: { mode: 'grid', seed: '0', max_trials: '64' },
  selection: { objective: '', direction: '', secondary_metric: '', secondary_direction: '', minimum_closed_trades: '' },
  budgets: { max_native_runs: '', experiment_seconds: '', trial_seconds: '', no_experiment_time_cap: false, no_trial_time_cap: false },
  scenarios: [{ id: 'scenario-1', fee_usd: '', fee_per: '', limit_fill_probability: '', slippage_probability: '', random_seed: '0', latency_ns: 0 }],
});
const blankEval = () => ({
  proposal_id: '', history_key: '', starting_cash: '', start_at: '', end_at: '', decision_at: '',
  decision_basis: '', fee_usd: '', fee_per: '', limit_fill_probability: '', slippage_probability: '',
  random_seed: '', latency_ns: '', reviewed: false,
});
const blankRule = () => ({
  name: '', kind: '', scope: '', symbol: '', threshold: '', max_age_seconds: '', proposal_id: '',
  condition: '', active: false, operator: 'ALL', target_mode: 'symbol', watchlist_id: '', atoms: [],
});
function alertDraftFromMarkets(intent) {
  if (intent?.kind === 'drawing-alert') {
    const option = intent.option;
    const ref = option?.drawing_ref || intent.drawing_ref;
    const scope = option?.scope;
    return {
      ...blankRule(),
      name: 'Drawing alert',
      kind: 'drawing',
      scope: 'drawing',
      symbol: scope?.symbol || intent.symbol || '',
      drawing_ref: ref ? structuredClone(ref) : undefined,
      drawing: option?.drawing ? structuredClone(option.drawing) : undefined,
      drawing_candidate: ref ? `${ref.drawing_id}/${ref.revision}/${ref.geometry_sha256}` : '',
      field: 'c',
      comparison: 'cross_above',
      geometry_policy: 'segment',
      context: scope?.context === 'current' || intent.context === 'current' ? 'current' : 'research',
      timeframe: scope?.timeframe || intent.timeframe || '',
      history_key: intent.history_key || '',
      run_id: intent.run_id || '',
      target_mode: 'symbol',
      active: false,
    };
  }
  if (intent?.kind === 'indicator-alert') {
    return {
      ...blankRule(),
      name: 'Indicator alert',
      kind: 'indicator',
      scope: 'indicator',
      symbol: intent.symbol || '',
      indicator: intent.indicator || '',
      context: intent.context === 'current' ? 'current' : 'research',
      timeframe: intent.timeframe || '',
      history_key: intent.history_key || '',
      run_id: intent.run_id || '',
      target_mode: 'symbol',
      active: false,
    };
  }
  return null;
}

function text(value) {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  return String(value);
}
function labelize(value) {
  const known = { hindsight_scenario: 'Historical scenario', recorded_decision: 'Recorded decision availability' };
  if (known[value]) return known[value];
  if (!value) return 'Unavailable';
  return String(value).replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase());
}
function finite(value) {
  return (typeof value === 'number' || (typeof value === 'string' && value.trim() !== '')) && Number.isFinite(Number(value));
}
function count(value) {
  return finite(value) && Number.isSafeInteger(Number(value)) && Number(value) >= 0;
}
function setPath(root, path, value) {
  const next = structuredClone(root);
  const keys = path.split('.');
  let target = next;
  while (keys.length > 1) {
    const key = keys.shift();
    const index = Number(key);
    if (target[Number.isInteger(index) && String(index) === key ? index : key] == null) target[key] = /^\d+$/.test(keys[0]) ? [] : {};
    target = target[key];
  }
  target[keys[0]] = value;
  return next;
}
function downloadText(body, filename, type) {
  const url = URL.createObjectURL(body instanceof Blob ? body : new Blob([body], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
function messageOf(error) {
  return error?.message || 'The request failed.';
}
function clone(value) {
  return value == null ? null : structuredClone(value);
}
function storedNotificationProfile() {
  try { return localStorage.getItem('tradingagents-notification-profile') || ''; } catch { return ''; }
}
/** Parent Orders ticket effect: copy intent.terms and intent.research into the local draft only. Never preview, save, approve, or submit. Ignore the handoff when the ticket draft is dirty. */
function orderHandoff(symbol, source, terms, research) {
  return { tab: 'ticket', symbol, source, terms: clone(terms), research: clone(research) };
}
/** Parent Settings already selects intent.tab. Also honor focus session_freshness (quote-age rule) and native-report with reportKind positions; do not capture or save. */
function settingsHandoff(focus, extra = {}) {
  return { tab: 'Trading rules', focus, ...extra };
}
function rowsOf(value) {
  if (!Array.isArray(value) || !value.length || value.some((row) => !row || typeof row !== 'object' || Array.isArray(row))) return [];
  return value.map(row => ({...row, _id: row.id ?? row.lifecycle_id ?? JSON.stringify(row)}));
}
function objectRows(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  return Object.entries(value).map(([field, item]) => ({ id: field, field, value: item && typeof item === 'object' ? JSON.stringify(item) : text(item) }));
}
function EquityChart({ points, label }) {
  const usable = (points || []).filter((point) => Number.isFinite(Number(point.equity ?? point.equity_usd)));
  if (usable.length < 2) return <Typography>No retained dated equity curve is available. No curve is fabricated.</Typography>;
  const values = usable.map((point) => Number(point.equity ?? point.equity_usd));
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const d = values.map((value, index) => `${index ? 'L' : 'M'}${10 + (index / (values.length - 1)) * 680},${10 + ((high - value) / span) * 150}`).join(' ');
  return (
    <Box component="figure" sx={{ m: 0 }}>
      <Box component="svg" viewBox="0 0 700 180" role="img" aria-label={label} sx={{ width: '100%', color: 'primary.main' }}>
        <path d={d} fill="none" stroke="currentColor" strokeWidth="2" />
      </Box>
      <Typography component="figcaption" variant="body2">{label}. Exact dated observations stay in the table.</Typography>
    </Box>
  );
}
function Choice({ label, value, onChange, options, disabled }) {
  return (
    <FormControl fullWidth disabled={disabled}>
      <InputLabel>{label}</InputLabel>
      <Select label={label} value={value ?? ''} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <MenuItem key={option.value} value={option.value} disabled={option.disabled}>{option.label}</MenuItem>)}
      </Select>
    </FormControl>
  );
}
function Field({ label, value, onChange, disabled, type = 'text' }) {
  return <TextField fullWidth label={label} type={type} value={value ?? ''} disabled={disabled} onChange={(event) => onChange(event.target.value)} />;
}
function ReportTable({ name, report }) {
  const fields = {
    Orders: ['instrument_id', 'side', 'type', 'quantity', 'filled_qty', 'price', 'trigger_price', 'avg_px', 'status'],
    Fills: ['instrument_id', 'order_side', 'last_qty', 'last_px', 'currency', 'commission', 'ts_event'],
    Positions: ['instrument_id', 'side', 'quantity', 'avg_px_open', 'avg_px_close', 'realized_pnl', 'ts_opened', 'ts_closed'],
    Account: ['currency', 'total', 'free', 'locked'],
  }[name] || [];
  if (!Array.isArray(report?.data) || !Array.isArray(report.columns)) return <Alert severity="warning">{name} native report unavailable.</Alert>;
  if (!report.data.length) return <Typography>No {name.toLowerCase()}.</Typography>;
  const columns = nativeReportColumns(report).filter(column => column.id === 'index' || fields.includes(column.label));
  const rows = report.data.map((cells, i) => ({id: i, index: report.index?.[i], cells}));
  return <DataTable label={`${name} native report`} rows={rows} columns={columns} getRowId={(row) => row.id} empty="No rows." />;
}
function cleanOperand(value) {
  if (value?.kind === 'price') return { kind: value.kind, field: value.field };
  if (value?.kind === 'indicator') return { kind: value.kind, name: value.name };
  if (value?.kind === 'parameter') return { kind: value.kind, name: value.name, units: value.units };
  return { kind: 'constant', value: value?.value, units: value?.units };
}
function integerField(value, label) {
  if (String(value).trim() === '' || !Number.isSafeInteger(Number(value))) throw new Error(`Enter an explicit integer for ${label}.`);
  return Number(value);
}

function OperandEditor({ title, value, onChange, quantity = false, priceOnly = false, parameters = [], disabled }) {
  const operand = value || { kind: quantity ? 'constant' : 'price' };
  const kinds = quantity ? ['constant', 'parameter'] : ['price', 'indicator', 'constant', 'parameter'];
  const units = quantity ? ['shares'] : priceOnly ? ['price'] : ['price', '0-100', '0-1', 'shares'];
  return (
    <Stack spacing={1} component="fieldset" sx={{ border: 1, borderColor: 'divider', p: 1.5 }}>
      <Typography component="legend" variant="body2">{title}</Typography>
      <Choice label="Operand kind" value={operand.kind || ''} disabled={disabled} onChange={(kind) => onChange({ ...operand, kind })} options={kinds.map((kind) => ({ value: kind, label: kind }))} />
      {operand.kind === 'price' ? <Choice label="Recorded field" value={operand.field || ''} disabled={disabled} onChange={(field) => onChange({ ...operand, field })} options={['open', 'high', 'low', 'close'].map((field) => ({ value: field, label: field }))} /> : null}
      {operand.kind === 'indicator' ? <Choice label="Indicator" value={operand.name || ''} disabled={disabled} onChange={(name) => onChange({ ...operand, name })} options={(priceOnly ? INDICATORS.filter((name) => !['rsi', 'mfi'].includes(name)) : INDICATORS).map((name) => ({ value: name, label: name }))} /> : null}
      {operand.kind === 'parameter' ? <Choice label="Finite parameter name" value={operand.name || ''} disabled={disabled} onChange={(name) => onChange({ ...operand, name })} options={[{ value: '', label: 'Choose explicitly' }, ...parameters.filter(Boolean).map((name) => ({ value: name, label: name }))]} /> : null}
      {operand.kind === 'constant' || !operand.kind ? <Field label="Exact decimal value" value={operand.value || ''} disabled={disabled} onChange={(next) => onChange({ ...operand, kind: operand.kind || 'constant', value: next })} /> : null}
      <Choice label="Units" value={operand.units || ''} disabled={disabled} onChange={(next) => onChange({ ...operand, units: next })} options={units.map((unit) => ({ value: unit, label: unit }))} />
    </Stack>
  );
}

function useBoundIdentity() {
  const { state } = useDesk();
  return [state?.server_instance_id, state?.store_generation, state?.nautilus?.connection_session].join('|');
}

export function StrategyView() {
  const desk = useDesk();
  const { api, act, page, stateError, navigation, clearNavigation } = desk;
  const identity = useBoundIdentity();
  const [engine, setEngine] = useState('simulations');
  const [view, setView] = useState('setup');
  const [sources, setSources] = useState(null);
  const [evalDraft, setEvalDraft] = useState(blankEval);
  const [simItem, setSimItem] = useState(null);
  const [scenario, setScenario] = useState({ start: '', end: '', fee_usd: '0' });
  const [scenarioStatus, setScenarioStatus] = useState('');
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const modelFile = useRef(null);
  const modelJson = useRef(null);
  const [benchmark, setBenchmark] = useState(null);
  const [strategy, setStrategy] = useState(blankStrategy);
  const [execution, setExecution] = useState(blankExecution);
  const [experiment, setExperiment] = useState(blankExperiment);
  const [strategyId, setStrategyId] = useState('');
  const [strategyRevision, setStrategyRevision] = useState(null);
  const [strategyDirty, setStrategyDirty] = useState(true);
  const [experimentDirty, setExperimentDirty] = useState(true);
  const [branch, setBranch] = useState(null);
  const [expItem, setExpItem] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [eventEvidence, setEventEvidence] = useState(null);
  const [compared, setCompared] = useState([]);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const consumedNavigation = useRef(new Set());
  const active = engine === 'simulations' ? simItem : expItem;
    const seenIdentity = useRef(identity);

    useEffect(() => {
      if (seenIdentity.current && seenIdentity.current !== identity) {
        setSimItem(null);
        setBenchmark(null);
        setExpItem(null);
        setComparison(null);
        setEventEvidence(null);
        setSources(null);
        setExperimentDirty(true);
        setLocalError('Saved plans, previews and results were unbound because the server, store generation or connection session changed. Setup drafts were kept. Load sources again before preview or run.');
      }
      seenIdentity.current = identity;
    }, [identity]);

        useEffect(() => {
          if (!navigation || navigation.page !== 'strategy' || consumedNavigation.current.has(navigation.id)) return;
          const intent = navigation.intent || {};
          const id = navigation.id;
                    if (intent.view === 'results' && intent.simulation_id) {
                      consumedNavigation.current.add(id);
            setEngine('simulations');
            setView('results');
            setLocalError('');
            api(`/api/evaluations?id=${encodeURIComponent(intent.simulation_id)}`).then((item) => {
              if (item?.id !== intent.simulation_id) {
                setSimItem(null);
                setLocalError('That saved simulation is unavailable.');
                return;
              }
              setSimItem(item);
            }).catch(() => {
              setSimItem(null);
              setLocalError('That saved simulation is unavailable.');
            });
            clearNavigation(id);
            return;
          }
          if (intent.kind === 'portfolio_scenario' || intent.model) {
                      consumedNavigation.current.add(id);
                      setEngine('simulations');
            setView('setup');
            setScenarioOpen(true);
            if (intent.model) modelJson.current = structuredClone(intent.model);
            setScenario({ start: intent.start || '', end: intent.end || '', fee_usd: intent.fee_usd ?? intent.fee ?? '' });
            setScenarioStatus(`Portfolio allocation draft loaded${intent.model?.name ? `: ${intent.model.name}` : ''}. Review the dates and fee, then run the historical scenario explicitly. Nothing was started.`);
            clearNavigation(id);
          }
        }, [navigation, clearNavigation, api]);

    useEffect(() => {
    if (page !== 'strategy' || !active?.id || !['queued', 'running', 'cancelling'].includes(active.status)) return undefined;
    const identity = active.id;
    const timer = setTimeout(() => {
      api(`/api/evaluations?id=${encodeURIComponent(identity)}`).then((fresh) => {
        if (fresh?.id !== identity) return;
        if (engine === 'simulations') setSimItem(fresh);
        else setExpItem(fresh);
      }).catch((error) => setLocalError(messageOf(error)));
    }, 5000);
    return () => clearTimeout(timer);
  }, [page, active?.id, active?.status, engine, api]);

  async function loadSources() {
    setBusy(true);
    setLocalError('');
    try {
      const loaded = await api('/api/evaluations');
      setSources(loaded);
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }
  async function openItem(id, nextView = 'results') {
    setView(nextView);
    setBusy(true);
    setLocalError('');
    try {
      const item = await api(`/api/evaluations?id=${encodeURIComponent(id)}`);
      if (item.kind === 'experiment_comparison') setComparison(item);
      else if (item.kind === 'experiment' || item.preview?.strategy) {
        setExpItem(item);
        setExperimentDirty(false);
        setEventEvidence(null);
      } else setSimItem(item);
      if (sources && Number.isSafeInteger(item.revision)) setSources({ ...sources, revision: item.revision });
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }
  async function savePreview() {
    if (!evalDraft.reviewed) { setLocalError('Review the scenario assumptions before saving a preview.'); return; }
    if (evalDraft.random_seed.trim() === '' || evalDraft.latency_ns.trim() === '') { setLocalError('Enter an explicit seed and latency.'); return; }
    const proposal = sources?.proposals?.find((item) => item.id === evalDraft.proposal_id);
    if (!proposal) { setLocalError('Choose an existing saved plan revision.'); return; }
    setBusy(true);
    setLocalError('');
    try {
      const item = await act('evaluation-preview', '/api/evaluations', {
        ...evalDraft, action: 'preview', proposal_revision: proposal.revision, currency: 'USD',
        currency_basis: 'declared_simulation_assumption', starting_holdings: [], submission_model: 'after_first_completed_bar',
        end_positions: 'leave_open', actual_fees: 'unknown', bar_path: 'open_high_low_close',
        random_seed: Number(evalDraft.random_seed), latency_ns: Number(evalDraft.latency_ns),
      });
      setSimItem(item);
      setView('results');
      setSources(await api('/api/evaluations'));
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }
  async function runSimulation() {
    if (!simItem?.preview || simItem.status !== 'preview') { setLocalError('Save and review an unchanged preview first.'); return; }
    setBusy(true);
    setLocalError('');
    try {
      const item = await act('evaluation-run', '/api/evaluations', { action: 'run', id: simItem.id, spec_sha256: simItem.spec_sha256 });
      setSimItem(item);
      setSources(await api('/api/evaluations'));
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }
  async function deleteSimulations() {
    const ids = (sources?.items || []).filter((item) => ['simulation', 'portfolio_scenario'].includes(item.kind)).map((item) => item.id);
    setConfirmDelete(false);
    if (!ids.length) return;
    setBusy(true);
    try {
      const result = await act('evaluation-delete', '/api/evaluations', { action: 'delete_simulations', ids, expected_revision: sources.revision });
      if (ids.includes(simItem?.id)) setSimItem(null);
      setBenchmark(null);
      setLocalError(`Deleted ${result.deleted} saved simulations.${result.warnings?.length ? ` ${result.warnings.join(' ')}` : ''}`);
      setSources(await api('/api/evaluations'));
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }
  async function runScenario() {
    if (scenarioBusy) return;
    setScenarioBusy(true);
    setLocalError('');
    try {
      const file = modelFile.current;
      if (!modelJson.current && !file) throw new Error('Select the original archived model JSON.');
      if (!modelJson.current) modelJson.current = JSON.parse(await file.text());
      const request = { action: 'portfolio_scenario', model: modelJson.current, start: scenario.start, end: scenario.end, fee_usd: scenario.fee_usd };
      setScenarioStatus('Preparing the simulation from saved daily prices…');
      let result = await api('/api/evaluations', request, { timeoutMs: 900000 });
      while (result.status === 'collecting') {
        setScenarioStatus(result.message || 'Collecting saved daily prices…');
        request.collection = result.collection;
        await new Promise((resolve) => setTimeout(resolve, 2000));
        result = await api('/api/evaluations', request, { timeoutMs: 900000 });
      }
      setSimItem(result);
      setView('results');
      setScenarioStatus(result.status || '');
      setSources(await api('/api/evaluations'));
    } catch (error) {
      setLocalError(messageOf(error));
      setScenarioStatus(messageOf(error));
    } finally {
      setScenarioBusy(false);
    }
  }
  async function loadBenchmark(collect) {
    const item = simItem;
    const curve = item?.result?.ledger?.equity_curve;
    if (item?.result?.kind !== 'portfolio_scenario' || !curve?.length) return;
    const comparison = { id: item.id, start: curve[0].date, end: curve.at(-1).date, busy: true, error: '', history: null };
    setBenchmark(comparison);
    try {
      let historyState = await api('/api/market-history');
      const matches = () => Object.values(historyState.data?.entries || {}).filter((entry) => entry.symbol === 'SPY' && entry.timeframe === '1Day' && entry.adjustment === 'all' && entry.start <= comparison.start && entry.end >= comparison.end && entry.complete && entry.pagination_complete && !entry.error).sort((a, b) => String(b.captured_at).localeCompare(String(a.captured_at)));
      if (collect) {
        const previous = new Set(Object.keys(historyState.data?.jobs || {}));
        historyState = await act('portfolio-benchmark', '/api/market-history', { action: 'start', symbols: ['SPY'], start: comparison.start, end: comparison.end, asof: comparison.end, adjustment: 'all', timeframe: '1Day', purpose: 'simulation_benchmark' });
        const job = Object.values(historyState.data?.jobs || {}).find((row) => !previous.has(row.id) && row.request?.purpose === 'simulation_benchmark' && row.request.start === comparison.start && row.request.end === comparison.end);
        if (!job) throw new Error('SPY collection could not be identified. Reopen this result to check retained data.');
        while (['queued', 'running'].includes(historyState.data?.jobs?.[job.id]?.status)) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          historyState = await api('/api/market-history');
        }
        if (historyState.data?.jobs?.[job.id]?.status !== 'completed') throw new Error(historyState.data?.jobs?.[job.id]?.symbols?.SPY?.error || 'SPY collection did not complete. Load the benchmark again to retry.');
      }
      const entry = matches()[0];
      if (!entry) throw new Error('SPY prices have not been collected for this period.');
      const history = await api(`/api/market-history?symbol=SPY&key=${encodeURIComponent(entry.key)}`);
      const closes = new Map();
      for (const bar of history.bars || []) closes.set(bar.t, closes.has(bar.t) ? NaN : Number(bar.raw?.c));
      const first = closes.get(comparison.start);
      const last = closes.get(comparison.end);
      if (history.symbol !== 'SPY' || history.timeframe !== '1Day' || history.adjustment !== 'all' || history.currency !== 'USD' || history.feed !== 'iex' || !history.complete || !history.pagination_complete || history.error || ![first, last].every((price) => Number.isFinite(price) && price > 0)) throw new Error('Benchmark unavailable. Complete dividend-adjusted SPY closing prices are required on both dates.');
      setBenchmark({ ...comparison, busy: false, history: { start: comparison.start, end: comparison.end, start_close: first, end_close: last, return_pct: (last / first - 1) * 100, source: history.source, captured_at: history.captured_at } });
    } catch (error) {
      setBenchmark({ ...comparison, busy: false, error: messageOf(error) });
    }
  }
  function strategyRequest() {
    const parameters = {};
    for (const parameter of strategy.parameters) {
      if (!parameter.name || parameters[parameter.name]) throw new Error('Each finite parameter needs a distinct name.');
      parameters[parameter.name] = { type: parameter.type, values: String(parameter.values || '').split(',').map((value) => value.trim()).filter(Boolean) };
    }
    const rule = (value) => ({ operator: value.operator, atoms: value.atoms.map((atom) => ({ left: cleanOperand(atom.left), comparison: atom.comparison, right: cleanOperand(atom.right) })) });
    return {
      version: 'declarative-equity-rules-v1', name: strategy.name, symbol: strategy.symbol, instrument_id: `${strategy.symbol}.ALPACA`,
      currency: 'USD', session: 'regular', quantity: cleanOperand(strategy.quantity), entry: rule(strategy.entry), exit: rule(strategy.exit), parameters,
      execution: { ...structuredClone(execution), limit_price: execution.limit_price ? cleanOperand(execution.limit_price) : null, stop_price: execution.stop_price ? cleanOperand(execution.stop_price) : null, exit_plan: execution.exit_plan ? Object.fromEntries(Object.entries(execution.exit_plan).map(([key, value]) => [key, cleanOperand(value)])) : null },
    };
  }
  function experimentRequest() {
    const request = structuredClone(experiment);
    delete request.history_key;
    delete request.benchmark_history_key;
    for (const key of ['train_sessions', 'validation_sessions', 'gap_sessions', 'oos_sessions', 'step_sessions']) request.window[key] = integerField(request.window[key], key);
    request.search.seed = integerField(request.search.seed, 'seed');
    request.search.max_trials = integerField(request.search.max_trials, 'maximum trials');
    request.search.sampler = request.search.mode === 'grid' ? 'GridSampler' : 'TPESampler';
    request.search.pruner = 'NopPruner';
    request.selection.minimum_closed_trades = integerField(request.selection.minimum_closed_trades, 'minimum closed trades');
    request.budgets.max_native_runs = integerField(request.budgets.max_native_runs, 'maximum native runs');
    for (const kind of ['experiment', 'trial']) request.budgets[`${kind}_seconds`] = request.budgets[`no_${kind}_time_cap`] ? null : integerField(request.budgets[`${kind}_seconds`], `${kind} deadline`);
    request.scenarios.forEach((item) => { item.random_seed = integerField(item.random_seed, 'scenario seed'); });
    request.currency_basis = 'declared_simulation_assumption';
    if (!request.benchmark_history_key) delete request.benchmark_history_key;
    return request;
  }
  function loadStrategy(definition) {
    setStrategyId(definition.id);
    setStrategyRevision(definition.revision);
    setExecution(structuredClone(definition.execution));
    setStrategy({ ...structuredClone(definition), parameters: Object.entries(definition.parameters || {}).map(([name, parameter]) => ({ name, type: parameter.type, values: parameter.values.join(', ') })) });
    setStrategyDirty(false);
    setExperimentDirty(true);
  }
  async function experimentAction(action) {
    setBusy(true);
    setLocalError('');
    try {
      const request = { expected_revision: sources.revision };
      if (action === 'save-strategy') Object.assign(request, { action: 'save_strategy', strategy_id: strategyId || undefined, strategy_revision: strategyRevision || undefined, strategy: strategyRequest() });
      else if (action === 'preview') {
        if (strategyDirty) throw new Error('Save the edited strategy revision before preview.');
        setView('results');
        Object.assign(request, { action: 'preview_experiment', strategy_id: strategyId, strategy_revision: strategyRevision, history_key: experiment.history_key, ...(experiment.benchmark_history_key ? { benchmark_history_key: experiment.benchmark_history_key } : {}), experiment: experimentRequest(), ...(branch ? { parent_id: branch.id, parent_spec_sha256: branch.spec_sha256 } : {}) });
      } else if (action === 'run') {
        if (experimentDirty || expItem?.status !== 'preview' || sources?.capabilities?.optimizer?.available !== true) throw new Error('Select an unchanged preview and an available optimizer before Run.');
        Object.assign(request, { action: 'run_experiment', id: expItem.id, spec_sha256: expItem.spec_sha256 });
      } else if (action === 'compare') Object.assign(request, { action: 'compare_experiments', ids: compared });
      else Object.assign(request, { action: action === 'cancel' ? 'cancel_experiment' : 'repeat_experiment', id: expItem.id, spec_sha256: expItem.spec_sha256 });
      const response = await act(`experiment-${action}`, '/api/evaluations', request);
      if (action === 'save-strategy') {
        const rows = (response.strategies || []).filter((row) => row.definition.id === response.saved_strategy_id);
        if (rows.length !== 1) throw new Error('Saved strategy identity is ambiguous; reload saved strategies.');
        setSources(response);
        loadStrategy(rows[0].definition);
      } else if (action === 'compare') {
        setComparison(response);
        setSources(await api('/api/evaluations'));
        setView('results');
      } else {
        setExpItem(response);
        setEventEvidence(null);
        setExperimentDirty(false);
        setSources(await api('/api/evaluations'));
      }
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }
  async function openEvent(id) {
    setLocalError('');
    try {
      setEventEvidence(await api(`/api/evaluations?id=${encodeURIComponent(expItem.id)}&event_id=${encodeURIComponent(id)}`));
    } catch (error) {
      setLocalError(messageOf(error));
    }
  }

  const simulations = (sources?.items || []).filter((item) => !['experiment', 'experiment_comparison'].includes(item.kind));
  const experiments = (sources?.items || []).filter((item) => item.kind === 'experiment');
  const comparisons = (sources?.items || []).filter((item) => item.kind === 'experiment_comparison');
  const proposal = sources?.proposals?.find((item) => item.id === evalDraft.proposal_id);
  const histories = (sources?.histories || []).filter((item) => !evalDraft.proposal_id || proposal?.terms?.symbol === item.symbol);
  const result = simItem?.result;
  const headlines = useMemo(() => {
    if (!result || result.kind === 'portfolio_scenario') return [];
    const metrics = result.metrics || {};
    const native = result.native_result;
    const summary = native?.summary || {};
    const currencies = Object.keys(native?.stats_pnls || {});
    const usd = currencies.length === 1 && currencies[0] === 'USD' ? native.stats_pnls.USD : null;
    const completed = ['completed', 'completed_with_limitations'].includes(result.status);
    const closedOnly = completed && count(summary['positions.open']) && Number(summary['positions.open']) === 0;
    return [
      ['net_return_pct', 'Net Return %', 'PnL% (total)'],
      ['total_pnl', 'Modeled P/L · USD', 'PnL (total)'],
      ['max_drawdown_pct', 'Max Drawdown %', null],
      ['closed_trades', 'Closed Trades', null],
    ].map(([key, label, nativeKey]) => {
      let value = metrics[key];
      let basis = 'Retained worker metrics.';
      if (!(key === 'closed_trades' ? count(value) : finite(value))) {
        value = null;
        if (nativeKey && closedOnly && finite(usd?.[nativeKey])) {
          value = usd[nativeKey];
          basis = `Native USD account-balance change from starting cash; no open positions. Exact source: native_result.stats_pnls.USD[${nativeKey}].`;
        } else if (key === 'closed_trades' && completed && count(summary['positions.closed'])) {
          value = summary['positions.closed'];
          basis = 'Exact native_result.summary[positions.closed] cache count.';
        } else basis = 'No supplied equivalent. Return ratios and a dollar curve are not substitutes.';
      }
      return { id: key, label, value: text(value), basis };
    });
  }, [result]);

  const setup = {simulations: (
    <Stack spacing={1.5}>
      <Typography>Isolated model over retained bars. Results never establish broker fills or account performance.</Typography>
      <Accordion expanded={scenarioOpen} onChange={(_event, open) => setScenarioOpen(open)}>
        <AccordionSummary>Model portfolio · historical scenario</AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1.5}>
            <Typography>Apply the archived model weights to historical data. This is not historical research performance or a broker result.</Typography>
            <Button component="label" variant="outlined">Original model archive<input hidden type="file" accept="application/json" onChange={(event) => { modelFile.current = event.target.files?.[0] || null; modelJson.current = null; setScenarioStatus(modelFile.current ? `Selected archive: ${modelFile.current.name}` : ''); }} /></Button>
            <Field label="Start date" type="date" value={scenario.start} onChange={(start) => setScenario({ ...scenario, start })} />
            <Field label="End date" type="date" value={scenario.end} onChange={(end) => setScenario({ ...scenario, end })} />
            <Field label="Fee per order / USD" value={scenario.fee_usd} onChange={(fee_usd) => setScenario({ ...scenario, fee_usd })} />
            <Button variant="contained" disabled={scenarioBusy} onClick={runScenario}>Run historical scenario</Button>
            <Typography role="status">{scenarioStatus || 'No archive selected.'}</Typography>
          </Stack>
        </AccordionDetails>
      </Accordion>
      <Button variant="outlined" disabled={busy} onClick={loadSources}>Load Saved Plans & Data</Button>
      {!sources ? <Typography>Load saved plans and data to select an exact revision and raw daily history receipt.</Typography> : (
        <>
          <Choice label="Immutable saved plan revision" value={evalDraft.proposal_id} onChange={(proposal_id) => { setEvalDraft({ ...evalDraft, proposal_id, history_key: '' }); setSimItem(null); }} options={[{ value: '', label: 'Choose explicitly' }, ...(sources.proposals || []).map((item) => ({ value: item.id, label: `${item.terms.symbol} · ${item.terms.side} ${item.terms.quantity} ${item.terms.order_type} ${item.terms.time_in_force} · revision ${item.revision}` }))]} />
          <Choice label="Saved raw daily history receipt" value={evalDraft.history_key} onChange={(history_key) => { setEvalDraft({ ...evalDraft, history_key }); setSimItem(null); }} options={[{ value: '', label: 'Choose explicitly' }, ...histories.map((item) => ({ value: item.key, label: `${item.symbol} · ${item.start} to ${item.end} · ${item.adjustment} · captured ${item.captured_at}` }))]} />
          {['start_at', 'end_at', 'decision_at'].map((key) => <Field key={key} label={`${key.replaceAll('_', ' ')} / ISO timestamp with timezone`} value={evalDraft[key]} onChange={(value) => { setEvalDraft({ ...evalDraft, [key]: value }); setSimItem(null); }} />)}
          <Choice label="Plan availability basis" value={evalDraft.decision_basis} onChange={(decision_basis) => { setEvalDraft({ ...evalDraft, decision_basis }); setSimItem(null); }} options={[{ value: '', label: 'Choose explicitly' }, { value: 'recorded_decision', label: 'On or after this revision was recorded' }, { value: 'hindsight_scenario', label: 'Historical scenario; availability not established' }]} />
          <Typography>Complete raw daily bars, sourced session calendar and instrument receipt are required. Split-adjusted data cannot be relabeled raw.</Typography>
          {['starting_cash', 'fee_usd', 'limit_fill_probability', 'slippage_probability', 'random_seed', 'latency_ns'].map((key) => <Field key={key} label={key.replaceAll('_', ' ')} value={evalDraft[key]} onChange={(value) => { setEvalDraft({ ...evalDraft, [key]: value }); setSimItem(null); }} />)}
          <Choice label="Fee charged per" value={evalDraft.fee_per} onChange={(fee_per) => { setEvalDraft({ ...evalDraft, fee_per }); setSimItem(null); }} options={[{ value: '', label: 'Choose explicitly' }, { value: 'order', label: 'Order' }, { value: 'fill', label: 'Fill' }]} />
          <FormControlLabel control={<Checkbox checked={evalDraft.reviewed} onChange={(event) => { setEvalDraft({ ...evalDraft, reviewed: event.target.checked }); setSimItem(null); }} />} label="I reviewed USD assumptions and empty starting holdings. Submit after the first completed daily bar; use OHLC ordering, FULL bracket activation and open ending positions. Actual fees are unknown." />
          <Button variant="contained" disabled={busy} onClick={savePreview}>Save Immutable Preview</Button>
        </>
      )}
      <Button variant="contained" disabled={busy || simItem?.status !== 'preview' || !simItem?.preview} onClick={runSimulation}>Run this exact simulation</Button>
      <Typography>Changing any setup field invalidates the selected preview. Run uses its saved ID and specification hash. Saved BUY whole-share USD equity MARKET, LIMIT or STOP_LIMIT plans with DAY/GTC. Empty starting holdings; SELL starting holdings are unavailable.</Typography>
    </Stack>
  ), experiments: (
    <ExperimentSetup sources={sources} busy={busy} strategy={strategy} setStrategy={setStrategy} execution={execution} setExecution={setExecution} experiment={experiment} setExperiment={setExperiment} strategyId={strategyId} strategyRevision={strategyRevision} strategyDirty={strategyDirty} setStrategyDirty={setStrategyDirty} setExperimentDirty={setExperimentDirty} branch={branch} expItem={expItem} onLoad={loadSources} onLoadStrategy={loadStrategy} onClearStrategy={() => { setStrategyId(''); setStrategyRevision(null); setStrategyDirty(true); setExperimentDirty(true); }} onAction={experimentAction} />
  )};

  const results = {simulations: (
    <Stack spacing={1.5}>
      {result?.kind === 'portfolio_scenario' ? <PortfolioResult result={result} benchmark={benchmark} onLoad={() => loadBenchmark(true)} /> : result ? (
        <>
          <Typography variant="h3">Modeled simulation result · {labelize(result.status)}</Typography>
          <Typography>Native engine {text(result.engine_version)} · reported orders {text(result.reports?.orders?.data?.length)} · fills {text(result.reports?.fills?.data?.length)} · positions {text(result.reports?.positions?.data?.length)}</Typography>
          {result.error ? <Alert severity="error">{result.error}</Alert> : null}
          <DataTable rows={headlines} columns={[{ id: 'label', label: 'Metric' }, { id: 'value', label: 'Value', numeric: true }, { id: 'basis', label: 'Basis' }]} getRowId={(row) => row.id} empty="No retained headline metrics." />
          {Array.isArray(result.equity_curve) ? <EquityChart points={result.equity_curve} label="Retained modeled equity / USD" /> : <Typography>Dollar equity curve unavailable in this saved-plan result. {text(result.benchmark?.reason || 'No matching benchmark supplied.')}</Typography>}
          {['Orders', 'Fills', 'Positions', 'Account'].map((name) => <Box key={name}><Typography variant="h4">{name}</Typography><ReportTable name={name} report={result.reports?.[name.toLowerCase()]} /></Box>)}
          <Evidence title="Model limitations and assumptions" data={{ limitations: result.limitations, assumptions: result.assumptions, return_series_basis: result.return_series_basis }} />
          <Evidence title="Complete native result, events, and source references" data={result} />
        </>
      ) : null}
      {simItem?.preview ? <Evidence title="Saved immutable preview" data={simItem.preview} /> : !result ? <Typography>No simulation selected. Save an immutable preview in Setup or open a retained simulation from Runs & Compare.</Typography> : null}
      <Button variant="contained" disabled={busy || simItem?.status !== 'preview' || !simItem?.preview} onClick={runSimulation}>Run this exact simulation</Button>
    </Stack>
  ), experiments: (
    <ExperimentResults item={expItem} comparison={comparison} eventEvidence={eventEvidence} busy={busy} dirty={experimentDirty} optimizer={sources?.capabilities?.optimizer?.available === true} onRun={() => experimentAction('run')} onCancel={() => experimentAction('cancel')} onRepeat={() => experimentAction('repeat')} onBranch={() => { if (!expItem?.preview?.strategy || !expItem.history_key) { setLocalError('Exact retained strategy or history selector is unavailable; cannot reconstruct a branch from latest data.'); return; } loadStrategy(expItem.preview.strategy); setStrategyId(''); setStrategyRevision(null); setStrategyDirty(true); setExperiment({ ...structuredClone(expItem.preview.request), history_key: expItem.history_key, benchmark_history_key: expItem.benchmark_history_key || '' }); setBranch({ id: expItem.id, spec_sha256: expItem.spec_sha256 }); setEngine('experiments'); setView('setup'); }} onEvent={openEvent} />
  )};
  const runs = {simulations: (
    <Stack spacing={1}>
      {!sources ? <Typography>Load saved plans and data in Setup to browse retained simulations.</Typography> : (
        <>
          <Button color="error" disabled={busy || !simulations.length} onClick={() => setConfirmDelete(true)}>Delete all saved simulations</Button>
          <DataTable rows={simulations.map((item) => ({ ...item, label: item.kind === 'portfolio_scenario' ? `Fixed portfolio · ${item.start} to ${item.end}` : `${item.proposal?.id} revision ${item.proposal?.revision}` }))} columns={[{ id: 'label', label: 'Saved simulation' }, { id: 'status', label: 'Status', render: (row) => <Status value={row.status} /> }]} getRowId={(row) => row.id} onRowClick={(row) => openItem(row.id)} empty="No saved simulations." />
        </>
      )}
    </Stack>
  ), experiments: (
    <Stack spacing={1}>
      {!sources ? <Typography>Load strategies, retained daily history, and experiment runs to inspect or compare walk-forward evaluations.</Typography> : (
        <>
          <DataTable rows={experiments} columns={[{ id: 'id', label: 'Experiment' }, { id: 'status', label: 'Status', render: (row) => <Status value={row.status} /> }, { id: 'spec_sha256', label: 'Specification' }]} getRowId={(row) => row.id} selectedIds={compared} onSelectionChange={ids => setCompared([...ids])} onRowClick={(row) => openItem(row.id)} empty="No saved experiments." />
          <Button disabled={busy || compared.length < 2} onClick={() => experimentAction('compare')}>Compare selected retained experiments</Button>
          <DataTable rows={comparisons} columns={[{ id: 'id', label: 'Saved comparison' }]} getRowId={(row) => row.id} onRowClick={(row) => openItem(row.id)} empty="No saved comparisons." />
        </>
      )}
    </Stack>
  )};

  return (
    <Page tabbed title="Strategy Lab" subtitle="Isolated model over retained bars. Results never establish broker fills or account performance." actions={<Status value={busy || scenarioBusy ? 'Working' : active?.status || 'No evaluation selected'} />}>
      <Stack spacing={2}>
        {stateError ? <Alert severity="warning">{stateError}</Alert> : null}
        {localError ? <Alert severity="error" onClose={() => setLocalError('')}>{localError}</Alert> : null}
        <Tabs value={engine} onChange={(_event, value) => setEngine(value)} aria-label="Strategy engines">
          <Tab value="simulations" label="Saved-Plan Simulations" />
          <Tab value="experiments" label="Walk-Forward Experiments" />
        </Tabs>
        <Tabs value={view} onChange={(_event, value) => setView(value)} aria-label="Strategy views">
          <Tab value="setup" label="Setup" />
          <Tab value="results" label="Preview & Results" />
          <Tab value="runs" label="Runs & Compare" />
        </Tabs>
        <Typography role="status">{localError || (busy ? 'Working…' : active?.status ? labelize(active.status) : 'No evaluation selected')}</Typography>
      </Stack>
      {['simulations', 'experiments'].flatMap(kind => [['setup', setup], ['results', results], ['runs', runs]].map(([name, panels]) =>
        <Box key={`${kind}-${name}`} role="tabpanel" hidden={engine !== kind || view !== name}>{panels[kind]}</Box>))}
      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle>Delete all saved simulations</DialogTitle>
        <DialogContent><Typography>Permanently delete all saved simulations and their unshared result files?</Typography></DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>Keep simulations</Button>
          <Button color="error" onClick={deleteSimulations}>Delete all saved simulations</Button>
        </DialogActions>
      </Dialog>
    </Page>
  );
}

function PortfolioResult({ result, benchmark, onLoad }) {
  const ledger = result.ledger;
  if (!ledger) return <Alert severity="error">{result.error || 'Portfolio calculation did not complete.'}</Alert>;
  const ending = Number(ledger.equity_curve?.at?.(-1)?.equity_usd);
  const capital = Number(result.starting_cash);
  const history = benchmark?.id === result.id || benchmark?.history ? benchmark : null;
  return (
    <Stack spacing={1.5}>
      <Typography variant="h3">Model portfolio · historical scenario</Typography>
      <Typography>{text(result.holdings_source_name || 'Holdings source not recorded')} · Holdings as of {text(result.holdings_as_of)} · {result.fractional_shares ? 'fractional' : 'whole'} shares.</Typography>
      <Typography>This is a hindsight scenario using a fixed holdings snapshot. Availability at the simulation start is not verified; these results do not establish point-in-time strategy performance.</Typography>
      <Typography>{text(result.start)} through {text(result.end)} · initial capital {Number.isFinite(capital) ? money(capital) : 'Unavailable'} · ending equity {money(ending)} · ending cash {money(ledger.cash_usd)}.</Typography>
      <Typography>Fee {money(result.fee_usd)} per entry order. No modeled slippage, reinvestment, cash interest or rebalancing. Distributions stay cash. Not historical research performance or broker performance.</Typography>
      <Typography role="status">{history?.busy ? 'Loading SPY comparison…' : history?.error || (history?.history ? '' : 'Load SPY prices for the same period.')}</Typography>
      <Button disabled={history?.busy} onClick={onLoad}>Load S&P 500 benchmark</Button>
      {history?.history ? <Typography>{history.history.start} through {history.history.end} · SPY dividend-adjusted closing prices · SPY return {number(history.history.return_pct)}%.</Typography> : null}
      <DataTable rows={rowsOf(ledger.events?.filter((row) => row.kind === 'entry'))} columns={[{ id: 'symbol', label: 'Symbol' }, { id: 'shares', label: 'Shares', numeric: true }, { id: 'price', label: 'Price', numeric: true }, { id: 'date', label: 'Date', type: 'date' }]} getRowId={(row) => row._id} empty="No historical entries retained." />
      <Evidence title="Native fills and retained accounting" data={result} />
    </Stack>
  );
}

function ExperimentSetup({ sources, busy, strategy, setStrategy, execution, setExecution, experiment, setExperiment, strategyId, strategyRevision, strategyDirty, setStrategyDirty, setExperimentDirty, branch, expItem, onLoad, onLoadStrategy, onClearStrategy, onAction }) {
  const disabled = busy;
  const markStrategy = (next) => { setStrategy(next); setStrategyDirty(true); setExperimentDirty(true); };
  const histories = (symbol) => (sources?.histories || []).filter((item) => !symbol || item.symbol === symbol);
  const reason = (item) => (item.adjustment !== 'raw' ? 'Requires raw adjustment' : item.complete !== true || item.pagination_complete !== true ? 'Incomplete retained history' : item.error ? `Source error: ${item.error}` : '');
  return (
    <Stack spacing={1.5}>
      <Typography>Retained daily data · isolated native simulation · whole-share USD equity and empty starting holdings. Closed-bar signals use a separately specified later execution event; results are modeled hindsight, not live or broker fills.</Typography>
      <Button variant="outlined" disabled={disabled} onClick={onLoad}>Load Strategies & Retained Data</Button>
      {!sources ? null : (
        <>
          <Evidence title="Installed capability and supported profile" data={sources.capabilities} />
          <Typography>{sources.capabilities?.optimizer?.available === true ? 'Required optimizer is available; runtime/profile and data validation remain separate.' : (sources.capabilities?.optimizer?.reason || 'Required optional optimizer is unavailable; preview remains available but Run is disabled.')}</Typography>
          <Choice label="Saved strategy revision" value={strategyId} disabled={disabled} onChange={(value) => { const row = sources.strategies?.find((item) => item.definition.id === value); if (row) onLoadStrategy(row.definition); else onClearStrategy(); }} options={[{ value: '', label: 'New strategy' }, ...(sources.strategies || []).map((row) => ({ value: row.definition.id, label: `${row.definition.name} · ${row.definition.symbol} · revision ${row.definition.revision}` }))]} />
          <Field label="Strategy name" value={strategy.name} disabled={disabled} onChange={(name) => markStrategy({ ...strategy, name })} />
          <Field label="One equity symbol" value={strategy.symbol} disabled={disabled} onChange={(symbol) => markStrategy({ ...strategy, symbol })} />
          <OperandEditor title="Quantity · whole shares" quantity value={strategy.quantity} parameters={strategy.parameters.map((item) => item.name)} disabled={disabled} onChange={(quantity) => markStrategy({ ...strategy, quantity })} />
          {strategy.parameters.map((parameter, index) => (
            <Stack key={index} spacing={1}>
              <Field label="Parameter name" value={parameter.name} disabled={disabled} onChange={(name) => markStrategy(setPath(strategy, `parameters.${index}.name`, name))} />
              <Choice label="Type" value={parameter.type} disabled={disabled} onChange={(type) => markStrategy(setPath(strategy, `parameters.${index}.type`, type))} options={['integer', 'decimal'].map((type) => ({ value: type, label: type }))} />
              <Field label="Exact values, comma-separated" value={parameter.values} disabled={disabled} onChange={(values) => markStrategy(setPath(strategy, `parameters.${index}.values`, values))} />
              <Button disabled={disabled} onClick={() => markStrategy({ ...strategy, parameters: strategy.parameters.filter((_item, itemIndex) => itemIndex !== index) })}>Remove parameter</Button>
            </Stack>
          ))}
          <Button disabled={disabled} onClick={() => markStrategy({ ...strategy, parameters: [...strategy.parameters, { name: '', type: 'integer', values: '' }] })}>Add finite parameter</Button>
          {['entry', 'exit'].map((name) => (
            <Accordion key={name} defaultExpanded={name === 'entry'}>
              <AccordionSummary>{name === 'entry' ? 'Entry rule' : 'Exit rule'}</AccordionSummary>
              <AccordionDetails>
                <Stack spacing={1}>
                  <Choice label="Combine conditions" value={strategy[name].operator} disabled={disabled} onChange={(operator) => markStrategy(setPath(strategy, `${name}.operator`, operator))} options={['ALL', 'ANY'].map((value) => ({ value, label: value }))} />
                  {strategy[name].atoms.map((atom, index) => (
                    <Stack key={index} spacing={1}>
                      <OperandEditor title="Left series/value" value={atom.left} parameters={strategy.parameters.map((item) => item.name)} disabled={disabled} onChange={(left) => markStrategy(setPath(strategy, `${name}.atoms.${index}.left`, left))} />
                      <Choice label="Comparison" value={atom.comparison} disabled={disabled} onChange={(comparison) => markStrategy(setPath(strategy, `${name}.atoms.${index}.comparison`, comparison))} options={['above', 'below', 'cross_above', 'cross_below'].map((value) => ({ value, label: value }))} />
                      <OperandEditor title="Right series/value" value={atom.right} parameters={strategy.parameters.map((item) => item.name)} disabled={disabled} onChange={(right) => markStrategy(setPath(strategy, `${name}.atoms.${index}.right`, right))} />
                      <Button disabled={disabled || strategy[name].atoms.length === 1} onClick={() => markStrategy({ ...strategy, [name]: { ...strategy[name], atoms: strategy[name].atoms.filter((_item, itemIndex) => itemIndex !== index) } })}>Remove condition</Button>
                    </Stack>
                  ))}
                  <Button disabled={disabled || strategy[name].atoms.length >= 16} onClick={() => markStrategy({ ...strategy, [name]: { ...strategy[name], atoms: [...strategy[name].atoms, blankAtom()] } })}>Add condition</Button>
                </Stack>
              </AccordionDetails>
            </Accordion>
          ))}
          <Choice label="Entry order type" value={execution.entry_order_type} disabled={disabled} onChange={(entry_order_type) => { setStrategyDirty(true); setExperimentDirty(true); setExecution({ ...execution, entry_order_type, limit_price: entry_order_type === 'MARKET' ? null : execution.limit_price || { kind: 'price', field: 'close' }, stop_price: entry_order_type === 'STOP_LIMIT' ? execution.stop_price || { kind: 'price', field: 'close' } : null }); }} options={['MARKET', 'LIMIT', 'STOP_LIMIT'].map((value) => ({ value, label: value }))} />
          <Choice label="Duration" value={execution.time_in_force} disabled={disabled} onChange={(time_in_force) => { setStrategyDirty(true); setExecution({ ...execution, time_in_force }); }} options={['DAY', 'GTC'].map((value) => ({ value, label: value }))} />
          {execution.entry_order_type !== 'MARKET' ? <OperandEditor title="Entry limit price" priceOnly value={execution.limit_price || { kind: 'price', field: 'close' }} disabled={disabled} onChange={(limit_price) => { setStrategyDirty(true); setExecution({ ...execution, limit_price }); }} /> : null}
          {execution.entry_order_type === 'STOP_LIMIT' ? <OperandEditor title="Entry stop trigger" priceOnly value={execution.stop_price || { kind: 'price', field: 'close' }} disabled={disabled} onChange={(stop_price) => { setStrategyDirty(true); setExecution({ ...execution, stop_price }); }} /> : null}
          {[['take_profit', 'Linked take-profit limit'], ['stop_price', 'Linked protective stop'], ['stop_limit_price', 'Protective stop limit · requires stop']].map(([key, label]) => (
            <Box key={key}>
              <FormControlLabel control={<Checkbox checked={Boolean(execution.exit_plan?.[key])} disabled={disabled || (key === 'stop_limit_price' && !execution.exit_plan?.stop_price)} onChange={(event) => { const exit_plan = { ...(execution.exit_plan || {}) }; if (event.target.checked) exit_plan[key] = { kind: 'price', field: 'close' }; else { delete exit_plan[key]; if (key === 'stop_price') delete exit_plan.stop_limit_price; } setStrategyDirty(true); setExecution({ ...execution, exit_plan: Object.keys(exit_plan).length ? exit_plan : null }); }} />} label={label} />
              {execution.exit_plan?.[key] ? <OperandEditor title={label} priceOnly value={execution.exit_plan[key]} disabled={disabled} onChange={(value) => { setStrategyDirty(true); setExecution({ ...execution, exit_plan: { ...execution.exit_plan, [key]: value } }); }} /> : null}
            </Box>
          ))}
          <Typography>Native FULL-entry activation: a partial entry may remain unprotected. No pyramiding or duplicate exits. Selected timing: native OHLC-path next modeled open. These are modeled events, not actual session opens, ticks, BBO or liquidity.</Typography>
          <Button disabled={disabled} onClick={() => onAction('save-strategy')}>Save strategy {strategyId ? 'new revision' : 'definition'}</Button>
          <Typography>{strategyDirty ? 'Unsaved strategy edits; save a new revision before preview.' : `Saved strategy revision ${strategyRevision} selected.`}</Typography>
          {branch ? <Typography>New branch of {branch.id} · parent spec {branch.spec_sha256}. Retained cache selectors are explicit.</Typography> : null}
          <Choice label="Exact retained history receipt" value={experiment.history_key} disabled={disabled} onChange={(history_key) => { setExperiment({ ...experiment, history_key }); setExperimentDirty(true); }} options={[{ value: '', label: 'Choose complete raw daily history' }, ...histories(strategy.symbol).map((item) => ({ value: item.key, label: `${item.symbol} · ${item.start} to ${item.end} · ${item.adjustment} · ${reason(item) || 'Source selection available'}`, disabled: Boolean(reason(item)) }))]} />
          <Choice label="Optional retained benchmark receipt" value={experiment.benchmark_history_key} disabled={disabled} onChange={(benchmark_history_key) => { setExperiment({ ...experiment, benchmark_history_key }); setExperimentDirty(true); }} options={[{ value: '', label: 'No benchmark' }, ...histories('').map((item) => ({ value: item.key, label: `${item.symbol} · ${item.start} to ${item.end}`, disabled: Boolean(reason(item)) }))]} />
          <Field label="Window start · ISO timestamp with timezone" value={experiment.start_at} disabled={disabled} onChange={(start_at) => { setExperiment({ ...experiment, start_at }); setExperimentDirty(true); }} />
          <Field label="Window end · ISO timestamp with timezone" value={experiment.end_at} disabled={disabled} onChange={(end_at) => { setExperiment({ ...experiment, end_at }); setExperimentDirty(true); }} />
          <Choice label="Strategy availability basis" value={experiment.decision_basis} disabled={disabled} onChange={(decision_basis) => { setExperiment({ ...experiment, decision_basis }); setExperimentDirty(true); }} options={['recorded_decision', 'hindsight_scenario'].map((value) => ({ value, label: value }))} />
          <Field label="Scenario starting cash / USD" value={experiment.starting_cash} disabled={disabled} onChange={(starting_cash) => { setExperiment({ ...experiment, starting_cash }); setExperimentDirty(true); }} />
          <Choice label="Training mode" value={experiment.window.mode} disabled={disabled} onChange={(mode) => { setExperiment(setPath(experiment, 'window.mode', mode)); setExperimentDirty(true); }} options={['rolling', 'expanding'].map((value) => ({ value, label: value }))} />
          {['train_sessions', 'validation_sessions', 'gap_sessions', 'oos_sessions', 'step_sessions'].map((key) => <Field key={key} label={key.replaceAll('_', ' ')} value={experiment.window[key]} disabled={disabled} onChange={(value) => { setExperiment(setPath(experiment, `window.${key}`, value)); setExperimentDirty(true); }} />)}
          <Choice label="Search mode" value={experiment.search.mode} disabled={disabled} onChange={(mode) => { setExperiment(setPath(experiment, 'search.mode', mode)); setExperimentDirty(true); }} options={['grid', 'adaptive'].map((value) => ({ value, label: value }))} />
          <Field label="Sampler seed" value={experiment.search.seed} disabled={disabled} onChange={(seed) => { setExperiment(setPath(experiment, 'search.seed', seed)); setExperimentDirty(true); }} />
          <Field label="Maximum trials" value={experiment.search.max_trials} disabled={disabled} onChange={(max_trials) => { setExperiment(setPath(experiment, 'search.max_trials', max_trials)); setExperimentDirty(true); }} />
          <Choice label="Objective" value={experiment.selection.objective} disabled={disabled} onChange={(objective) => { setExperiment(setPath(experiment, 'selection.objective', objective)); setExperimentDirty(true); }} options={METRICS.map((value) => ({ value, label: value }))} />
          <Choice label="Direction" value={experiment.selection.direction} disabled={disabled} onChange={(direction) => { setExperiment(setPath(experiment, 'selection.direction', direction)); setExperimentDirty(true); }} options={['maximize', 'minimize'].map((value) => ({ value, label: value }))} />
          <Choice label="Secondary tie-break metric" value={experiment.selection.secondary_metric} disabled={disabled} onChange={(secondary_metric) => { setExperiment(setPath(experiment, 'selection.secondary_metric', secondary_metric)); setExperimentDirty(true); }} options={METRICS.map((value) => ({ value, label: value }))} />
          <Choice label="Secondary direction" value={experiment.selection.secondary_direction} disabled={disabled} onChange={(secondary_direction) => { setExperiment(setPath(experiment, 'selection.secondary_direction', secondary_direction)); setExperimentDirty(true); }} options={['maximize', 'minimize'].map((value) => ({ value, label: value }))} />
          <Field label="Minimum closed trades" value={experiment.selection.minimum_closed_trades} disabled={disabled} onChange={(minimum_closed_trades) => { setExperiment(setPath(experiment, 'selection.minimum_closed_trades', minimum_closed_trades)); setExperimentDirty(true); }} />
          <Field label="Maximum native runs" value={experiment.budgets.max_native_runs} disabled={disabled} onChange={(max_native_runs) => { setExperiment(setPath(experiment, 'budgets.max_native_runs', max_native_runs)); setExperimentDirty(true); }} />
          {['experiment', 'trial'].map((kind) => (
            <Box key={kind}>
              <Field label={`${kind} deadline / seconds`} value={experiment.budgets[`${kind}_seconds`]} disabled={disabled} onChange={(value) => { setExperiment(setPath(experiment, `budgets.${kind}_seconds`, value)); setExperimentDirty(true); }} />
              <FormControlLabel control={<Checkbox checked={experiment.budgets[`no_${kind}_time_cap`]} onChange={(event) => { setExperiment(setPath(experiment, `budgets.no_${kind}_time_cap`, event.target.checked)); setExperimentDirty(true); }} />} label={`Explicitly no ${kind} time cap`} />
            </Box>
          ))}
          {experiment.scenarios.map((item, index) => (
            <Stack key={index} spacing={1}>
              <Typography>Scenario {index + 1}</Typography>
              {['id', 'fee_usd', 'limit_fill_probability', 'slippage_probability', 'random_seed'].map((key) => <Field key={key} label={key.replaceAll('_', ' ')} value={item[key]} disabled={disabled} onChange={(value) => { setExperiment(setPath(experiment, `scenarios.${index}.${key}`, value)); setExperimentDirty(true); }} />)}
              <Choice label="fee per" value={item.fee_per} disabled={disabled} onChange={(fee_per) => { setExperiment(setPath(experiment, `scenarios.${index}.fee_per`, fee_per)); setExperimentDirty(true); }} options={['order', 'fill'].map((value) => ({ value, label: value }))} />
              <Typography>Latency is 0 ns for this declared profile. Fees, fill probabilities and slippage are assumptions; actual fees remain unknown.</Typography>
              <Button disabled={disabled || experiment.scenarios.length === 1} onClick={() => { setExperiment({ ...experiment, scenarios: experiment.scenarios.filter((_item, itemIndex) => itemIndex !== index) }); setExperimentDirty(true); }}>Remove scenario</Button>
            </Stack>
          ))}
          <Button disabled={disabled} onClick={() => { setExperiment({ ...experiment, scenarios: [...experiment.scenarios, { id: `scenario-${experiment.scenarios.length + 1}`, fee_usd: '', fee_per: '', limit_fill_probability: '', slippage_probability: '', random_seed: '0', latency_ns: 0 }] }); setExperimentDirty(true); }}>Add scenario</Button>
          <Button variant="contained" disabled={disabled || !strategyId || strategyDirty} onClick={() => onAction('preview')}>Save Immutable Preview</Button>
          <Button variant="contained" disabled={disabled || experimentDirty || expItem?.status !== 'preview' || sources.capabilities?.optimizer?.available !== true} onClick={() => onAction('run')}>Run this exact experiment</Button>
          <Typography>Changed setup invalidates Run. Run binds the saved ID and exact specification hash. Preview does not run evaluation or collect data.</Typography>
        </>
      )}
    </Stack>
  );
}

function ExperimentResults({ item, comparison, eventEvidence, busy, dirty, optimizer, onRun, onCancel, onRepeat, onBranch, onEvent }) {
  const result = item?.result;
  const terminal = Boolean(result) && !['preview', 'queued', 'running', 'cancelling'].includes(item?.status);
  return (
    <Stack spacing={1.5}>
      {!item && !comparison ? <Typography>No experiment or comparison selected. Load experiment sources in Setup, save an immutable experiment preview, or open a retained experiment from Runs.</Typography> : null}
      {item ? (
        <>
          <Typography>Experiment {item.id} · {item.status} · spec {item.spec_sha256} · {dirty ? 'Editor changed; save a new preview before Run.' : 'Exact saved preview selected.'}</Typography>
          {result ? <Typography>Analytical outcome: {result.analytical_outcome === 'no_qualifier' ? 'Finished — no eligible strategy' : result.analytical_outcome === 'selection_gaps' ? 'Finished — selection gaps' : text(result.analytical_outcome)}. Negative OOS performance is a result, not a reason to reselect.</Typography> : null}
          {result ? <DataTable rows={objectRows(result.counts)} columns={[{ id: 'field', label: 'Count' }, { id: 'value', label: 'Value', numeric: true }]} getRowId={(row) => row.id} empty="No retained counts." /> : null}
          <DataTable rows={rowsOf(result?.folds)} columns={[{ id: 'id', label: 'Fold' }, { id: 'status', label: 'Status', render: (row) => <Status value={row.status} /> }, { id: 'selected_trial_id', label: 'Selected trial' }, { id: 'reason', label: 'Reason' }]} getRowId={(row) => row._id} empty="No fold outcomes retained." />
          <Evidence title="Saved experiment preview" data={item.preview} />
          <Evidence title="Exact terminal result, native reports and source references" data={result || { status: 'No terminal result retained.' }} />
          {['queued', 'running', 'cancelling'].includes(item.status) ? <Button disabled={busy} onClick={onCancel}>Request cancellation</Button> : null}
          <Button disabled={busy} onClick={onBranch}>Edit configuration as a new branch</Button>
          <Button disabled={busy} onClick={onRepeat}>Create a separate repeat / branch preview</Button>
          <Typography>A repeat receives a new ID and requires explicit Run. Exact resume, pruning, carry, overlapping OOS and wider asset/order profiles remain unavailable.</Typography>
          <Button variant="contained" disabled={busy || dirty || item.status !== 'preview' || !optimizer} onClick={onRun}>Run this exact experiment</Button>
          <DataTable rows={(item.events || []).map((event) => ({ ...event, where: [event.fold_id, event.trial_id, event.phase, event.scenario_id].filter(Boolean).join(' / ') }))} columns={[{ id: 'ordinal', label: 'Ordinal', numeric: true }, { id: 'type', label: 'Event' }, { id: 'where', label: 'Fold / trial / scenario' }]} getRowId={(row) => row.id} onRowClick={(row) => onEvent(row.id)} empty="No execution events retained for this preview." />
          {eventEvidence ? <Evidence title="Exact retained native event and reports" data={eventEvidence} /> : null}
        </>
      ) : null}
      {comparison ? <Evidence title="Immutable member references and exact comparison evidence" data={comparison.comparison || comparison} /> : null}
      {comparison?.comparison?.rows ? <DataTable rows={comparison.comparison.rows.map((row, index) => ({ id: row.experiment_id || String(index), experiment_id: row.experiment_id, status: row.status, coverage: JSON.stringify(row.coverage ?? null) }))} columns={[{ id: 'experiment_id', label: 'Experiment' }, { id: 'status', label: 'Status' }, { id: 'coverage', label: 'Coverage' }]} getRowId={(row) => row.id} empty="No comparison rows retained." /> : null}
    </Stack>
  );
}

function journalKind(item) {
  return { human_proposal: 'Human proposal', allocation_basket: 'Human allocation basket', saved_native_draft: 'Saved native draft' }[item.kind] || labelize(item.kind);
}

export function JournalView() {
  const desk = useDesk();
  const { state, api, act, refresh, page, navigate, setSelectedSymbol, stateError } = desk;
  const [tab, setTab] = useState('decisions');
  const [decisionTab, setDecisionTab] = useState('rationale');
  const [record, setRecord] = useState(null);
  const [selected, setSelected] = useState('');
  const [exports, setExports] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [settings, setSettings] = useState(null);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [symbols, setSymbols] = useState('');
  const [collectionId, setCollectionId] = useState('');
  const [collections, setCollections] = useState({});
  const [collectionError, setCollectionError] = useState('');
  const [outcomeId, setOutcomeId] = useState('');
  const [asOf, setAsOf] = useState('');
  const [loading, setLoading] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [localError, setLocalError] = useState('');
  const bound = [state?.server_instance_id, state?.store_generation, state?.nautilus?.connection_session].join('|');
    const generation = useRef(bound);

    useEffect(() => {
      if (generation.current && generation.current !== bound) {
        setRecord(null);
        setCollections({});
        setConflict(true);
        setLocalError('Saved records were unbound because the server, store generation or connection session changed. Notes and reporting drafts were kept. Reload before saving.');
      }
      generation.current = bound;
    }, [bound]);
  useEffect(() => {
    if (page !== 'journal' || record) return undefined;
    let cancelled = false;
    setLoading(true);
    api('/api/reporting').then((loaded) => { if (!cancelled) { setRecord(loaded); setConflict(false); setLocalError(''); setLoading(false); } }).catch((error) => { if (!cancelled) { setLocalError(messageOf(error)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [page, record, api, bound]);

  async function reload(discard) {
    setLoading(true);
    try {
      const loaded = await api('/api/reporting');
      setRecord(loaded);
      setConflict(false);
      setLocalError('');
      if (discard) { setDrafts({}); setSettings(null); }
    } catch (error) {
      setLocalError(messageOf(error));
    } finally {
      setLoading(false);
    }
  }
  async function openCollection(id = collectionId) {
    setCollectionId(id);
    if (!id || collections[id]) return;
    setCollectionError('');
    setLoading(true);
    try {
      const data = await api(`/api/reporting/collections/${encodeURIComponent(id)}`);
      if (data.id !== id) throw new Error('History collection identity differs');
      setCollections((current) => ({ ...current, [id]: data }));
    } catch (error) {
      setCollectionError(messageOf(error));
    } finally {
      setLoading(false);
    }
  }
  async function journalAction(request) {
    if (loading || conflict || !record) return;
    setLoading(true);
    setLocalError('');
    try {
        const body = { ...request, expected_revision: record.revision };
        const result = request.action === 'collect'
          ? await api('/api/reporting', body, { timeoutMs: 600000 })
          : await act(`journal-${request.action}`, '/api/reporting', body);
        if (request.action === 'collect') {
          try { await refresh({fresh: true}); } catch (failure) {
            setLocalError(`The request completed, but the updated workspace could not be read: ${failure.message}. Check current status before repeating the action.`);
          }
          setRecord(result);
          const created = result.data?.collections?.[0];
          if (created) await openCollection(created.id);
          return;
        }
        if (result instanceof Blob) downloadText(result, request.kind ? `${request.kind}.csv` : 'tradingagents-export', result.type || 'application/octet-stream');
        else if (request.action === 'export') downloadText(JSON.stringify(result.export, null, 2), 'tradingagents-selected-decisions.json', 'application/json');
        else if (request.action === 'export_csv') downloadText(result.csv, result.filename, 'text/csv;charset=utf-8');
      else {
        setRecord(result);
        if (request.action === 'settings') setSettings(null);
        if (request.action === 'note') setDrafts((current) => { const next = { ...current }; delete next[request.id]; return next; });
        if (request.action === 'refresh_methods') {
          setCollections((current) => { const next = { ...current }; delete next[request.collection_id]; return next; });
          await openCollection(request.collection_id);
        }
      }
    } catch (error) {
      setLocalError(messageOf(error));
      if (error.status === 409) setConflict(true);
    } finally {
      setLoading(false);
    }
  }
  async function collect() {
    if (!record || conflict) return;
    setLoading(true);
    try {
      const saved = await api('/api/reporting', { action: 'collect', start, end, expected_revision: record.revision }, { timeoutMs: 600000 });
            try { await refresh({fresh: true}); } catch (failure) {
              setLocalError(`The request completed, but the updated workspace could not be read: ${failure.message}. Check current status before repeating the action.`);
            }
            setRecord(saved);
      const item = saved.data?.collections?.[0];
      if (item) await openCollection(item.id);
    } catch (error) {
      setLocalError(messageOf(error));
      if (error.status === 409) setConflict(true);
    } finally {
      setLoading(false);
    }
  }

  const decisions = record?.decisions || [];
  const item = decisions.find((row) => row.id === selected);
  const draft = item ? drafts[item.id] || { assumptions: record.data.entries?.[item.id]?.assumptions || '', review_date: record.data.entries?.[item.id]?.review_date || '', outcome_notes: record.data.entries?.[item.id]?.outcome_notes || '' } : null;
  const dirtyCount = Object.entries(drafts).filter(([id, value]) => ['assumptions', 'review_date', 'outcome_notes'].some((key) => (value[key] || '') !== (record?.data?.entries?.[id]?.[key] || ''))).length;
  const positions = state?.nautilus?.positions || state?.positions || [];
  const holding = item ? positions.find((position) => position.symbol === item.symbol) : null;
  const savedSettings = settings || { benchmark: record?.data?.benchmark?.symbol || '', currency: record?.data?.benchmark?.currency || '', treatment: record?.data?.benchmark?.treatment || '', horizon: record?.data?.horizon_days ?? '', reason: '' };
  const collection = collections[collectionId];
  const groups = record?.position_outcomes?.groups || [];

  return (
    <Page tabbed title="Decision Journal" subtitle={record ? `Saved reporting revision ${record.revision}` : 'Saved local decisions, notes, outcomes and account-history evidence.'} actions={<Button disabled={loading} onClick={() => reload(false)}>Reload saved journal</Button>}>
      <Stack spacing={2}>
            {stateError ? <Alert severity="warning">{stateError}</Alert> : null}
            {localError ? <Alert severity="error">{localError}</Alert> : null}
        {conflict ? <Alert severity="warning">Application records changed. Reload saved journal before saving.</Alert> : null}
      </Stack>
        {!record ? <Typography role="status">{loading ? 'Loading saved local records…' : 'Saved journal is not loaded.'}</Typography> : (
          <>
            <Tabs value={tab} onChange={(_event, value) => setTab(value)} aria-label="Journal views">
              <Tab value="decisions" label={`Decisions & Notes (${decisions.length})`} />
              <Tab value="outcomes" label={`Position Outcomes (${groups.length})`} />
              <Tab value="history" label="Account History" />
            </Tabs>
            <Box role="tabpanel" hidden={tab !== 'decisions'}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Stack spacing={1}>
                    <Stack direction="row" spacing={1}>
                      <Button disabled={!exports.length || loading || conflict} onClick={() => journalAction({ action: 'export', ids: exports })}>Export selected ({exports.length})</Button>
                      <Button disabled={!dirtyCount || loading} onClick={() => setDrafts({})}>Revert Unsaved Edits ({dirtyCount})</Button>
                    </Stack>
                    <DataTable label="Saved journal decisions" rows={decisions} selectedIds={exports} onSelectionChange={ids => setExports([...ids])} onRowClick={(row) => { setSelected(row.id); if (/^[A-Z][A-Z0-9.-]{0,9}$/.test(row.symbol || '')) setSelectedSymbol(row.symbol); setTab('decisions'); }}
                      columns={[{id: 'saved_at', label: 'Saved', type: 'dateTime', render: row => dateTime(row.saved_at)}, {id: 'symbol', label: 'Symbol'},
                        {id: 'kind', label: 'Kind', value: journalKind}, {id: 'terms', label: 'Call / Terms', value: row => row.terms ? [row.terms.side, row.terms.quantity ?? row.terms.qty, row.terms.order_type || row.terms.type].filter(Boolean).join(' ') : row.rationale},
                        {id: 'rationale', label: 'Rationale'}, {id: 'status', label: 'Status', render: row => <Status value={row.status}/>}]} getRowId={(row) => row.id} empty="No matching saved decisions. No research or trades are created to populate the journal." />
                  </Stack>
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  {!item || !draft ? <Typography>Select a saved decision to inspect its rationale, orders, outcomes and notes.</Typography> : (
                    <Stack spacing={1.5}>
                      <Typography variant="h2">{item.symbol || journalKind(item)} · {journalKind(item)}</Typography>
                      <Typography>Current holding: {holding ? `${holding.qty} shares` : 'FLAT (0 shares) or holding observation unavailable in this snapshot.'}</Typography>
                      <Stack direction="row" spacing={1}>
                        <Button disabled={loading || conflict} onClick={() => journalAction({ action: 'note', id: item.id, ...draft })}>Save journal note</Button>
                        {item.research && item.research_available ? <Button onClick={() => { setSelectedSymbol(item.symbol); navigate('research', { symbol: item.symbol, run_id: item.research.run_id, revision: item.research.revision ?? 0, report_key: item.research.report_key || null }); }}>Open Linked Research</Button> : null}
                                                {/^[A-Z][A-Z0-9.-]{0,9}$/.test(item.symbol || '') ? <Button onClick={() => { setSelectedSymbol(item.symbol); navigate('orders', orderHandoff(item.symbol, { page: 'journal', decision_id: item.id, kind: item.kind }, item.terms, item.research)); }}>Prepare Order (T)</Button> : null}
                      </Stack>
                                                                      {item.research ? <ResearchDisposition symbol={item.symbol} researchLink={item.research} /> : null}
                      <Tabs value={decisionTab} onChange={(_event, value) => setDecisionTab(value)}>
                        <Tab value="rationale" label="Rationale & Note" />
                        <Tab value="orders" label="Linked Orders & Outcome" />
                      </Tabs>
                      <Box role="tabpanel" hidden={decisionTab !== 'orders'} sx={{height: 'min(640px, 65vh)', overflow: 'auto'}}>
                        <Stack spacing={1}>
                          {(item.command_outcomes || []).map((command) => (
                            <Box key={command.command_id}>
                              <Typography>Command {command.command_id}</Typography>
                              <Typography>Broker outcome: {text(command.broker_outcome)} · filled {text(command.filled_quantity)} · native application: {text(command.native_application)}</Typography>
                              <Typography>Broker IDs {text((command.broker_order_ids || []).join(', ') || 'None recorded')} · fills {text((command.fill_ids || []).join(', ') || 'None recorded')}</Typography>
                              <Evidence title="Command approval, exact terms, broker receipts and historical native receipts" data={command} />
                            </Box>
                          ))}
                          {(item.position_outcome_ids || []).map((id) => <Button key={id} onClick={() => { setOutcomeId(id); setTab('outcomes'); }}>Shared position outcome {id}</Button>)}
                          {item.execution_plans?.length ? <Evidence title="Non-atomic basket completion and paused legs" data={item.execution_plans} /> : null}
                        </Stack>
                      </Box>
                      <Box role="tabpanel" hidden={decisionTab !== 'rationale'} sx={{height: 'min(640px, 65vh)', overflow: 'auto'}}>
                        <Stack spacing={1}>
                          <Typography>{journalKind(item)} · source revision {text(item.revision)} · saved {dateTime(item.saved_at)}</Typography>
                          <Typography>{item.rationale || 'No human rationale recorded in this source'}</Typography>
                          <Typography>Policy revision {text(item.policy_revision)} · broker order {text(item.broker_order_id || 'None recorded')} · fills {text(item.fill_ids?.join(', ') || 'None recorded')}</Typography>
                          <Typography>Approval record: {item.approval_recorded == null ? 'None recorded' : JSON.stringify(item.approval_recorded)}. This saved decision does not submit an order.</Typography>
                          {item.research && !item.research_available ? <Typography>Referenced research unavailable or replaced. Saved terms are unchanged.</Typography> : null}
                          <TextField label="Investor assumptions" multiline slotProps={{ htmlInput: { maxLength: 20000 } }} value={draft.assumptions} onChange={(event) => setDrafts({ ...drafts, [item.id]: { ...draft, assumptions: event.target.value } })} />
                                                    <TextField label="Investor review date" type="date" value={draft.review_date} onChange={(event) => setDrafts({ ...drafts, [item.id]: { ...draft, review_date: event.target.value } })} slotProps={{ inputLabel: { shrink: true } }} />
                                                    <TextField label="Later outcome notes" multiline slotProps={{ htmlInput: { maxLength: 20000 } }} value={draft.outcome_notes} onChange={(event) => setDrafts({ ...drafts, [item.id]: { ...draft, outcome_notes: event.target.value } })} />
                          <Typography>{record.data.entries?.[item.id] ? `Note revision ${record.data.entries[item.id].revision} · saved ${record.data.entries[item.id].saved_at}` : 'No saved follow-up note'}</Typography>
                          <Evidence title="Exact decision, source research and revision history" data={item} />
                          <Evidence title="Follow-up note history" data={record.data.entries?.[item.id]?.history || []} />
                        </Stack>
                      </Box>
                    </Stack>
                  )}
                </Grid>
              </Grid>
            </Box>
            <Box role="tabpanel" hidden={tab !== 'outcomes'}>
              <Stack spacing={1.5}>
                <Typography>One row per captured lifecycle. Dated native accounting is separate from broker statements and current holdings. No totals across lifecycles. No capture runs automatically.</Typography>
                <Button onClick={() => navigate('settings', settingsHandoff('native-report', { reportKind: 'positions', nativePanelOpen: true }))}>Capture Native Position Table in Settings</Button>
                <DataTable rows={groups} onRowClick={(row) => setOutcomeId(row.lifecycle_id)} columns={[{ id: 'instrument_id', label: 'Sym' },
                  {id: 'native_position', label: 'Lifecycle state', value: row => row.native_position?.side === 'FLAT' ? 'Closed' : ['LONG', 'SHORT'].includes(row.native_position?.side) ? 'Open' : null},
                  {id: 'quantity', label: 'Qty', numeric: true, value: row => row.native_position?.quantity},
                  {id: 'realized_pnl', label: 'Realized P/L', numeric: true, value: row => row.realized_pnl?.amount, render: row => row.realized_pnl ? `${row.realized_pnl.amount} ${row.realized_pnl.currency}` : 'Unavailable'},
                  {id: 'unrealized_pnl', label: 'Unrealized P/L', numeric: true, value: row => row.unrealized_pnl?.amount, render: row => row.unrealized_pnl ? `${row.unrealized_pnl.amount} ${row.unrealized_pnl.currency}` : 'Unavailable'},
                  {id: 'coverage', label: 'Coverage', value: row => row.coverage?.status}]} getRowId={(row) => row.lifecycle_id} empty="No attributable position outcomes have been captured." />
                {groups.filter((group) => group.lifecycle_id === outcomeId).map((group) => (
                  <Stack key={group.lifecycle_id} spacing={1}>
                    <Typography variant="h3">{group.instrument_id} · shared lifecycle {group.lifecycle_id}</Typography>
                    <Typography>Account {text(group.account_id)} · position {text(group.position_id)} · opening order {text(group.opening_order_id)} · latest capture {dateTime(group.latest_capture_at)}. This saved capture does not update automatically.</Typography>
                    <Typography>Native realized P/L already includes applied settlement-currency commissions. These are dated native results, not independently verified actual net profit or tax lots.</Typography>
                    {(group.coverage?.gaps || []).map((gap) => <Typography key={gap}>{gap}</Typography>)}
                    {(group.contributors || []).map((contributor) => (
                      <Box key={contributor.command_id}>
                        <Typography>Command {contributor.command_id} · proposal {text(contributor.proposal_id || 'External / not recorded')} · {contributor.origin}</Typography>
                        <Typography>Original thesis: {contributor.rationale || 'No saved rationale'}</Typography>
                        {(contributor.decision_links || []).map((id) => <Button key={id} onClick={() => { setSelected(id); setTab('decisions'); }}>{id}</Button>)}
                      </Box>
                    ))}
                    <Evidence title="Native open/closed snapshot, source precision, capture epochs and fee evidence" data={group} />
                  </Stack>
                ))}
                <Evidence title="Unattributed native observations — no decision allocation" data={record.position_outcomes?.unattributed || []} />
                <Evidence title="Retained capture identities and source artifacts" data={record.position_outcomes?.captures || []} />
              </Stack>
            </Box>
            <Box role="tabpanel" hidden={tab !== 'history'}>
              <Stack spacing={1.5}>
                <Typography>Explicit retrieval only · up to 366 days and 2,000 activities per collection. This does not place orders or run agents.</Typography>
                <Stack direction="row" spacing={1}>
                  <Button onClick={() => journalAction({ action: 'export_csv', kind: 'holdings' })}>Export full-account holdings CSV</Button>
                  <Button disabled={!collectionId} onClick={() => journalAction({ action: 'export_csv', kind: 'activity', collection_id: collectionId, ...(symbols.trim() ? { symbols: symbols.toUpperCase().split(/[\s,]+/).filter(Boolean) } : {}) })}>Export selected interval activity CSV</Button>
                  <Button disabled={!collectionId} onClick={() => journalAction({ action: 'export_csv', kind: 'performance', collection_id: collectionId })}>Export full-account selected-period performance CSV</Button>
                </Stack>
                <TextField label="Optional activity export symbols · blank = full account" value={symbols} onChange={(event) => setSymbols(event.target.value)} />
                <Field label="Start date" type="date" value={start} onChange={setStart} />
                <Field label="End date" type="date" value={end} onChange={setEnd} />
                <Button disabled={loading || conflict} onClick={collect}>Collect read-only broker history for this interval</Button>
                <Choice label="Saved history collection" value={collectionId} onChange={openCollection} options={[{ value: '', label: 'Choose a saved interval' }, ...(record.data.collections || []).map((item) => ({ value: item.id, label: `${item.requested_start} to ${item.requested_end} · ${item.collected_at}` }))]} />
                <Button disabled={!collectionId || loading} onClick={() => openCollection(collectionId)}>Open selected saved interval</Button>
                {collectionError ? <Alert severity="error" action={<Button onClick={() => openCollection(collectionId)}>Retry saved source</Button>}>{collectionError}</Alert> : null}
                {!collection ? <Typography>{collectionId ? 'Loading the selected saved account-history collection… No new broker history is fetched.' : 'No saved account-history collection selected. Loading saved records never fetches new broker history.'}</Typography> : <HistoryCollection data={collection} asOf={asOf} setAsOf={setAsOf} onRefresh={() => journalAction({ action: 'refresh_methods', collection_id: collectionId })} onBenchmark={() => journalAction({ action: 'benchmark_history', collection_id: collectionId, asof: asOf })} />}
                <Typography variant="h2">Your reporting choices</Typography>
                <Typography>A benchmark is the symbol you want to compare with your account over the same dates. Saving does not fetch data, place orders or schedule work.</Typography>
                <Field label="Comparison symbol (optional)" value={savedSettings.benchmark} onChange={(benchmark) => setSettings({ ...savedSettings, benchmark })} />
                <Field label="Comparison currency (USD required for comparison)" value={savedSettings.currency} onChange={(currency) => setSettings({ ...savedSettings, currency })} />
                <Choice label="What the comparison includes" value={savedSettings.treatment} onChange={(treatment) => setSettings({ ...savedSettings, treatment })} options={[{ value: '', label: 'Decide later' }, { value: 'price', label: 'Price change only (dividends excluded)' }, { value: 'total_return', label: 'Price change plus reinvested dividends (not supported)', disabled: true }]} />
                <Field label="Planned review horizon (whole calendar days, optional)" value={savedSettings.horizon} onChange={(horizon) => setSettings({ ...savedSettings, horizon })} />
                <TextField label="Optional note about these reporting choices" multiline value={savedSettings.reason} onChange={(event) => setSettings({ ...savedSettings, reason: event.target.value })} />
                <Button disabled={loading || conflict} onClick={() => journalAction({ action: 'settings', benchmark: savedSettings.benchmark ? { symbol: savedSettings.benchmark, currency: savedSettings.currency, treatment: savedSettings.treatment } : null, horizon_days: savedSettings.horizon === '' ? null : Number(savedSettings.horizon), reason: savedSettings.reason })}>Save reporting choices</Button>
              </Stack>
            </Box>
          </>
        )}
    </Page>
  );
}

function HistoryCollection({ data, asOf, setAsOf, onRefresh, onBenchmark }) {
  const points = data.points || [];
  const chartPoints = points.map((point) => ({ at: new Date(point.timestamp * 1000).toISOString(), equity: Number(point.equity) })).filter((point) => Number.isFinite(point.equity));
  return (
    <Stack spacing={1.5}>
      <Typography>Account {text(data.account_id)} · {text(data.currency || 'Currency unknown')} · {text(data.requested_start)} to {text(data.requested_end)} · captured {dateTime(data.collected_at)}</Typography>
      <Typography>{text(data.source)} · 1D · cashflow_types=ALL · {text(data.broker_rounding)}</Typography>
      <Typography>{text(data.raw_broker_percent_method)}</Typography>
      <EquityChart points={chartPoints} label="Broker-reported equity over the saved interval" />
      <DataTable rows={points.map(point => ({id: String(point.timestamp), time: new Date(point.timestamp * 1000).toISOString(), equity: point.equity, pnl: point.broker_profit_loss, fraction: point.broker_profit_loss_pct}))} columns={[{ id: 'time', label: 'Provider timestamp', type: 'dateTime' }, { id: 'equity', label: 'Equity / USD', numeric: true }, { id: 'pnl', label: 'Broker P&L / USD', numeric: true }, { id: 'fraction', label: 'Broker P&L fraction', numeric: true }]} getRowId={(row) => row.id} empty="Broker equity series unavailable." />
      <Typography>{data.technical_method_assessment?.accepted ? 'Supported performance method' : 'Unsupported or missing performance method'}</Typography>
      <Typography>{(data.technical_method_assessment?.reasons || ['No current method assessment recorded']).join('; ')}</Typography>
      <Button onClick={onRefresh}>Save method report from existing records</Button>
      <Field label="Benchmark symbol mapping as-of date" type="date" value={asOf} onChange={setAsOf} />
      <Button onClick={onBenchmark}>Queue selected benchmark history for this interval</Button>
      <Typography>Activity pagination {data.pagination_complete ? 'completed for its creation-time query' : 'incomplete'} · covered interval {data.interval_complete ? 'complete' : 'not established'} · calculation coverage {data.calculation_coverage_complete ? 'matched under the declared method' : 'incomplete'}</Typography>
      {[['Linked time-weighted return', data.time_weighted, 'return'], ['Modified Dietz estimate', data.dietz, 'estimate'], ['Drawdown', data.drawdown, 'value'], ['Benchmark excess price-return comparison', data.benchmark_comparison, 'excess_return']].map(([label, metric, key]) => <Typography key={label}><strong>{label}</strong> · {text(metric?.calculable ? metric[key] : 'Unavailable')} · method {text(metric?.method)} · {(metric?.readiness_reasons || [metric?.reason].filter(Boolean)).join('; ')}</Typography>)}
      <DataTable rows={(data.activities || []).map((activity) => ({ ...activity, issues: (activity.issues || []).join('; ') }))} columns={[{ id: 'id', label: 'ID' }, { id: 'activity_type', label: 'Type' }, { id: 'category', label: 'Classification' }, { id: 'amount', label: 'Recorded amount', numeric: true }, { id: 'time', label: 'Time / date', type: 'dateTime', value: row => row.time || row.date }, { id: 'issues', label: 'Limitation' }]} getRowId={(row) => row.id} empty="No activities retained." />
      <Typography>Deposits/withdrawals are external capital. Dividends remain investment income. Fees and unknown activity types are explicit; no zero-fee assumption is applied. Allocation observation does not reconstruct holdings for past dates.</Typography>
      <DataTable rows={data.allocation_observation?.positions || []} columns={[{ id: 'symbol', label: 'Symbol' }, { id: 'qty', label: 'Observed quantity', numeric: true }, { id: 'market_value', label: 'Source market value / USD', numeric: true }, { id: 'unrealized_pl', label: 'Source unrealized P&L / USD', numeric: true }, { id: 'reconciliation_status', label: 'Import' }]} getRowId={(row) => row.symbol || row.id} empty="No allocation positions retained." />
      <Stack spacing={0.5}>
        {(data.receipts || []).map((receipt, index) => <Link key={receipt.artifact?.sha256 || index} href={`/api/reporting/collections/${encodeURIComponent(data.id)}/receipts/${index}`} target="_blank" rel="noopener">Open receipt {index + 1} · {receipt.path} · SHA-256 {receipt.artifact?.sha256}</Link>)}
      </Stack>
      <Evidence title="Calculation inputs and broker cash-flow series" data={{ dietz: data.dietz, base_value: data.broker_base_value, cashflow: data.broker_cashflow_series }} />
    </Stack>
  );
}

function alertAtom(draft) {
  if (draft.kind === 'drawing') return { kind: 'drawing', scope: 'drawing', parameters: { drawing_ref: draft.drawing_ref, field: draft.field, comparison: draft.comparison, geometry_policy: draft.geometry_policy, max_age_seconds: draft.max_age_seconds, context: draft.context, timeframe: draft.timeframe, history_key: draft.history_key || '', run_id: draft.run_id || '' } };
  return { kind: draft.kind, scope: draft.scope, parameters: { threshold: draft.threshold, max_age_seconds: draft.max_age_seconds, proposal_id: draft.proposal_id, condition: draft.condition, ...(draft.kind === 'indicator' ? { indicator: draft.indicator, comparison: draft.comparison, context: draft.context, timeframe: draft.timeframe, history_key: draft.history_key, run_id: draft.run_id } : {}) } };
}

export function ResearchDisposition({ symbol, researchLink = null }) {
  const { state, act } = useDesk();
  const [drafts, setDrafts] = useState({});
  const [error, setError] = useState('');
  const attention = state?.attention;
  const savedResearch = state?.research?.[symbol] || state?.saved_research?.[symbol] || null;
  const linked = researchLink && savedResearch && savedResearch.run_id === researchLink.run_id && (savedResearch.revision || 0) === (researchLink.revision || 0) ? savedResearch : savedResearch && !researchLink ? savedResearch : null;
  const research = linked || (researchLink?.run_id ? { ...researchLink, symbol, revision: researchLink.revision || 0 } : null);
  const key = research?.run_id ? `${symbol}:${research.run_id}:${research.revision || 0}` : '';
  const saved = key ? attention?.data?.reviews?.[key] : null;
  const shown = saved?.review_required ? { ...saved, recorded_disposition: saved.disposition, disposition: 'needs_review' } : saved;
  const draft = drafts[key] || { disposition: shown?.recorded_disposition || shown?.disposition || '', notes: shown?.notes || '', prioritize: !!shown?.prioritize };
  const today = state?.clock?.date || '';
  const age = research?.trade_date && today ? Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${research.trade_date}T00:00:00Z`)) / 86400000) : null;
  async function save() {
    if (!attention || !research?.run_id) return;
    setError('');
    try {
      await act('attention-review', '/api/attention', { action: 'review', symbol, run_id: research.run_id, research_revision: research.revision || 0, disposition: draft.disposition, notes: draft.notes, prioritize: draft.prioritize, expected_revision: attention.revision });
    } catch (failure) {
      setError(messageOf(failure));
    }
  }
  if (!symbol) return null;
  if (!research?.run_id) return <Typography>No saved result for this stock. New research is separate from reviewing a saved result.</Typography>;
  return (
    <Stack spacing={1} component="section" aria-label="Review this saved revision">
      <Typography variant="h3">Review this saved revision</Typography>
      <Typography>Run {research.run_id} · revision {research.revision || 0} · research date {text(research.trade_date)} · {Number.isFinite(age) ? (age < 0 ? 'research date is after the current market date' : `${age} calendar days old`) : 'age unavailable'}. Reviewing this revision does not start a job or authorize orders.</Typography>
      {shown?.review_required ? <Alert severity="warning">Review required: {(shown.review_reasons || []).join('; ')}</Alert> : null}
      <Choice label="Human disposition" value={draft.disposition} onChange={(disposition) => setDrafts((current) => ({ ...current, [key]: { ...draft, disposition } }))} options={[{ value: '', label: 'Choose a disposition' }, ['reviewed', 'Reviewed'], ['needs_review', 'Needs review'], ['deferred', 'Deferred']].map((item) => Array.isArray(item) ? { value: item[0], label: item[1] } : item)} />
      <TextField label="Review notes" multiline minRows={2} value={draft.notes} onChange={(event) => setDrafts((current) => ({ ...current, [key]: { ...draft, notes: event.target.value } }))} />
      <FormControlLabel control={<Checkbox checked={draft.prioritize} onChange={(event) => setDrafts((current) => ({ ...current, [key]: { ...draft, prioritize: event.target.checked } }))} />} label="Prioritize future research · does not start a job" />
      <Button disabled={!attention} onClick={save}>Save revision review</Button>
      <Typography role="status">{error || shown?.saved_at || 'No saved disposition'}</Typography>
      {research.reports ? <Evidence title="Saved opposing arguments and source text" data={Object.fromEntries(Object.entries(research.reports).filter(([name]) => /debate/.test(name)))} /> : <Typography>No debate text is in this snapshot. Open the saved research reports for source text.</Typography>}
    </Stack>
  );
}

export function AlertsView() {
  const desk = useDesk();
  const { state, api, act, page, pending, navigate, selectedSymbol, stateError, navigation, clearNavigation } = desk;
  const [tab, setTab] = useState('Inbox');
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(blankRule);
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState('');
  const [localError, setLocalError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [evidenceId, setEvidenceId] = useState('');
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState('');
  const [evidenceTab, setEvidenceTab] = useState('Event');
  const [browserError, setBrowserError] = useState('');
  const [browserBusy, setBrowserBusy] = useState(false);
  const [profileId, setProfileId] = useState('');
  const [pendingDraft, setPendingDraft] = useState(null);
  const consumedNavigation = useRef(new Set());
  const bound = [state?.server_instance_id, state?.store_generation, state?.nautilus?.connection_session].join('|');
    const generation = useRef(bound);
      const claimBusy = useRef(false);
      const claimSeen = useRef(new Set());
      const attentionRef = useRef(null);
      const attention = record || state?.attention;
      attentionRef.current = attention;
      const observed = attention?.observations?.data || {};

    useEffect(() => {
      if (generation.current && generation.current !== bound) {
        setConflict(true);
        setRecord(null);
        setEvidence(null);
        setEvidenceId('');
        setLocalError('Saved attention records were unbound because the server, store generation or connection session changed. The rule draft was kept. Reload before saving or acknowledging.');
      claimSeen.current.clear();
      }
      generation.current = bound;
    }, [bound]);
  useEffect(() => {
    if (page !== 'alerts' || attention || pending.has('attention-load')) return undefined;
    let cancelled = false;
    api('/api/attention').then((loaded) => { if (!cancelled) setRecord(loaded); }).catch((error) => { if (!cancelled) setLocalError(messageOf(error)); });
    return () => { cancelled = true; };
  }, [page, attention, pending, api]);
  useEffect(() => {
    if (!navigation || navigation.page !== 'alerts' || consumedNavigation.current.has(navigation.id)) return;
    const next = alertDraftFromMarkets(navigation.intent);
    const id = navigation.id;
    if (!next) return;
        consumedNavigation.current.add(id);
    if (dirty) {
      setPendingDraft(next);
      setNotice('A Markets alert draft arrived. The current edited rule was kept. Apply the incoming draft only if you want to replace it.');
    } else {
      setDraft(next);
      setDirty(true);
      setTab('Rules');
      setNotice('Markets draft loaded. Set the threshold and maximum age, then save explicitly. Nothing was saved.');
    }
    clearNavigation(id);
  }, [navigation, clearNavigation, dirty]);

  function edit(next) { setDraft(next); setDirty(true); }
  async function attentionAction(request) {
    if (conflict || !attention) return;
    setLocalError('');
    try {
      const result = await act(`attention-${request.action}`, '/api/attention', { ...request, expected_revision: attention.revision });
      setRecord(result);
      setDirty(false);
      if (request.action === 'save') setDraft(blankRule());
    } catch (error) {
      setLocalError(messageOf(error));
      if (error.status === 409) setConflict(true);
    }
  }
  async function reload() {
    setNotice('');
    try {
      const loaded = await api('/api/attention');
      setRecord(loaded);
      setDirty(false);
      setConflict(false);
      setLocalError('');
      setDraft(blankRule());
    } catch (error) {
      setLocalError(messageOf(error));
    }
  }
  async function openEvidence(id) {
    const requestGeneration = state?.store_generation;
    if (!requestGeneration) { setLocalError('Application records changed. Open the saved alert again.'); return; }
    setEvidenceId(id);
    setEvidence(null);
    setEvidenceError('');
    setTab('Inbox');
    try {
      const saved = await api(`/api/attention/occurrences/${encodeURIComponent(id)}?generation=${encodeURIComponent(requestGeneration)}`);
      if (saved.store_generation !== requestGeneration || saved.occurrence?.id !== id) throw new Error('Saved occurrence identity or generation differs.');
      setEvidence(saved);
    } catch (error) {
      setEvidenceError(messageOf(error));
    }
  }
  function profile() {
    if (profileId) return profileId;
    try {
      const stored = localStorage.getItem('tradingagents-notification-profile');
      if (stored) { setProfileId(stored); return stored; }
      const id = crypto.randomUUID();
      localStorage.setItem('tradingagents-notification-profile', id);
      setProfileId(id);
      return id;
    } catch {
      setBrowserError('Browser profile storage is unavailable; notifications remain disabled.');
      return null;
    }
  }
  async function browserAction(request) {
    const id = profile();
    const currentGeneration = state?.store_generation;
    if (!id) throw new Error(browserError || 'Browser profile storage is unavailable.');
    const result = await act(`attention-${request.action}`, '/api/attention', { ...request, profile_id: id, store_generation: currentGeneration });
    if (state?.store_generation !== currentGeneration) throw new Error('Application records changed; reload notification state.');
    setRecord(result);
    return result.browser_delivery;
  }
  async function enableBrowser() {
    setBrowserBusy(true);
    setBrowserError('');
    try {
      if (typeof Notification === 'undefined') throw new Error('Browser notifications are unavailable.');
      const permission = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Browser notification permission was not granted.');
      await browserAction({ action: 'browser_enable', permission });
    } catch (error) {
      setBrowserError(messageOf(error));
    } finally {
      setBrowserBusy(false);
    }
  }
  useEffect(() => {
    const profileId = storedNotificationProfile();
    const data = attention?.observations?.data;
    const profile = data?.browser_profiles?.[profileId];
    const generationNow = state?.store_generation;
    if (stateError || conflict || !profileId || typeof Notification === 'undefined' || Notification.permission !== 'granted' || !profile?.enabled || profile.generation !== generationNow) return undefined;
    const waiting = Object.values(data.occurrences || {}).filter((item) => item.unread && item.created_at > profile.enabled_after && !profile.deliveries?.[item.id] && !claimSeen.current.has(item.id)).sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
    if (!waiting.length || claimBusy.current) return undefined;
    let cancelled = false;
    claimBusy.current = true;
    waiting.forEach((item) => claimSeen.current.add(item.id));
    (async () => {
      try {
        for (const occurrence of waiting) {
          if (cancelled || state?.store_generation !== generationNow) break;
          const result = await api('/api/attention', { action: 'browser_claim', id: occurrence.id, profile_id: profileId, store_generation: generationNow });
          const delivery = result.browser_delivery;
          setRecord(result);
          if (!delivery?.claimed) { claimSeen.current.delete(occurrence.id); continue; }
          const shown = delivery.occurrence;
          const fail = async (problem) => {
            const detail = `Notification failed: ${problem?.message || problem || 'Browser reported a display error'}`;
            setBrowserError(detail);
            if (state?.store_generation === generationNow) {
              try {
                const failed = await api('/api/attention', { action: 'browser_failed', id: occurrence.id, profile_id: profileId, store_generation: generationNow, attempt_id: delivery.attempt_id, error: detail });
                setRecord(failed);
              } catch (saveError) { setBrowserError(`${detail}; failure status could not be saved: ${saveError.message}`); }
            }
          };
          try {
            const current = attentionRef.current?.observations?.data?.browser_profiles?.[profileId];
            if (Notification.permission !== 'granted' || !current?.enabled || current.generation !== generationNow) throw new Error('Browser permission or opt-in changed before display');
            const notification = new Notification(shown.name, { body: `${shown.symbol || 'Account'} · ${shown.scope} · ${shown.evaluation?.reason || ''}`, tag: `${profileId}:${occurrence.id}` });
            notification.onerror = () => { void fail('Browser reported a display error'); };
            notification.onclick = () => { window.focus(); notification.close(); openEvidence(shown.id); };
          } catch (problem) { await fail(problem); }
        }
      } catch (problem) {
        setBrowserError(messageOf(problem));
      } finally {
        claimBusy.current = false;
      }
    })();
    return () => { cancelled = true; };
  }, [attention, state?.store_generation, stateError, conflict, api]);
  async function retryBrowser(id) {
    setBrowserBusy(true);
    setBrowserError('');
    try {
      const delivery = await browserAction({ action: 'browser_retry', id });
      if (!delivery?.claimed) return;
      const occurrence = delivery.occurrence;
      const notification = new Notification(occurrence.name, { body: `${occurrence.symbol || 'Account'} · ${occurrence.scope} · ${occurrence.evaluation?.reason || ''}`, tag: `${profile()}:${id}` });
      notification.onclick = () => { window.focus(); notification.close(); openEvidence(occurrence.id); };
    } catch (error) {
      setBrowserError(messageOf(error));
    } finally {
      setBrowserBusy(false);
    }
  }

  const occurrences = Object.values(observed.occurrences || {});
  const rules = Object.values(attention?.data?.rules || {}).filter((rule) => !rule.removed);
  const unread = Object.values(observed.occurrences || {}).filter((item) => item.unread).length;
  const quotes = state?.quotes || {};
  const universe = state?.config?.symbols || state?.universe || Object.keys(quotes);
  const unconfigured = universe.filter((symbol) => quotes[symbol] && (quotes[symbol].freshness_configured !== true || quotes[symbol].max_age_seconds == null)).length;
  const watchlists = state?.workspace?.data?.watchlists || [];
  const mode = draft.kind === 'drawing' || (draft.atoms || []).some((atom) => atom.kind === 'drawing') ? 'symbol' : draft.target?.mode || draft.target_mode || 'symbol';
  const browserProfileSaved = observed.browser_profiles?.[profileId];
  const supported = typeof Notification !== 'undefined';
  const permission = supported ? Notification.permission : 'unavailable';

  return (
    <Page tabbed title="Alerts" subtitle="Rules use saved snapshots; continuous interval coverage is not implied." actions={<Button onClick={() => navigate('settings', settingsHandoff('session_freshness'))}>Set quote-age limits in Trading Rules</Button>}>
      <Stack spacing={2}>
        <Typography>Quote-age limits: {quotes && universe.length ? (unconfigured ? `${unconfigured} stocks not configured` : 'Configured for current stocks with quote freshness fields') : 'Quote freshness is not in this snapshot.'} Market is {state?.clock?.is_open === false ? 'closed' : state?.clock?.is_open === true ? 'open' : 'unavailable'}.</Typography>
        {stateError ? <Alert severity="warning">{stateError}</Alert> : null}
                {localError ? <Alert severity="error">{localError}</Alert> : null}
                {notice ? <Alert severity="info">{notice}</Alert> : null}
        {pendingDraft ? <Alert severity="info" action={<Button color="inherit" onClick={() => { setDraft(pendingDraft); setDirty(true); setTab('Rules'); setPendingDraft(null); }}>Replace edited draft</Button>}>Incoming {pendingDraft.kind} draft for {pendingDraft.symbol || 'the saved symbol'} was not applied.</Alert> : null}
        {conflict ? <Button onClick={reload}>Reload saved attention state (discard rule edits)</Button> : null}
      </Stack>
        <Tabs value={tab} onChange={(_event, value) => setTab(value)} aria-label="Alerts views">
          <Tab value="Inbox" label={`Inbox (${unread} unread)`} />
          <Tab value="Rules" label={`Alert Rules (${rules.length})`} />
          <Tab value="Delivery" label="Browser Delivery" />
        </Tabs>
        <Box role="tabpanel" hidden={tab !== 'Inbox'}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Stack spacing={1}>
                <Typography>Monitor: {observed.monitor?.last_evaluated_at ? (Date.now() - Date.parse(observed.monitor.last_evaluated_at) > 15000 ? 'Stale / interrupted' : observed.monitor.state || 'Unknown') : 'Not evaluated'} · last evaluated {dateTime(observed.monitor?.last_evaluated_at)}</Typography>
                <DataTable label="Alert inbox" rows={occurrences} onRowClick={(row) => openEvidence(row.id)}
                  columns={[{id: 'name', label: 'Alert'}, {id: 'symbol', label: 'Symbol'}, {id: 'scope', label: 'Scope'},
                    {id: 'unread', label: 'State', value: row => row.unread ? 'Unread' : 'Acknowledged'},
                    {id: 'reason', label: 'Reason', value: row => row.evaluation?.reason},
                    {id: 'created_at', label: 'Created', type: 'dateTime', render: row => dateTime(row.created_at)},
                    {id: 'action', label: '', render: row => row.unread && <Button onClick={() => attentionAction({action: 'acknowledge', id: row.id, occurrence_revision: row.revision})}>Acknowledge</Button>}]}
                  getRowId={row => row.id} empty="No saved alert occurrences." />
                <Evidence title="Service restart gaps are unobserved intervals, not acknowledgements" data={(observed.monitor?.gaps || [])} />
              </Stack>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              {!evidenceId ? <Typography>Select an alert to review its evidence. Opening retains the captured event. It does not acknowledge, refresh sources, run research, or trade.</Typography> : (
                <Stack spacing={1}>
                  <Typography variant="h2">{evidence?.occurrence?.name || 'Saved alert evidence'}</Typography>
                  <Tabs value={evidenceTab} onChange={(_event, value) => setEvidenceTab(value)}>
                    <Tab value="Event" label="Event" />
                    <Tab value="Evidence" label="Evidence" />
                    <Tab value="Rule" label="Rule" />
                  </Tabs>
                  {evidenceError ? <Alert severity="error">{evidenceError}</Alert> : null}
                  {evidenceTab === 'Event' ? <Typography>{evidence?.occurrence?.evaluation?.reason || evidenceError || 'Loading saved occurrence…'} · {evidence?.occurrence?.unread ? 'Unread' : evidence?.occurrence ? 'Acknowledged' : 'Loading'} · created {dateTime(evidence?.occurrence?.created_at)}</Typography> : null}
                  <Evidence title={evidenceTab === 'Rule' ? 'Exact captured rule' : 'Exact captured evidence'} data={evidenceTab === 'Rule' ? evidence?.occurrence?.evidence?.rule || { status: 'No captured rule for this legacy occurrence' } : evidence || { status: 'Captured bindings unavailable' }} />
                  <Button onClick={() => { setEvidenceId(''); setEvidence(null); }}>Close saved evidence</Button>
                </Stack>
              )}
            </Grid>
          </Grid>
        </Box>
        <Box role="tabpanel" hidden={tab !== 'Rules'}><RuleEditor attention={attention} observed={observed} draft={draft} dirty={dirty} edit={edit} mode={mode} watchlists={watchlists} selectedSymbol={selectedSymbol} rules={rules} onSave={() => { setNotice(''); attentionAction({ action: 'save', id: draft.id, name: draft.name, symbol: (draft.symbol || '').toUpperCase(), active: Boolean(draft.active), atoms: Number.isInteger(draft.atomIndex) ? (draft.atoms || []).map((atom, index) => index === draft.atomIndex ? alertAtom(draft) : atom) : (draft.atoms?.length ? draft.atoms : [alertAtom(draft)]), operator: draft.operator || 'ALL', target: { mode: (draft.atoms || []).some((atom) => atom.kind === 'drawing') || draft.kind === 'drawing' ? 'symbol' : mode, symbol: (draft.symbol || '').toUpperCase(), watchlist_id: draft.watchlist_id || draft.target?.watchlist_id } }); }} onTemplate={(kind) => { if (dirty && !window.confirm('Discard unsaved alert rule edits and use this template?')) return; edit({ ...blankRule(), name: kind === 'price_above' ? 'Price above' : kind === 'price_below' ? 'Price below' : 'Quote stale', kind, scope: 'quote', symbol: selectedSymbol || '', target_mode: 'symbol' }); setNotice('Template loaded. Enter explicit limits, review the target, then Save rule.'); }} onAction={(action, id) => attentionAction({ action, id })} onEditRule={(rule) => { setTab('Rules'); edit({ ...structuredClone(rule), ...rule.parameters, target_mode: rule.target?.mode || 'symbol', watchlist_id: rule.target?.watchlist_id || '', atomIndex: rule.atoms ? 0 : undefined }); }} /></Box>
        <Box role="tabpanel" hidden={tab !== 'Delivery'}>
          <Stack spacing={1}>
            <Typography>Opt in for new alert occurrences on this browser profile. Enabling starts from now and does not replay the unread backlog. The desk and browser page must remain running. Email and closed-browser push are not configured.</Typography>
            <Typography>Browser permission: {permission} · saved preference: {browserProfileSaved?.enabled ? 'enabled' : 'disabled'}</Typography>
            <Stack direction="row" spacing={1}>
              <Button disabled={!supported || permission === 'denied' || browserBusy} onClick={enableBrowser}>Enable browser notifications</Button>
              <Button disabled={!browserProfileSaved?.enabled || browserBusy} onClick={() => browserAction({ action: 'browser_disable' }).catch((error) => setBrowserError(messageOf(error)))}>Disable</Button>
            </Stack>
            {browserError ? <Alert severity="error">{browserError}</Alert> : null}
            <Typography>Requested means a browser display attempt was recorded. It does not confirm delivery or reading. Failures are retried only when you choose Retry; unread acknowledgment is separate.</Typography>
            <DataTable label="Browser notification attempts" rows={Object.entries(browserProfileSaved?.deliveries || {}).map(([id, attempt]) => ({...attempt, id}))}
              getRowId={row => row.id} columns={[{id: 'name', label: 'Alert', value: row => observed.occurrences?.[row.id]?.name || row.id},
                {id: 'state', label: 'Delivery state'}, {id: 'requested_at', label: 'Requested', type: 'dateTime', render: row => dateTime(row.requested_at)},
                {id: 'error', label: 'Error'}, {id: 'actions', label: '', render: row => <Stack direction="row" spacing={1}>
                  <Button onClick={() => openEvidence(row.id)}>Open evidence</Button>
                  {row.state === 'failed' && <Button disabled={browserBusy} onClick={() => retryBrowser(row.id)}>Retry failed notification</Button>}
                </Stack>}]} empty="No browser notification attempts recorded." />
            <Typography>Enable starts from now and does not replay the unread backlog. After permission is granted, new unread occurrences are claimed once per profile delivery record. Retry is only for a failed display. Acknowledgement stays separate.</Typography>
        {selectedSymbol ? <ResearchDisposition symbol={selectedSymbol} /> : null}
          </Stack>
        </Box>
        {attention ? <Typography>Future research priorities: {Object.values(attention.data?.reviews || {}).filter((review) => review.prioritize).map((review) => `${review.symbol} · ${review.run_id} revision ${review.research_revision}`).join('; ') || 'No priorities saved'}. Provider {text(state?.config?.llm_provider)} · fast model {text(state?.config?.quick_think_llm)} · deep model {text(state?.config?.deep_think_llm)}. Start new research through Research. Save a disposition from the review editor; it does not start research or authorize an order.</Typography> : <Typography>Saved rule configuration unavailable.</Typography>}
    </Page>
  );
}

function RuleEditor({ attention, observed, draft, dirty, edit, mode, watchlists, rules, onSave, onTemplate, onAction, onEditRule }) {
  const drawingKey = (ref) => (ref ? `${ref.drawing_id}/${ref.revision}/${ref.geometry_sha256}` : '');
  const options = attention?.drawing_options || [];
  const bound = drawingKey(draft.drawing_ref);
  const candidate = draft.drawing_candidate ?? bound;
  function keepAtom() {
    const values = [...(draft.atoms || [])];
    if (Number.isInteger(draft.atomIndex)) values[draft.atomIndex] = alertAtom(draft);
    else if (values.length < 16) values.push(alertAtom(draft));
    else return edit({ ...draft, error: 'Use at most 16 conditions' });
    edit({ ...draft, atoms: values, atomIndex: undefined, kind: '', scope: '', threshold: '', max_age_seconds: '', proposal_id: '', condition: '' });
  }
  function bindDrawing() {
    const option = options.find((item) => drawingKey(item.drawing_ref) === candidate);
    if (!option) return edit({ ...draft, error: 'Choose a current eligible saved numeric drawing revision; no historical/latest substitution is performed.' });
    const context = option.scope.context === 'current' ? 'current' : 'research';
    edit({ ...draft, kind: 'drawing', scope: 'drawing', symbol: option.scope.symbol, drawing_ref: structuredClone(option.drawing_ref), drawing: structuredClone(option.drawing), field: draft.field || 'c', comparison: draft.comparison || 'cross_above', geometry_policy: draft.geometry_policy || 'segment', context, timeframe: option.scope.timeframe, history_key: draft.context !== context || draft.timeframe !== option.scope.timeframe ? '' : draft.history_key, run_id: draft.context !== context || draft.timeframe !== option.scope.timeframe ? '' : draft.run_id, target_mode: 'symbol', watchlist_id: '', error: 'Chosen saved geometry is bound in this draft. Save the rule revision explicitly to establish its new baseline; acknowledgment/pause do not rearm it.' });
  }
  return (
    <Stack spacing={1.5}>
      <Typography>Templates fill an unsaved draft. Choose explicit thresholds and Save; no rule is activated by selecting a template.</Typography>
      <Stack direction="row" spacing={1}>
        <Button onClick={() => onTemplate('price_above')}>Price Above $</Button>
        <Button onClick={() => onTemplate('price_below')}>Price Below $</Button>
        <Button onClick={() => onTemplate('source_stale')}>Quote Stale &gt; s</Button>
      </Stack>
      <Accordion expanded={dirty || Boolean(draft.id)}>
        <AccordionSummary>{draft.id ? 'Edit rule' : 'Create an explicit rule'}</AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1.5}>
            {draft.error ? <Alert severity="warning">{draft.error}</Alert> : null}
            <Field label="Rule name" value={draft.name} onChange={(name) => edit({ ...draft, name })} />
            <Choice label="Combine conditions" value={draft.operator || 'ALL'} onChange={(operator) => edit({ ...draft, operator })} options={['ALL', 'ANY'].map((value) => ({ value, label: value }))} />
            <Typography>ALL requires every condition; ANY requires one. Missing inputs remain unavailable. Level conditions may trigger on the first eligible matching observation. Typed crossing conditions require comparable previous and current observations.</Typography>
            <Choice label="Target" value={mode} onChange={(target_mode) => edit({ ...draft, target_mode, target: null })} options={[['symbol', 'One stock'], ['account', 'Global account'], ['proposal', 'One fixed proposal'], ['snapshot', 'Watchlist snapshot'], ['follow', 'Follow watchlist']].filter(([value]) => mode !== 'symbol' || value === 'symbol' || draft.kind !== 'drawing').map(([value, label]) => ({ value, label }))} />
            {['snapshot', 'follow'].includes(mode) ? <Choice label="Watchlist" value={draft.watchlist_id || ''} onChange={(watchlist_id) => edit({ ...draft, watchlist_id })} options={[{ value: '', label: 'Choose' }, ...watchlists.map((list) => ({ value: list.id, label: list.name }))]} /> : null}
            <Typography>Snapshot retains the current members. Follow records removals and re-additions at each workspace save. Account conditions run once globally; policy conditions bind once to one saved proposal.</Typography>
            <Typography>Conditions · {(draft.atoms || []).length} / 16 {Number.isInteger(draft.atomIndex) ? `· editing condition ${draft.atomIndex + 1}` : ''}</Typography>
            {(draft.atoms || []).map((atom, index) => (
              <Stack key={index} direction="row" spacing={1}>
                <Typography>{atom.kind} · {atom.scope}</Typography>
                <Button onClick={() => edit({ ...draft, ...atom, ...atom.parameters, atomIndex: index })}>Edit condition {index + 1}</Button>
                <Button onClick={() => edit({ ...draft, atoms: draft.atoms.filter((_item, itemIndex) => itemIndex !== index), atomIndex: undefined })}>Remove condition {index + 1}</Button>
              </Stack>
            ))}
            <Choice label="Rule type" value={draft.kind} onChange={(kind) => edit({ ...draft, kind, scope: ['indicator', 'drawing'].includes(kind) ? kind : draft.scope })} options={[{ value: '', label: 'Choose' }, ...RULE_KINDS.map((kind) => ({ value: kind, label: kind }))]} />
            <Choice label="Source scope" value={draft.scope} onChange={(scope) => edit({ ...draft, scope })} options={[{ value: '', label: 'Choose' }, ...RULE_SCOPES.map((scope) => ({ value: scope, label: scope }))]} />
            {mode === 'symbol' ? <Field label="Symbol · blank for account condition" value={draft.symbol} onChange={(symbol) => edit({ ...draft, symbol })} /> : null}
            {['price_above', 'price_below', 'movement', 'indicator'].includes(draft.kind) ? <Field label={draft.kind === 'indicator' ? 'Indicator threshold / recorded series units' : 'Price threshold / USD or absolute movement / %'} value={draft.threshold} onChange={(threshold) => edit({ ...draft, threshold })} /> : null}
            <Field label="Maximum source age / seconds" value={draft.max_age_seconds} onChange={(max_age_seconds) => edit({ ...draft, max_age_seconds })} />
            {draft.kind === 'policy_condition' || mode === 'proposal' ? <Field label="Proposal ID · policy condition only" value={draft.proposal_id} onChange={(proposal_id) => edit({ ...draft, proposal_id })} /> : null}
            {draft.kind === 'policy_condition' ? <TextField label="Exact saved policy condition · policy rule only" multiline value={draft.condition || ''} onChange={(event) => edit({ ...draft, condition: event.target.value })} /> : null}
            {draft.kind === 'indicator' ? (
              <Stack spacing={1}>
                <Choice label="Indicator" value={draft.indicator || ''} onChange={(indicator) => edit({ ...draft, indicator })} options={[{ value: '', label: 'Choose' }, ...INDICATORS.map((value) => ({ value, label: value }))]} />
                <Choice label="Comparison" value={draft.comparison || ''} onChange={(comparison) => edit({ ...draft, comparison })} options={['above', 'below', 'cross_above', 'cross_below'].map((value) => ({ value, label: value }))} />
                <Choice label="Input context" value={draft.context || ''} onChange={(context) => edit({ ...draft, context })} options={['current', 'research'].map((value) => ({ value, label: value }))} />
                {draft.context !== 'research' ? <Choice label="Current-history interval" value={draft.timeframe || ''} onChange={(timeframe) => edit({ ...draft, timeframe })} options={INTERVALS.map((value) => ({ value, label: value }))} /> : null}
                {draft.context !== 'research' ? <Field label="Current history cache key · blank follows latest retained cache" value={draft.history_key || ''} onChange={(history_key) => edit({ ...draft, history_key })} /> : <Field label="Exact saved research run" value={draft.run_id || ''} onChange={(run_id) => edit({ ...draft, run_id })} />}
                <Typography>The threshold uses the displayed indicator units, including RSI 0–100 and MFI 0–1. Crossing needs two eligible observations. Correction or replacement resets its baseline without creating a crossing. This rule collects no data.</Typography>
              </Stack>
            ) : null}
            {draft.kind === 'drawing' ? (
              <Stack spacing={1}>
                <Choice label="Saved numeric drawing revision" value={candidate} onChange={(drawing_candidate) => edit({ ...draft, drawing_candidate })} options={[{ value: '', label: 'Choose saved geometry' }, ...options.map((option) => ({ value: drawingKey(option.drawing_ref), label: `${option.scope.symbol} · ${option.drawing.kind} · ${option.scope.timeframe} · revision ${option.drawing_ref.revision}` }))]} />
                <Button onClick={bindDrawing}>Explicitly bind chosen saved revision</Button>
                <Choice label="Actual retained OHLC field" value={draft.field || ''} onChange={(field) => edit({ ...draft, field })} options={[['c', 'Close'], ['o', 'Open'], ['h', 'High'], ['l', 'Low']].map(([value, label]) => ({ value, label }))} />
                <Choice label="Residual crossing" value={draft.comparison || ''} onChange={(comparison) => edit({ ...draft, comparison })} options={[['cross_above', 'Cross above drawing'], ['cross_below', 'Cross below drawing']].map(([value, label]) => ({ value, label }))} />
                <Choice label="Trendline extent only" value={draft.geometry_policy || ''} onChange={(geometry_policy) => edit({ ...draft, geometry_policy })} options={[['segment', 'Within both anchors'], ['extrapolate', 'Explicit extrapolation on actual bar axis']].map(([value, label]) => ({ value, label }))} />
                <Typography>Horizontal levels are constant across the actual retained bar axis. Unavailable, acknowledgment and pause do not rearm; only an eligible clear does. Rebinding establishes a fresh baseline.</Typography>
                <Evidence title="Exact pinned reference, scope and typed anchors" data={{ drawing_ref: draft.drawing_ref ?? null, drawing: draft.drawing ?? null }} />
              </Stack>
            ) : null}
            <FormControlLabel control={<Checkbox checked={Boolean(draft.active)} onChange={(event) => edit({ ...draft, active: event.target.checked })} />} label="Evaluate this rule while the service runs" />
            <Button onClick={keepAtom}>Keep condition in group</Button>
            <Button variant="contained" onClick={onSave}>Save rule</Button>
          </Stack>
        </AccordionDetails>
      </Accordion>
      <DataTable rows={rules} columns={[{ id: 'name', label: 'Rule' }, { id: 'kind', label: 'Type', value: (row) => row.atoms ? `${row.operator} · ${row.atoms.length} conditions` : row.kind },
        {id: 'revision', label: 'Revision', numeric: true}, {id: 'active', label: 'Configuration', type: 'boolean', render: row => row.active ? 'Active configuration' : 'Paused'},
        {id: 'evaluation', label: 'Evaluation', value: row => {const observation = observed.rule_states?.[row.id]; return observation?.rule_revision === row.revision ? observation.evaluation?.state || 'Not evaluated' : 'Not evaluated';}}]}
        getRowId={(row) => row.id} onRowClick={onEditRule} empty="No saved alert rules." />
      {rules.map((rule) => (
        <Stack key={rule.id} direction="row" spacing={1}>
          <Typography>{rule.name} · revision {rule.revision}</Typography>
          <Button onClick={() => onEditRule(rule)}>Edit</Button>
          <Button onClick={() => onAction(rule.active ? 'pause' : 'resume', rule.id)}>{rule.active ? 'Pause' : 'Resume'}</Button>
          <Button onClick={() => onAction('remove', rule.id)}>Remove</Button>
        </Stack>
      ))}
      <Evidence title="Per-member results, membership history and rule gaps" data={observed.rule_states || {}} />
    </Stack>
  );
}
