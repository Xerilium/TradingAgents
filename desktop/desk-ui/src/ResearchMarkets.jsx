import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel,
  Grid, Link, MenuItem, Paper, Stack, Tab, Tabs, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TablePagination, TextField, Typography, Autocomplete,
} from '@mui/material';
import { useDesk } from './DeskContext.jsx';
import { Page, Evidence, DataTable, money, number, dateTime, Status } from './ui.jsx';
import { ResearchDisposition } from './LabJournalAlerts.jsx';

const ACTIVE = ['queued', 'running', 'cancelling', 'cancel_requested'];
const SYMBOL = /^[A-Z][A-Z0-9.-]{0,14}$/;
const UNAVAILABLE = 'Unavailable';

const dateNY = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date());
const universeOf = (state) => state?.config?.universe || [];
const activeRun = (state) => (state?.runs || []).find((r) => ACTIVE.includes(r.status) && !r.history_source);
const rowStatus = (r) => (!r ? 'none' : r.status === 'completed' && r.completion_gaps?.length ? 'incomplete' : r.status);
const count = (v) => { const n = number(v); return n === null ? UNAVAILABLE : n.toLocaleString(); };
const pct = (v) => (typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(2)}%` : UNAVAILABLE);
const text = (v) => (v == null || v === '' ? UNAVAILABLE : typeof v === 'string' ? v : JSON.stringify(v, null, 2));
const errMessage = (e) => e?.message || String(e);
// Source-bound previews and approvals are only valid for the instance, store, broker session and configuration they were read from.
const deskIdentity = (s) => [s?.server_instance_id, s?.store_generation, s?.nautilus?.connection_session, s?.config_revision].join('|');

function download(content, name, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Report text is untrusted: rendered as plain pre-wrapped text only.
function ReportText({ value }) {
  return (
    <Typography component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', m: 0, overflowWrap: 'anywhere' }}>
      {text(value)}
    </Typography>
  );
}

function Section({ title, children, actions }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Stack direction="row"   sx={{justifyContent: "space-between", alignItems: "center",  mb: 1 }}>
        <Typography variant="h6" component="h2">{title}</Typography>
        <Box>{actions}</Box>
      </Stack>
      {children}
    </Paper>
  );
}

function useAsyncAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = useCallback(async (fn) => {
    setBusy(true); setError('');
    try { return await fn(); } catch (e) { setError(errMessage(e)); return undefined; } finally { setBusy(false); }
  }, []);
  return { busy, error, run, setError };
}

/* ------------------------------------------------------------------ Research */

function researchEstimate(state, config, count, concurrency) {
  const keys = ['llm_provider', 'deep_think_llm', 'quick_think_llm', 'max_debate_rounds', 'max_risk_discuss_rounds'];
  const times = [];
  for (const run of state?.runs || []) {
    if (!keys.every((k) => run.config?.[k] === config?.[k])) continue;
    for (const r of run.results || []) {
      if (r.status === 'completed' && Number.isFinite(r.elapsed_seconds)) times.push(r.elapsed_seconds);
    }
  }
  if (!times.length) return null;
  times.sort((a, b) => a - b);
  const mid = times[Math.floor(times.length / 2)];
  return mid * Math.ceil(count / Math.max(1, concurrency || 1));
}

const duration = (s) => (s == null ? UNAVAILABLE : s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`);

function ReviewDialog({ review, onClose, onStart, busy, error }) {
  const [date, setDate] = useState('');
  const [fred, setFred] = useState(false);
  const [keep, setKeep] = useState(true);
  if (!review) return null;
  const today = dateNY();
  const invalid = date && (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date > today);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Review research batch</DialogTitle>
      <DialogContent>
        <Typography>{review.symbols.length} stock(s): {review.symbols.join(', ')}</Typography>
        <Typography>Quick model: {text(review.config?.quick_think_llm)} · Deep model: {text(review.config?.deep_think_llm)}</Typography>
        <Typography>Estimated time: {duration(review.estimate)}{review.estimate == null ? ' (no comparable completed run)' : ''}</Typography>
        <TextField
          type="date" label="Analysis date (blank = today, New York)" value={date} margin="normal" fullWidth
          onChange={(e) => setDate(e.target.value)} slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: today } }}
          error={Boolean(invalid)} helperText={invalid ? 'Choose a date no later than today.' : ''}
        />
        <Alert severity="info" sx={{ my: 1 }}>Only one result per stock is kept. A new run replaces the saved result, including for a historical date.</Alert>
        <FormControlLabel control={<Checkbox checked={fred} onChange={(e) => setFred(e.target.checked)} />} label="Exclude FRED data" />
        <FormControlLabel control={<Checkbox checked={keep} onChange={(e) => setKeep(e.target.checked)} />} label="Keep selection after starting" />
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Dismiss</Button>
        <Button variant="contained" disabled={busy || Boolean(invalid)} onClick={() => onStart({ analysis_date: date && date !== today ? date : undefined, exclude_fred: fred, keep })}>
          Start research
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function activityRows(run) {
  const groups = new Map();
  const add = (kind, item) => {
    const id = item.attempt_id || 'whole-run';
    if (!groups.has(id)) groups.set(id, { id, events: [], receipts: [] });
    groups.get(id)[kind].push(item);
  };
  (run?.events || []).forEach((e) => add('events', e));
  [...(run?.source_evidence || []), ...(run?.gateway_evidence || []), ...(run?.jev_evidence || [])].forEach((r) => add('receipts', r));
  return [...groups.values()];
}

const failedReceipt = (r, terminal) =>
  ['error', 'failed', 'cancelled', 'interrupted'].includes(r.outcome) || (r.outcome === 'unknown' && terminal) || r.capture_error ||
  ['unavailable', 'partial', 'no_usable_coverage'].includes(r.data_status) || r.http_status === 429 || r.status === 'rate_limited';

function ResearchDetail({ detail, run, symbol, tab, setTab, failuresOnly, setFailuresOnly, desk }) {
  const reports = detail?.reports || {};
  const urls = useMemo(() => {
    const found = new Set();
    Object.values(reports).forEach((v) => {
      if (typeof v === 'string') for (const m of v.matchAll(/https?:\/\/[^\s)>\]"']+/g)) found.add(m[0]);
    });
    return [...found];
  }, [reports]);
  const terminal = run && !ACTIVE.includes(run.status);
  const groups = useMemo(() => activityRows(run), [run]);
  const visible = failuresOnly ? groups.filter((g) => g.receipts.some((r) => failedReceipt(r, terminal))) : groups;
  const debate = reports.investment_debate_state || {};
  const risk = reports.risk_debate_state || {};
  const analyst = ['market_report', 'fundamentals_report', 'news_report', 'sentiment_report'];
  return (
    <Box>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable">
        {['summary', 'reports', 'debate', 'sources', 'activity'].map((t) => <Tab key={t} value={t} label={{ summary: 'Summary', reports: 'Reports', debate: 'Debate & Risk', sources: 'Sources & Filings', activity: 'Activity' }[t]} />)}
      </Tabs>
      <Box sx={{ pt: 2 }}>
        {!detail && <Typography>Select a researched stock to read its saved result.</Typography>}
        {detail && tab === 'summary' && (
          <Stack spacing={2}>
            <Typography variant="subtitle1">{symbol} · {text(detail.rating)} · {text(detail.trade_date)}</Typography>
            {detail.status === 'completed' && reports.final_trade_decision
              ? <><Typography variant="subtitle2">Portfolio Manager decision</Typography><ReportText value={reports.final_trade_decision} /></>
              : <Alert severity="warning">No completed verdict is available for {symbol}.</Alert>}
            <Typography variant="subtitle2">Trader plan</Typography>
            <ReportText value={reports.trader_investment_plan} />
          </Stack>
        )}
        {detail && tab === 'reports' && analyst.map((k) => (
          <Box key={k} sx={{ mb: 2 }}><Typography variant="subtitle2">{k.replace(/_/g, ' ')}</Typography><ReportText value={reports[k]} /></Box>
        ))}
        {detail && tab === 'debate' && (
          <Stack spacing={2}>
            {[['Bull', debate.bull_history], ['Bear', debate.bear_history], ['Research manager', debate.judge_decision],
              ['Aggressive', risk.aggressive_history], ['Neutral', risk.neutral_history], ['Conservative', risk.conservative_history], ['Risk judge', risk.judge_decision]]
              .map(([label, v]) => <Box key={label}><Typography variant="subtitle2">{label}</Typography><ReportText value={v} /></Box>)}
          </Stack>
        )}
        {detail && tab === 'sources' && (
          <Stack spacing={1}>
            <Typography variant="subtitle2">Links found in report text</Typography>
            {urls.length ? urls.map((u) => <Link key={u} href={u} target="_blank" rel="noreferrer noopener">{u}</Link>) : <Typography>None found.</Typography>}
            <Evidence title="Provenance receipts" data={{ source: run?.source_evidence, gateway: run?.gateway_evidence, jev: run?.jev_evidence }} />
            <SupplementaryEvidence symbol={symbol} desk={desk} />
          </Stack>
        )}
        {detail && tab === 'activity' && (
          <Stack spacing={1}>
            <FormControlLabel control={<Checkbox checked={failuresOnly} onChange={(e) => setFailuresOnly(e.target.checked)} />} label="Failures only" />
            {visible.length ? visible.map((g) => <Evidence key={g.id} title={`Attempt ${g.id} · ${g.events.length} events · ${g.receipts.length} receipts`} data={g} />) : <Typography>No activity recorded.</Typography>}
          </Stack>
        )}
      </Box>
    </Box>
  );
}

export function ResearchView() {
  const desk = useDesk();
  const { state, api, act, refresh, page, selectedSymbol, setSelectedSymbol, navigate, pending, stateError, navigation, clearNavigation } = desk;
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('symbol');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [batch, setBatch] = useState(() => new Set());
  const [tab, setTab] = useState('summary');
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [review, setReview] = useState(null);
  const [launched, setLaunched] = useState(null);
  const [detail, setDetail] = useState(null);
  const [run, setRun] = useState(null);
  const [del, setDel] = useState(null);
  const [link, setLink] = useState(null);
  useEffect(() => {
    if (!navigation || navigation.page !== 'research') return;
    const i = navigation.intent || {};
    if (i.symbol) setSelectedSymbol(i.symbol);
    // Exact retained-report link: the run is read by id below; it never falls back to the latest report.
    setLink(i.symbol && i.run_id ? { symbol: i.symbol, run_id: i.run_id, revision: i.revision ?? null, report_key: i.report_key || '' } : null);
    const key = i.report_key;
    if (key === 'final_trade_decision' || key === 'trader_investment_plan') setTab('summary');
    else if (['market_report', 'fundamentals_report', 'news_report', 'sentiment_report'].includes(key)) setTab('reports');
    else if (key === 'investment_debate_state' || key === 'risk_debate_state') setTab('debate');
    clearNavigation(navigation.id);
  }, [navigation, clearNavigation, setSelectedSymbol]);
  const reviewAction = useAsyncAction();
  const deleteAction = useAsyncAction();
  const detailAction = useAsyncAction();
  const today = dateNY();
  const universe = universeOf(state);
  const symbols = useMemo(() => [...new Set([...universe, ...Object.keys(state?.research || {})])], [universe, state?.research]);
  const active = activeRun(state);
  const blocked = Boolean(active || state?.browse_only);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = symbols.filter((s) => {
      const r = state?.research?.[s];
      if (q && !s.toLowerCase().includes(q) && !(state?.company_names?.[s] || '').toLowerCase().includes(q)) return false;
      if (filter === 'selected') return batch.has(s);
      if (filter !== 'all') return rowStatus(r) === filter;
      return true;
    });
    const age = (s) => state?.research?.[s]?.trade_date || '';
    const cmp = { symbol: (a, b) => a.localeCompare(b), status: (a, b) => rowStatus(state?.research?.[a]).localeCompare(rowStatus(state?.research?.[b])),
      oldest: (a, b) => age(a).localeCompare(age(b)), newest: (a, b) => age(b).localeCompare(age(a)) }[sort];
    return list.sort(cmp);
  }, [symbols, state?.research, state?.company_names, query, filter, sort, batch]);
  const pageRows = rows.slice(pageIndex * pageSize, pageIndex * pageSize + pageSize);
  const counts = useMemo(() => {
    const c = { all: symbols.length, selected: batch.size };
    symbols.forEach((s) => { const k = rowStatus(state?.research?.[s]); c[k] = (c[k] || 0) + 1; });
    return c;
  }, [symbols, state?.research, batch]);

  const toggle = (s) => setBatch((prev) => { const n = new Set(prev); if (n.has(s)) n.delete(s); else n.add(s); return n; });
  const inspected = selectedSymbol;
  const saved = state?.research?.[inspected];
  const linked = link && link.symbol === inspected ? link : null;
  const runId = linked ? linked.run_id : saved?.run_id;
  const savedRunId = saved?.run_id;

  // Read-only: loads the saved result for the inspected ticker while this page is visible.
  useEffect(() => {
    if (page !== 'research' || !inspected || !runId) { setDetail(null); setRun(null); return undefined; }
    setDetail(null); setRun(null);
    const ctl = new AbortController();
    (async () => {
      try {
        const d = await api(`/api/runs/${encodeURIComponent(runId)}/results/${encodeURIComponent(inspected)}`, undefined, { signal: ctl.signal });
        if (d?.symbol !== inspected) throw new Error('Result does not match the selected stock.');
        setDetail(d); detailAction.setError('');
        const full = await api(`/api/runs/${encodeURIComponent(runId)}`, undefined, { signal: ctl.signal });
        setRun(full);
      } catch (e) { if (!ctl.signal.aborted) detailAction.setError(errMessage(e)); }
    })();
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, inspected, runId, saved?.revision]);

  const batchSymbols = () => {
    const chosen = [...batch].filter((s) => universe.includes(s));
    return chosen.length ? chosen : inspected && universe.includes(inspected) ? [inspected] : [];
  };
  const identity = () => deskIdentity(state);

  const openReview = () => reviewAction.run(async () => {
    const list = batchSymbols();
    if (!list.length) throw new Error('Select at least one stock in the universe.');
    const wf = await api('/api/workflows');
    const config = wf?.effective_config || {};
    setReview({ symbols: list, config, identity: identity(), revision: state.config_revision,
      estimate: researchEstimate(state, config, list.length, config.research_concurrency) });
  });

  const start = (opts) => reviewAction.run(async () => {
    if (review.identity !== identity() || activeRun(state) || state?.browse_only) throw new Error('Selection or configuration changed. Dismiss and review the current batch again.');
    const body = { symbols: review.symbols, config_revision: review.revision, exclude_fred: opts.exclude_fred };
    if (opts.analysis_date) body.analysis_date = opts.analysis_date;
    const result = await act('run', '/api/runs', body);
    setLaunched({ id: result?.id || result?.run_id, first: review.symbols[0] });
    if (!opts.keep) setBatch(new Set());
    setReview(null);
  });

  const previewDelete = () => deleteAction.run(async () => {
    const list = [...batch];
    if (!list.length) throw new Error('Select stocks to delete.');
    setDel({ ...(await api('/api/research/delete', { symbols: list, preview: true })), identity: identity() });
  });
  const confirmDelete = () => deleteAction.run(async () => {
    if (del.identity !== identity()) throw new Error('The desk changed since this preview. Preview the deletion again.');
    try {
      const done = await api('/api/research/delete', { symbols: del.symbols, expected_revision: del.expected_revision, preview_token: del.preview_token, confirm: true });
      setDel(null); setBatch(new Set()); setLaunched({ deleted: done }); await refresh({fresh: true});
    } catch (e) {
      if (/409/.test(errMessage(e)) || e?.status === 409) { setDel(null); throw new Error('Research changed. Preview the deletion again.'); }
      throw e;
    }
  });
  const deleteBlocked = blocked || ['queued', 'running'].includes(state?.portfolio_model?.status) || pending?.has?.('run') || pending?.has?.('delete');

  const columns = [
    { id: 'batch', label: 'Batch', render: (s) => (
      <Checkbox size="small" checked={batch.has(s)} disabled={!universe.includes(s)} onClick={(e) => e.stopPropagation()} onChange={() => toggle(s)} slotProps={{ input: { 'aria-label': `Include ${s} in research batch` } }} />) },
    { id: 'symbol', label: 'Symbol', render: (s) => s },
    { id: 'company', label: 'Company', render: (s) => state?.company_names?.[s] || UNAVAILABLE },
    { id: 'status', label: 'Research', render: (s) => <Status value={rowStatus(state?.research?.[s])} /> },
    { id: 'rating', label: 'Rating', render: (s) => text(state?.research?.[s]?.rating) },
    { id: 'date', label: 'Trade date', render: (s) => text(state?.research?.[s]?.trade_date) },
  ];

  return (
    <Page
      title="Research"
      subtitle="Pick a batch, review it, then start. Inspecting a stock never changes the batch."
      actions={(
        <Stack direction="row" spacing={1}>
          <Chip label={`${batch.size} in batch`} />
          <Button onClick={() => setBatch(new Set(universe.filter((s) => state?.research?.[s]?.status !== 'completed' || state?.research?.[s]?.completion_gaps?.length)))}>Unfinished</Button>
          <Button onClick={() => setBatch(new Set(universe.filter((s) => { const r = state?.research?.[s]; return !(r?.status === 'completed' && !r.completion_gaps?.length && r.trade_date === today); })))}>Needs research today</Button>
          <Button onClick={() => setBatch(new Set())}>Clear</Button>
          <Button variant="contained" disabled={blocked || reviewAction.busy} onClick={openReview}>Run research</Button>
          {active && <Button color="warning" onClick={() => act('stop', '/api/runs/cancel', { run_id: active.id })}>Stop run</Button>}
        </Stack>
      )}
    >
      {desk.error && <Alert severity="error" onClose={() => desk.setError('')} sx={{ mb: 2 }}>{desk.error}</Alert>}
      {stateError && <Alert severity="warning" sx={{ mb: 2 }}>{String(stateError)}</Alert>}
      {review && review.identity !== identity() && <Alert severity="warning" sx={{ mb: 2 }}>The desk changed since this batch was reviewed; the review must be repeated.</Alert>}
      {reviewAction.error && !review && <Alert severity="error" sx={{ mb: 2 }}>{reviewAction.error}</Alert>}
      {launched?.id && (
        <Alert sx={{ mb: 2 }} onClose={() => setLaunched(null)} action={<Button onClick={() => { setSelectedSymbol(launched.first); setTab('summary'); setLaunched(null); }}>Open {launched.first} summary</Button>}>
          Research run {String(launched.id).slice(0, 8)} started.
        </Alert>
      )}
      {launched?.deleted && <Alert sx={{ mb: 2 }} onClose={() => setLaunched(null)}>Deleted {launched.deleted.deleted_results} result(s), {launched.deleted.deleted_artifacts} artifact(s).</Alert>}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 5 }}>
          <Section title="Stocks" actions={<Button color="error" disabled={deleteBlocked || deleteAction.busy || !batch.size} onClick={previewDelete}>Delete research…</Button>}>
            <Stack direction="row" spacing={1} sx={{flexWrap: "wrap",  mb: 1 }}  useFlexGap>
              <TextField size="small" label="Search" value={query} onChange={(e) => { setQuery(e.target.value); setPageIndex(0); }} />
              <TextField size="small" select label="Filter" value={filter} onChange={(e) => { setFilter(e.target.value); setPageIndex(0); }} sx={{ minWidth: 150 }}>
                {['all', 'selected', 'completed', 'incomplete', 'failed', 'cancelled'].map((f) => <MenuItem key={f} value={f}>{f} ({counts[f] || 0})</MenuItem>)}
              </TextField>
              <TextField size="small" select label="Sort" value={sort} onChange={(e) => setSort(e.target.value)} sx={{ minWidth: 130 }}>
                {[['symbol', 'Symbol'], ['status', 'Status'], ['oldest', 'Oldest'], ['newest', 'Newest']].map(([k, l]) => <MenuItem key={k} value={k}>{l}</MenuItem>)}
              </TextField>
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
              <Button size="small" onClick={() => setBatch((p) => new Set([...p, ...rows.filter((s) => universe.includes(s))]))}>Select matching</Button>
              <Button size="small" onClick={() => setBatch(new Set(symbols.filter((s) => !universe.includes(s))))}>Select outside universe</Button>
            </Stack>
            <DataTable rows={pageRows} columns={columns} getRowId={(s) => s} onRowClick={(s) => setSelectedSymbol(s)} empty="No stocks match." />
            <TablePagination component="div" count={rows.length} page={pageIndex} onPageChange={(_, p) => setPageIndex(p)}
              rowsPerPage={pageSize} rowsPerPageOptions={[25, 50, 100]} onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPageIndex(0); }} />
          </Section>
        </Grid>
        <Grid size={{ xs: 12, md: 7 }}>
          <Section title={inspected ? `${inspected} · ${state?.company_names?.[inspected] || ''}` : 'Inspected stock'}
            actions={inspected && <Button onClick={() => navigate('markets')}>Open instrument</Button>}>
            {detailAction.error && <Alert severity="error">{detailAction.error}</Alert>}
            {inspected && !runId && <Typography>No saved research for {inspected}.</Typography>}
            {linked && (
              <Alert severity={detail && (!linked.report_key || detail.reports?.[linked.report_key]) ? 'info' : 'warning'} sx={{ mb: 1 }}
                action={<Button color="inherit" size="small" onClick={() => setLink(null)}>Show latest saved</Button>}>
                Linked retained report: run {String(linked.run_id).slice(0, 8)}{linked.revision != null ? ` · revision ${linked.revision}` : ''}{linked.report_key ? ` · ${linked.report_key}` : ''}.
                {linked.run_id !== savedRunId && ' This is not the latest saved research for this stock.'}
                {linked.run_id === savedRunId && linked.revision != null && saved?.revision !== linked.revision && ' The saved record has since changed revision; this is the current record for that run, not the linked revision.'}
                {detailAction.error && ' The linked report could not be loaded; no other report is shown in its place.'}
                {detail && linked.report_key && !detail.reports?.[linked.report_key] && ' That report is unavailable in this retained run.'}
              </Alert>
            )}
            <ResearchDisposition symbol={inspected} />
            {inspected ? <Button disabled={!!linked && linked.run_id !== savedRunId} onClick={() => navigate('orders', { tab: 'ticket', symbol: inspected, source: { page: 'research', run_id: savedRunId || null }, terms: null, research: savedRunId ? { symbol: inspected, run_id: savedRunId, revision: state?.research?.[inspected]?.revision || 0, report_key: 'final_trade_decision' } : null })}>Prepare Order (T)</Button> : null}
            <ResearchDetail detail={detail} run={run} symbol={inspected} tab={tab} setTab={setTab} failuresOnly={failuresOnly} setFailuresOnly={setFailuresOnly} desk={desk} />
            {run && <Button sx={{ mt: 1 }} onClick={() => download(JSON.stringify(run, null, 2), `run-${run.id}.json`, 'application/json')}>Export run JSON</Button>}
          </Section>
        </Grid>
      </Grid>
      <ReviewDialog key={review ? review.identity + review.symbols.join() : 'none'} review={review} onClose={() => setReview(null)} onStart={start} busy={reviewAction.busy} error={reviewAction.error} />
      <Dialog open={Boolean(del)} onClose={() => setDel(null)}>
        <DialogTitle>Delete saved research</DialogTitle>
        <DialogContent>
          {del && <>
            <Typography>{del.symbols.join(', ')}</Typography>
            <Typography>{del.result_count} result(s), {del.artifact_count} artifact(s), {count(del.artifact_bytes)} bytes.</Typography>
            {del.identity !== identity() && <Alert severity="warning">The desk changed since this preview. Cancel and preview again.</Alert>}
            {(del.warnings || []).map((w) => <Alert key={w} severity="warning">{w}</Alert>)}
          </>}
          {deleteAction.error && <Alert severity="error">{deleteAction.error}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDel(null)}>Cancel</Button>
          <Button color="error" variant="contained" disabled={deleteAction.busy || deleteBlocked} onClick={confirmDelete}>Delete permanently</Button>
        </DialogActions>
      </Dialog>
      {deleteAction.error && !del && <Alert severity="error">{deleteAction.error}</Alert>}
    </Page>
  );
}

/* ------------------------------------------------------- Supplementary evidence */

const PROVIDERS = { alpaca: ['news', 'corporate_actions'], sec_edgar: ['fundamentals', 'classification'], alpha_vantage: ['fundamentals', 'classification', 'earnings'] };

const SourceLink = ({ url, label = 'Original source' }) => (/^https?:\/\//i.test(url || '')
  ? <Link href={url} target="_blank" rel="noopener noreferrer">{label}</Link> : <span>Source link not recorded</span>);
const STATEMENTS = { balance_sheet: 'Balance sheet', income_statement: 'Income statement', cashflow: 'Cash flow' };
const ev = (v, fallback = UNAVAILABLE) => (v == null || v === '' ? fallback : String(v));

function RecordTable({ columns, rows }) {
  return (
    <TableContainer>
      <Table size="small">
        <TableHead><TableRow>{columns.map(c => <TableCell key={c} scope="col">{c}</TableCell>)}</TableRow></TableHead>
        <TableBody>{rows.map((cells, i) => <TableRow key={i}>{cells.map((c, j) => <TableCell key={j}>{c}</TableCell>)}</TableRow>)}</TableBody>
      </Table>
    </TableContainer>
  );
}

function EvidenceRecords({ records }) {
  const facts = records.filter((r) => r.kind === 'reported_fact');
  const industry = records.filter((r) => r.kind === 'industry');
  const news = records.filter((r) => r.kind === 'news');
  const actions = records.filter((r) => r.reported && r.kind !== 'reported_fact');
  const other = records.filter((r) => !facts.includes(r) && !industry.includes(r) && !news.includes(r) && !actions.includes(r));
  if (!records.length) return <Typography variant="body2">No usable records retained for this scope. Coverage remains unavailable.</Typography>;
  return (
    <Box>
      {facts.length > 0 && <>
        <Typography variant="body2">Reported SEC XBRL facts · latest eligible filed vintage per line item and unit within the saved request boundary. Supported line items are not a complete financial statement. Filing date, reporting period and units remain distinct; no ratios or annualization are inferred.</Typography>
        {[...new Set([...Object.keys(STATEMENTS), ...facts.map((r) => r.statement)])].map((st) => {
          const rows = facts.filter((r) => r.statement === st);
          return (
            <Box key={st}>
              <Typography variant="subtitle2">{STATEMENTS[st] || ev(st, 'Statement unavailable')}</Typography>
              {rows.length ? <RecordTable columns={['Line item', 'Reported value', 'Units / currency', 'Reporting period', 'Filed / form', 'Original filing']}
                rows={rows.map((r) => [ev(r.name || r.tag), ev(r.value), `${r.units || 'Units unavailable'} / ${r.currency || 'Currency not reported'}`,
                  `${r.period_start || 'Start not reported'} → ${r.period_end || 'End not reported'}`, `${r.published_at || 'Filed date unavailable'} / ${r.form || 'Form unavailable'}`,
                  <><SourceLink url={r.source_url} label="Open filing" /><Evidence title="Exact source fields" data={r} /></>])} />
                : <Typography variant="body2">No supported filed facts retained for this statement.</Typography>}
            </Box>);
        })}
      </>}
      {industry.length > 0 && <>
        <Typography variant="subtitle2">SEC SIC industry</Typography>
        <Typography variant="body2">SIC industry is not a sector classification; sector remains unavailable.</Typography>
        <RecordTable columns={['Classification', 'SIC code', 'Industry', 'Retrieved', 'Source']}
          rows={industry.map((r) => [ev(r.classification_system, 'Classification unavailable'), ev(r.code), ev(r.value), dateTime(r.retrieved_at),
            <><SourceLink url={r.source_url} label="Open classification" /><Evidence title="Exact source fields" data={r} /></>])} />
      </>}
      {actions.length > 0 && <>
        <Typography variant="subtitle2">Corporate actions</Typography>
        <Typography variant="body2">Reported event and process dates have different meanings. Review dividends, splits, mergers and other retained actions before comparing prices; saved research inputs are unchanged.</Typography>
        <RecordTable columns={['Action', 'Effective / ex date', 'Process date', 'Provider-reported terms', 'Qualification', 'Source']}
          rows={actions.map((r) => [String(r.kind || 'Unknown action').replaceAll('_', ' '), ev(r.effective_at), ev(r.process_date),
            <dl key="t" style={{ margin: 0 }}>{Object.entries(r.reported).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v === null ? UNAVAILABLE : typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>)}</dl>,
            [r.date_basis, r.limitation, r.comparison_requires_review ? 'Comparison requires review' : null].filter(Boolean).join(' · '),
            <><SourceLink url={r.source_url} label="Open action source" /><Evidence title="Exact source fields" data={r} /></>])} />
      </>}
      {news.length > 0 && <>
        <Typography variant="subtitle2">News</Typography>
        {news.map((r, i) => (
          <Box key={r.id || r.source_url || i} component="article" sx={{ mb: 1 }}>
            <Typography variant="subtitle2" component="h5">{r.title || 'Untitled source article'}</Typography>
            <Typography variant="body2">{r.publisher || 'Publisher unavailable'} · published {dateTime(r.published_at)} · updated {dateTime(r.updated_at)} · retrieved {dateTime(r.retrieved_at)}</Typography>
            <Typography variant="body2">{r.summary || 'No source summary retained.'}</Typography>
            <SourceLink url={r.source_url} label="Read original article" />
            <Evidence title="Exact source fields" data={r} />
          </Box>))}
      </>}
      {other.length > 0 && <>
        <Typography variant="subtitle2">Other provider observations</Typography>
        <RecordTable columns={['Observation', 'Value / units', 'Period / event date', 'Qualification', 'Source']}
          rows={other.map((r) => [ev(r.name || r.kind), `${ev(r.value)} / ${r.units || 'Units not reported'}`, ev(r.effective_at || r.period_end || r.published_at),
            ev(r.limitation || r.provenance || r.date_basis, 'Provider reported'), <><SourceLink url={r.source_url} /><Evidence title="Exact source fields" data={r} /></>])} />
      </>}
    </Box>
  );
}

function SupplementaryEvidence({ symbol, desk }) {
  const { api, page, state, refresh } = desk;
  const [data, setData] = useState(null);
  const [forms, setForms] = useState({});
  const [collecting, setCollecting] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const form = forms[symbol] || { provider: '', scopes: [], start: '', end: '', horizon: '' };
  const setForm = (f) => setForms((p) => ({ ...p, [symbol]: f }));
  const action = useAsyncAction();
  const revision = state?.stock_evidence?.revision;

  useEffect(() => {
    if (!symbol || !(page === 'research' || page === 'markets')) return undefined;
    const ctl = new AbortController();
    setLoadError('');
    api(`/api/stock-evidence?symbol=${encodeURIComponent(symbol)}`, undefined, { signal: ctl.signal })
      .then((d) => { if (d?.symbol !== symbol) throw new Error('Stock-evidence response identity differs'); setData(d); })
      .catch((e) => { if (!ctl.signal.aborted) { setData(null); setLoadError(errMessage(e)); } });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, page, revision, reload]);

  const issue = (() => {
    const allowed = PROVIDERS[form.provider];
    if (!allowed) return 'Choose a provider.';
    if (!form.scopes.length || form.scopes.some((s) => !allowed.includes(s))) return 'Choose at least one scope supported by this provider.';
    if (!form.start || !form.end || form.start > form.end) return 'Choose a start date and an end date on or after it.';
    if (form.scopes.includes('earnings') && !form.horizon) return 'Choose the earnings calendar horizon.';
    return '';
  })();
  const collect = () => action.run(async () => {
    if (issue || collecting) return;
    setCollecting(true);
    try {
      await api('/api/market-history', { action: 'evidence', symbols: [symbol], provider: form.provider, scopes: form.scopes, start: form.start, end: form.end, earnings_horizon: form.horizon });
      await refresh({fresh: true});
    } catch (e) { throw new Error(`Collection request failed or outcome unknown: ${errMessage(e)}`); } finally { setCollecting(false); }
  });
  const observations = Object.entries(data?.observations || data?.scopes || {});
  const configText = data?.configuration?.[form.provider] || state?.stock_evidence?.configuration?.[form.provider] || 'Select a provider to inspect its configuration requirements.';

  return (
    <Section title="Supplementary evidence">
      {action.error && <Alert severity="error">{action.error}</Alert>}
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
        <TextField size="small" select label="Provider" value={form.provider} sx={{ minWidth: 150 }}
          onChange={(e) => setForm({ ...form, provider: e.target.value, scopes: [] })}>
          {Object.keys(PROVIDERS).map((p) => <MenuItem key={p} value={p}>{p}</MenuItem>)}
        </TextField>
        <Autocomplete multiple size="small" options={PROVIDERS[form.provider] || []} value={form.scopes} sx={{ minWidth: 220 }}
          onChange={(_, v) => setForm({ ...form, scopes: v })} renderInput={(p) => <TextField {...p} label="Scopes" />} />
        <TextField size="small" type="date" label="Start" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} slotProps={{ inputLabel: { shrink: true } }} />
        <TextField size="small" type="date" label="End" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} slotProps={{ inputLabel: { shrink: true } }} />
        {form.scopes.includes('earnings') && (
          <TextField size="small" select label="Earnings horizon" value={form.horizon} sx={{ minWidth: 150 }} onChange={(e) => setForm({ ...form, horizon: e.target.value })}>
            {['3month', '6month', '12month'].map((h) => <MenuItem key={h} value={h}>{h}</MenuItem>)}
          </TextField>
        )}
        <Button variant="outlined" disabled={action.busy || collecting || !!issue} onClick={collect}>{collecting ? 'Request pending…' : 'Queue selected evidence'}</Button>
      </Stack>
      <Typography variant="body2" sx={{ mb: 1 }}>{configText}</Typography>
      <Typography variant="body2" role="status" sx={{ mb: 1 }}>{collecting ? 'Collection request pending. A timeout may leave its outcome unknown; inspect job progress before retrying.' : issue || 'Explicit collection queues the chosen provider/scopes only; it does not run research. Progress appears with current-market history.'}</Typography>
      {loadError && <Alert severity="error" sx={{ mb: 1 }} action={<Button color="inherit" size="small" onClick={() => setReload((n) => n + 1)}>Retry saved-evidence read</Button>}>{loadError}</Alert>}
      {!data && !loadError && <Typography variant="body2">Saved evidence has not loaded.</Typography>}
      {data && !observations.length && <Typography variant="body2">No supplementary evidence saved for this stock. SEC facts, SIC industry, corporate actions and news remain unavailable until explicitly collected.</Typography>}
      {observations.map(([scope, o]) => (
        <Box key={scope} sx={{ mb: 2 }}>
          <Typography variant="subtitle2">{scope} · {text(o.provider || 'Provider unavailable')}</Typography>
          <Typography variant="body2">Status {text(o.latest_attempt?.status || o.status || 'Unknown')} · retrieved {dateTime(o.captured_at)} · pagination {o.complete === true ? 'complete' : 'incomplete'}</Typography>
          {o.retained_older_data && <Alert severity="warning">Older usable observations retained after a failed or incomplete latest request. Their original dates remain shown.</Alert>}
          <ul>{(o.latest_attempt?.gaps || o.gaps || []).map((g) => <li key={g}>{g}</li>)}</ul>
          <EvidenceRecords records={o.records || []} />
          <Evidence title="Source receipts, hashes and request qualifications" data={{ request: o.request, receipts: o.receipts, latest_attempt: o.latest_attempt, gaps: o.gaps }} />
        </Box>
      ))}
    </Section>
  );
}

/* ------------------------------------------------------------------- Charts */

const TIMEFRAMES = ['1Min', '5Min', '15Min', '30Min', '1Hour', '1Day'];
const RANGES = [['7', '1W'], ['30', '1M'], ['90', '3M'], ['180', '6M'], ['all', 'All saved']];
const SCOPE_KEYS = ['instrument_id', 'currency', 'provider', 'feed', 'adjustment', 'session', 'timeframe'];
const PRICE_FIELD = { open: 'o', high: 'h', low: 'l', close: 'c' };
const isDaily = (tf) => tf === '1Day';
const epochMs = (t, tf) => (isDaily(tf) ? Date.parse(`${t}T00:00:00Z`) : t * 1000);
const fmtTime = (t, tf) => (t == null ? UNAVAILABLE : window.DeskMarketChart?.formatTime?.(t, tf) ?? String(t));
const timeInput = (value, tf) => (isDaily(tf) ? value : value === '' ? '' : Number(value));

const missingCapabilities = () => [
  !window.LightweightCharts && 'LightweightCharts',
  !window.LightweightChartsDrawing && 'LightweightChartsDrawing (drawing plugin)',
  !window.DeskMarketChart?.mount && 'DeskMarketChart (market-chart.js)',
].filter(Boolean);

function chartPin(h) {
  const s = h?.source || {};
  if (!s.path || !s.sha256 || !h?.derivation_identity) return null;
  return {
    context: h.context === 'current' ? 'current' : 'saved', symbol: h.symbol, timeframe: h.timeframe || '1Day',
    ...(h.context === 'current' ? { cache_key: h.key } : { run_id: h.run_id }),
    artifact: { path: s.path, sha256: s.sha256 }, derivation_identity: h.derivation_identity,
  };
}
const samePin = (a, b) => !!a && !!b
  && ['context', 'symbol', 'timeframe', 'cache_key', 'run_id', 'derivation_identity'].every((k) => (a[k] ?? null) === (b[k] ?? null))
  && a.artifact?.path === b.artifact?.path && a.artifact?.sha256 === b.artifact?.sha256;

function drawingScope(h) {
  const s = h.source || {};
  return {
    symbol: h.symbol, timeframe: h.timeframe || '1Day', context: h.context === 'current' ? 'current' : 'saved',
    instrument_id: h.instrument_id ?? s.instrument_id ?? h.required_coverage?.provenance?.asset_id ?? null,
    currency: h.currency ?? s.currency ?? null, unit: 'price', provider: h.provider ?? s.vendor ?? null,
    feed: h.feed ?? s.feed ?? null, adjustment: h.adjustment ?? s.adjustment ?? null, session: h.session ?? s.session ?? null,
  };
}
const scopeId = (scope) => JSON.stringify(Object.keys(scope).sort().map((k) => [k, scope[k]]));
const paneMatches = (a, b) => ['symbol', 'timeframe', 'context'].every((k) => a?.[k] === b[k]);

function MarketChartCanvas({ bars, indicators, timeframe, comparison, mountKey, scope, drawings, selectedId, tool, handlers, ctlRef }) {
  const host = useRef(null);
  const live = useRef({});
  live.current = { drawings, selectedId, tool, handlers };
  const sid = scopeId(scope);
  const seq = useRef(0);
  // A new host element per chart identity: the adapter refuses to remount a live element.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const hostKey = useMemo(() => ++seq.current, [bars, indicators, timeframe, comparison, mountKey, sid]);
  useEffect(() => {
    const el = host.current;
    const D = window.DeskMarketChart;
    if (!el || !D?.mount) return undefined;
    const h = () => live.current.handlers;
    let ctl = null;
    try {
      ctl = D.mount(el, {
        bars, indicators, key: mountKey, timeframe, comparison,
        drawings: live.current.drawings, drawingScope: comparison ? null : scope,
        selectedDrawingId: live.current.selectedId, drawingTool: comparison ? null : live.current.tool,
        onSelect: (t) => h().select?.(t), onDrawingSelect: (id) => h().drawingSelect?.(id),
        onDrawingChange: (d) => h().drawingChange?.(d), onDrawingPoint: (p) => h().drawingPoint?.(p),
        onDrawingStatus: (s) => h().drawingStatus?.(s),
      });
    } catch (e) { h().error?.(errMessage(e)); }
    ctlRef.current = ctl;
    return () => { ctlRef.current = null; ctl?.destroy?.(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hostKey]);
  useEffect(() => { ctlRef.current?.setTool?.(comparison ? null : tool); }, [tool, comparison, ctlRef]);
  return <Box key={hostKey} ref={host} role="img" aria-label="Recorded market chart" sx={{ height: 380, width: '100%', position: 'relative' }} />;
}

/* Chart analysis state is kept per exact raw source so a pane change never discards authored definitions. */
const FAMILIES = { transform: ['heikin_ashi', 'renko', 'kagi', 'line_break', 'point_figure'], study: ['kama', 'cci', 'donchian', 'ichimoku'] };
const COMPONENTS = { kama: ['kama'], cci: ['cci'], donchian: ['upper', 'middle', 'lower'], ichimoku: ['tenkan', 'kijun', 'span_a', 'span_b', 'chikou'] };
const SETTING_LABELS = {
  box_size: 'Exact brick / box size', reversal: 'Reversal boxes', reversal_kind: 'Kagi reversal basis', reversal_amount: 'Exact reversal amount / percent',
  lines: 'Completed-line lookback', period: 'Period / observations', fast: 'Fast smoothing period', slow: 'Slow smoothing period', scalar: 'CCI scale',
  ma_type: 'Moving average', lag: 'Lag / actual bars', tenkan: 'Conversion period', kijun: 'Base period', senkou: 'Span-B period', displacement: 'Displacement',
};
const INTEGER_SETTINGS = ['reversal', 'lines', 'period', 'fast', 'slow', 'lag', 'tenkan', 'kijun', 'senkou', 'displacement'];
function analysisDefaults(kind, family) {
  if (kind === 'formula') return { expression: 'close', parameters: [], units: 'price', display_shift: '0', render: 'line' };
  if (kind === 'seasonality') return { alignment: 'calendar', comparison: 'normalized' };
  return ({
    heikin_ashi: {}, renko: { box_size: '', reversal: '2' }, kagi: { reversal_kind: 'fixed', reversal_amount: '' }, line_break: { lines: '3' },
    point_figure: { box_size: '', reversal: '3' }, kama: { period: '10', fast: '2', slow: '30' }, cci: { period: '20', scalar: '0.015', ma_type: 'SIMPLE' },
    donchian: { period: '20', lag: '0' }, ichimoku: { tenkan: '9', kijun: '26', senkou: '52', displacement: '26' },
  })[family] || {};
}
const defKey = (row) => `${row.definition.id}:${row.definition.revision}:${row.sha256}`;
const analysisStore = new Map();
const integerOf = (value, key) => {
  if (String(value).trim() === '' || !Number.isSafeInteger(Number(value))) throw new Error(`Enter an integer for ${key}`);
  return Number(value);
};

function ChartAnalysis({ h, pin, desk, onOpenSource }) {
  const { api, state, refresh } = desk;
  const pinKey = JSON.stringify(pin);
  const init = useRef(analysisStore.get(pinKey)).current;
  const [meta, setMeta] = useState(null);
  const [draft, setDraft] = useState(init?.draft ?? { name: '', kind: 'transform', family: 'heikin_ashi', settings: analysisDefaults('transform', 'heikin_ashi') });
  const [deps, setDeps] = useState(init?.deps ?? []);
  const [selKey, setSelKey] = useState(init?.selKey ?? null);
  const [changed, setChanged] = useState(init?.changed ?? false);
  const [budget, setBudget] = useState('60');
  const [calc, setCalc] = useState(null);
  const [eventOrdinal, setEventOrdinal] = useState(null);
  const [sourceOrdinal, setSourceOrdinal] = useState(null);
  const [yearScale, setYearScale] = useState('common');
  const action = useAsyncAction();
  const analysisHost = useRef(null);
  useEffect(() => { analysisStore.set(pinKey, { draft, deps, selKey, changed }); }, [pinKey, draft, deps, selKey, changed]);

  const history = meta?.history || [];
  const caps = meta?.capabilities || {};
  const edit = (fn) => { setDraft((d) => { const n = structuredClone(d); fn(n); return n; }); setChanged(true); };
  const setKind = (kind, family) => {
    const fam = FAMILIES[kind]?.includes(family) ? family : FAMILIES[kind]?.[0];
    setDraft((d) => ({ ...d, kind, family: fam, settings: analysisDefaults(kind, fam) })); setDeps([]); setChanged(true);
  };
  const loadDefinition = (row) => {
    const d = row.definition;
    const settings = structuredClone(d.settings);
    delete settings.family;
    if (d.kind === 'formula') settings.parameters = Object.entries(d.settings.parameters).map(([name, p]) => ({ name, ...p }));
    setDraft({ name: d.name, kind: d.kind, family: d.settings.family, settings });
    setSelKey(defKey(row)); setDeps((row.dependencies || []).map((r) => `${r.id}:${r.revision}:${r.sha256}`)); setChanged(false);
  };
  const call = (body) => api('/api/market-history', { workspace_revision: state.workspace.revision, ...body });

  const load = () => action.run(async () => {
    const r = await api('/api/market-history');
    if (!r.chart_analysis) throw new Error('Chart analysis metadata unavailable from this source version.');
    setMeta(r.chart_analysis);
    if (r.chart_analysis.workspace_revision > state.workspace.revision) await refresh({fresh: true});
  });
  const definition = () => {
    const settings = structuredClone(draft.settings);
    if (draft.kind === 'formula') {
      const parameters = {};
      for (const p of settings.parameters) {
        if (!p.name || parameters[p.name]) throw new Error('Use distinct parameter names.');
        parameters[p.name] = { value: p.value, units: p.units };
      }
      settings.parameters = parameters;
      settings.display_shift = integerOf(settings.display_shift, 'display shift');
    } else if (draft.kind === 'seasonality') settings.adjustment = h.adjustment ?? h.source?.adjustment;
    else {
      settings.family = draft.family;
      for (const key of INTEGER_SETTINGS) if (key in settings) settings[key] = integerOf(settings[key], key);
    }
    const row = history.find((r) => defKey(r) === selKey);
    return { id: row?.definition.id, revision: row?.definition.revision || 0, name: draft.name, kind: draft.kind, settings };
  };
  const adoptWorkspace = async (response) => {
    const record = await api('/api/workspace');
    if (record.revision !== response.chart_analysis.workspace_revision) throw new Error('Workspace changed after the chart definition save; reload the saved workspace before continuing.');
    await refresh({fresh: true});
  };
  const save = () => action.run(async () => {
    if (!meta) throw new Error('Load saved definitions first.');
    const dependencies = deps.map((key) => {
      const row = history.find((r) => defKey(r) === key);
      if (!row) throw new Error('Pinned dependency revision unavailable.');
      return { id: row.definition.id, revision: row.definition.revision, sha256: row.sha256 };
    });
    const r = await call({ action: 'chart_definition_save', definition: definition(), dependencies });
    setMeta(r.chart_analysis);
    await adoptWorkspace(r);
    const row = r.chart_analysis.definitions.find((x) => x.definition.id === r.saved_definition_id);
    if (!row) throw new Error('Saved definition identity unavailable.');
    loadDefinition(row);
  });
  const acceptCalc = (c) => {
    const p = c.source_pin;
    if (p.symbol !== h.symbol || p.context !== pin.context || p.timeframe !== pin.timeframe) throw new Error('This retained calculation belongs to a different instrument, context or interval.');
    setCalc(c); setEventOrdinal(null); setSourceOrdinal(null);
  };
  const calculate = () => action.run(async () => {
    const row = history.find((r) => defKey(r) === selKey);
    if (!row || changed) throw new Error('Save and select an unchanged definition revision.');
    const budgetSeconds = Number(budget);
    if (!Number.isInteger(budgetSeconds) || budgetSeconds < 1 || budgetSeconds > 600) throw new Error('Choose a whole-second chart budget from 1 through 600.');
    const r = await call({ action: 'chart_calculate', definition_id: row.definition.id, definition_revision: row.definition.revision, definition_sha256: row.sha256, source_pin: pin, budget_seconds: budgetSeconds });
    if (r.chart_analysis) setMeta(r.chart_analysis);
    if (r.calculation) acceptCalc(r.calculation);
  });
  const openCalc = (id) => action.run(async () => {
    const r = await call({ action: 'chart_calculation_open', id });
    if (r.chart_analysis) setMeta(r.chart_analysis);
    if (!r.calculation) return;
    acceptCalc(r.calculation);
    const row = (r.chart_analysis || meta).history.find((x) => x.sha256 === r.calculation.definition_sha256 && x.definition.id === r.calculation.definition_id && x.definition.revision === r.calculation.definition_revision);
    if (row) loadDefinition(row); else { setSelKey(null); setChanged(true); }
  });
  const cancelCalc = (id) => action.run(async () => {
    const r = await call({ action: 'chart_calculation_cancel', id });
    if (r.chart_analysis) setMeta(r.chart_analysis);
    if (r.calculation) acceptCalc(r.calculation);
  });
  const exportDefs = () => action.run(async () => {
    const row = history.find((r) => defKey(r) === selKey);
    const r = await call({ action: 'chart_definition_export', ...(row ? { id: row.definition.id, revision: row.definition.revision, sha256: row.sha256 } : {}) });
    download(JSON.stringify(r.bundle, null, 2), 'chart-definitions.json', 'application/json');
  });
  const importDefs = (file) => action.run(async () => {
    const r = await call({ action: 'chart_definition_import', bundle: JSON.parse(await file.text()) });
    setMeta(r.chart_analysis);
    await adoptWorkspace(r);
  });

  const events = calc?.result?.events || [];
  const selectedEvent = events.find((e) => e.output_ordinal === eventOrdinal) || events.at(-1);
  const range = selectedEvent?.source_range;
  const sourceRows = (calc?.spec?.rows || []).filter((r) => r.raw && (!range || (r.source_ordinal >= range[0] && r.source_ordinal <= range[1])));
  const sourceRow = sourceRows.find((r) => r.source_ordinal === sourceOrdinal) || sourceRows.at(-1);
  const openSource = () => action.run(async () => {
    if (!sourceRow) throw new Error('No actual contributing source bar selected.');
    const r = await api('/api/investor', { action: 'chart_source', pin: calc.source_pin });
    const raw = r.chart_source;
    if (!samePin(chartPin(raw), calc.source_pin) || !raw.bars.some((b) => b.t === sourceRow.t)) throw new Error('Exact raw source identity or selected bar is unavailable.');
    onOpenSource({
      chart: raw, time: sourceRow.t,
      reference: selectedEvent ? { calculation_id: calc.id, result_sha256: calc.result_sha256, event_ordinal: selectedEvent.output_ordinal, source_ordinal: sourceRow.source_ordinal } : undefined,
    });
  });

  useEffect(() => {
    const el = analysisHost.current;
    if (!el || !calc?.result || !window.DeskMarketChart?.mountAnalysis) return undefined;
    // The adapter renders escaped HTML/SVG into this dedicated element; React owns nothing inside it.
    window.DeskMarketChart.mountAnalysis(el, calc.result, {
      sourceRows: calc.spec?.rows || [], selectedSourceOrdinal: sourceOrdinal, yearScale, definition: calc.spec?.definition,
      onSelect: (ordinal) => { setEventOrdinal(ordinal); setSourceOrdinal(null); },
    });
    return () => el.replaceChildren();
  }, [calc, sourceOrdinal, yearScale]);

  const s = draft.settings;
  const field = (key, label, value, onChange, choices) => (
    <TextField key={key} size="small" label={label} value={value ?? ''} select={!!choices} onChange={(e) => onChange(e.target.value)} sx={{ minWidth: 170 }}>
      {choices?.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
    </TextField>
  );
  const setSetting = (key) => (v) => edit((d) => { d.settings[key] = v; });
  const dependencyTemplates = history.filter((r) => deps.includes(defKey(r))).flatMap((r) => (r.definition.kind === 'formula'
    ? [`${r.definition.name}(${Object.keys(r.definition.settings.parameters).sort().join(', ')})`]
    : (COMPONENTS[r.definition.settings.family] || []).map((c) => `${r.definition.name}__${c}`)));
  const savedCalcs = (meta?.calculations || []).filter((i) => i.source_pin?.symbol === h.symbol && i.source_pin.context === pin.context && i.source_pin.timeframe === pin.timeframe);

  return (
    <Accordion disableGutters onChange={(_, open) => { if (open && !meta) load(); }}>
      <AccordionSummary><Typography>Chart analysis · transforms, studies, seasonality and formulas</Typography></AccordionSummary>
      <AccordionDetails>
        <Typography variant="body2" sx={{ mb: 1 }}>Derived analysis of this exact retained source. The raw OHLC chart stays separate. Saving never calculates or collects data.</Typography>
        {action.error && <Alert severity="error" sx={{ mb: 1 }}>{action.error}</Alert>}
        <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
          <Button variant="outlined" disabled={action.busy} onClick={load}>Load saved definitions and calculation index</Button>
          <Button variant="outlined" disabled={action.busy || !meta} onClick={exportDefs}>Export selected revision or full library</Button>
          <Button component="label" variant="outlined" disabled={action.busy || !meta}>Import definition bundle
            <input hidden type="file" accept="application/json,.json" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) importDefs(f); }} />
          </Button>
        </Stack>
        {meta && <>
          <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
            <TextField size="small" select label="Saved definition revision" value={selKey ?? ''} sx={{ minWidth: 280 }}
              onChange={(e) => { const row = history.find((r) => defKey(r) === e.target.value); if (row) loadDefinition(row); else { setSelKey(null); setChanged(true); } }}>
              <MenuItem value="">New definition</MenuItem>
              {history.map((r) => <MenuItem key={defKey(r)} value={defKey(r)}>{r.definition.name} · {r.definition.kind} · revision {r.definition.revision}</MenuItem>)}
            </TextField>
            {field('name', 'Reusable identifier', draft.name, (v) => edit((d) => { d.name = v; }))}
            {field('kind', 'Analysis kind', draft.kind, (v) => setKind(v), ['transform', 'study', 'seasonality', 'formula'])}
          </Stack>
          <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
            {draft.kind === 'formula' && <>
              <TextField size="small" multiline minRows={2} label="Formula expression" value={s.expression} sx={{ minWidth: 360 }} slotProps={{ htmlInput: { spellCheck: false } }} onChange={(e) => setSetting('expression')(e.target.value)} />
              {field('render', 'Output presentation', s.render, setSetting('render'), ['line', 'histogram', 'overlay'])}
              {field('units', 'Declared output units', s.units, setSetting('units'), caps.units || [])}
              {field('display_shift', 'Forward display offset / logical bars', s.display_shift, setSetting('display_shift'))}
            </>}
            {draft.kind === 'seasonality' && <>
              {field('alignment', 'Year comparison alignment', s.alignment, setSetting('alignment'), ['calendar', 'session'])}
              {field('comparison', 'Comparison scale', s.comparison, setSetting('comparison'), ['raw', 'normalized'])}
            </>}
            {(draft.kind === 'transform' || draft.kind === 'study') && <>
              {field('family', draft.kind === 'study' ? 'Parameterized study' : 'Transformed display family', draft.family, (v) => setKind(draft.kind, v), FAMILIES[draft.kind])}
              {Object.keys(s).map((key) => field(key, SETTING_LABELS[key] || key, s[key], setSetting(key), key === 'reversal_kind' ? ['fixed', 'percent'] : key === 'ma_type' ? ['SIMPLE'] : undefined))}
            </>}
          </Stack>
          {draft.kind === 'formula' && <Box sx={{ mb: 1 }}>
            <Typography variant="subtitle2">Exact scalar parameters</Typography>
            {s.parameters.map((p, i) => (
              <Stack key={i} direction="row" spacing={1} sx={{ my: 0.5 }}>
                {field(`pn${i}`, 'Name', p.name, (v) => edit((d) => { d.settings.parameters[i].name = v; }))}
                {field(`pv${i}`, 'Exact decimal value', p.value, (v) => edit((d) => { d.settings.parameters[i].value = v; }))}
                {field(`pu${i}`, 'Units', p.units, (v) => edit((d) => { d.settings.parameters[i].units = v; }), (caps.units || []).filter((u) => u !== 'boolean'))}
                <Button onClick={() => edit((d) => { d.settings.parameters.splice(i, 1); })}>Remove</Button>
              </Stack>))}
            <Button onClick={() => edit((d) => { d.settings.parameters.push({ name: '', value: '', units: '' }); })}>Add typed parameter</Button>
            <Typography variant="subtitle2" sx={{ mt: 1 }}>Insert function</Typography>
            <Stack direction="row"  useFlexGap spacing={0.5} sx={{flexWrap: "wrap"}}>
              {(caps.formula_functions || []).map((name) => <Button key={name} size="small" onClick={() => edit((d) => { d.settings.expression += `${name}(`; })}>{name}</Button>)}
            </Stack>
            <Typography variant="subtitle2" sx={{ mt: 1 }}>Pinned reusable definitions</Typography>
            {history.filter((r) => ['formula', 'study'].includes(r.definition.kind)).map((r) => (
              <FormControlLabel key={defKey(r)} label={`${r.definition.name} · revision ${r.definition.revision}`}
                control={<Checkbox checked={deps.includes(defKey(r))} onChange={(e) => { setDeps(e.target.checked ? [...deps, defKey(r)] : deps.filter((k) => k !== defKey(r))); setChanged(true); }} />} />))}
            <Stack direction="row"  useFlexGap spacing={0.5} sx={{flexWrap: "wrap"}}>
              {dependencyTemplates.map((t) => <Button key={t} size="small" onClick={() => edit((d) => { d.settings.expression += t; })}>Insert {t}</Button>)}
            </Stack>
          </Box>}
          <Stack direction="row" spacing={1}  sx={{alignItems: "center",  mb: 1 }}>
            <Button variant="contained" disabled={action.busy} onClick={save}>Save immutable definition revision</Button>
            <TextField size="small" type="number" label="Total budget / seconds" value={budget} onChange={(e) => setBudget(e.target.value)} slotProps={{ htmlInput: { min: 1, max: 600, step: 1 } }} />
            <Button variant="outlined" disabled={action.busy || !selKey || changed} onClick={calculate}>Calculate exact saved revision</Button>
          </Stack>
          <Typography variant="caption" component="p">The 1–600 second budget starts at admission, including queue wait. Calculation uses the pinned raw artifact and needs no trading session.</Typography>
          <Typography variant="subtitle2" sx={{ mt: 1 }}>Saved calculations</Typography>
          {savedCalcs.length ? savedCalcs.map((i) => {
            const d = history.find((r) => r.definition.id === i.definition_id && r.definition.revision === i.definition_revision && r.sha256 === i.definition_sha256)?.definition;
            return <Stack key={i.id} direction="row" spacing={1}  sx={{alignItems: "center"}}><Button size="small" onClick={() => openCalc(i.id)}>{d ? `${d.name} · ${d.settings?.family || d.kind} · revision ${d.revision}` : `Definition ${i.definition_id} · revision ${i.definition_revision}`} · {i.status}</Button><Typography variant="caption">{dateTime(i.created_at)}</Typography></Stack>;
          }) : <Typography variant="body2">No saved calculations for this source.</Typography>}
          <Evidence title="Installed calculation capabilities and conventions" data={caps} />
        </>}
        {calc && <Box sx={{ mt: 2 }}>
          <Typography>{calc.status} · budget {text(calc.execution?.budget_seconds)} s · {calc.reason || ''}</Typography>
          <Typography variant="body2">Retained calculation {calc.id} · source {calc.source_pin?.artifact?.sha256} · {samePin(calc.source_pin, pin) ? 'matches this raw chart' : 'different retained source from the chart above'}</Typography>
          {calc.termination?.termination_confirmed === false && <Alert severity="warning">Worker termination is unconfirmed. No completed numerical result is claimed.</Alert>}
          {['queued', 'running'].includes(calc.status) && <Button disabled={action.busy} onClick={() => cancelCalc(calc.id)}>Cancel this calculation</Button>}
          <Evidence title="Queue, execution and termination evidence" data={{ execution: calc.execution, created_at: calc.created_at, started_at: calc.started_at, finished_at: calc.finished_at, termination: calc.termination, termination_history: calc.termination_history }} />
          {calc.result ? <>
            <Typography variant="body2">{calc.result.coverage?.complete === true ? 'Declared source coverage complete.' : 'Coverage gaps or unverified continuity remain; inspect the exact unavailable ordinals.'}</Typography>
            {calc.result.seasonality && <TextField size="small" select label="Yearly value scale" value={yearScale} onChange={(e) => setYearScale(e.target.value)} sx={{ my: 1, minWidth: 220 }}>
              <MenuItem value="common">Common scale across years</MenuItem><MenuItem value="separate">Separate labeled scale per year</MenuItem></TextField>}
            <Box ref={analysisHost} aria-label="Derived analysis display" />
            {events.length > 0 && <TextField size="small" select label="Derived event" value={selectedEvent?.output_ordinal ?? ''} sx={{ my: 1, minWidth: 320 }} onChange={(e) => { setEventOrdinal(Number(e.target.value)); setSourceOrdinal(null); }}>
              {events.map((e) => <MenuItem key={e.output_ordinal} value={e.output_ordinal}>Event {e.output_ordinal} · source {e.source_ordinal} · {text(e.t)} · {e.style || e.direction || ''}</MenuItem>)}
            </TextField>}
            {selectedEvent && <Evidence title="Exact derived geometry (not execution prices)" data={selectedEvent} />}
            <Typography variant="subtitle2">Actual source OHLC inspection</Typography>
            {sourceRow ? <>
              <TextField size="small" select label="Actual retained source bar" value={sourceRow.source_ordinal} sx={{ my: 1, minWidth: 260 }} onChange={(e) => setSourceOrdinal(Number(e.target.value))}>
                {sourceRows.map((r) => <MenuItem key={r.source_ordinal} value={r.source_ordinal}>Source {r.source_ordinal} · {r.t}</MenuItem>)}
              </TextField>
              <Typography>O {text(sourceRow.raw.o)} · H {text(sourceRow.raw.h)} · L {text(sourceRow.raw.l)} · C {text(sourceRow.raw.c)} · V {text(sourceRow.raw.v)}</Typography>
              <Button variant="outlined" disabled={action.busy} onClick={openSource}>Open this actual bar in the raw chart</Button>
            </> : <Typography variant="body2">No actual contributing raw bar is available for this selection.</Typography>}
          </> : <Typography>No numerical result is claimed.</Typography>}
          <Evidence title="Definitions, algorithm, precision, initialization and source evidence" data={{ spec: calc.spec, result: calc.result }} />
        </Box>}
      </AccordionDetails>
    </Accordion>
  );
}

const DRAWING_KINDS = ['horizontal-line', 'trend-line', 'text'];

/**
 * Reusable retained-OHLC instrument chart (read-only by itself).
 * Props:
 *  symbol          required US equity symbol.
 *  desk            optional useDesk() value; defaults to the context.
 *  active          reads run only while true (default: desk.page === 'markets'); pass true on a visible Dashboard.
 *  defaultContext  'current' (IEX cache) or 'saved' (research inputs); initial context only.
 *  copyTarget      optional {symbol, fields:[[key,label]], terms, expectedRevision, instrumentId, onApply(chart_copy, {symbol})};
 *                  the host owns the ticket. Review is explicit; onApply fires only from the explicit apply button.
 *  onDrawingAlert  optional (payload) => void; default is navigate('alerts', payload) with kind 'drawing-alert'.
 *  onSelectBar     optional (time) => void.
 *  onLoaded        optional (history|null) => void, the exact retained chart response.
 * Requires window.LightweightCharts, window.LightweightChartsDrawing and window.DeskMarketChart (market-chart.js); a missing one is reported, never emulated.
 */
export function InstrumentChart({ symbol, desk: provided, active, defaultContext = 'current', copyTarget, onDrawingAlert, onSelectBar, onLoaded }) {
  const ctx = useDesk();
  const desk = provided || ctx;
  const { api, page, state, refresh, navigate } = desk;
  const on = active ?? page === 'markets';
  const [mode, setMode] = useState(defaultContext);
  const [timeframe, setTimeframe] = useState('1Day');
  const [cacheKey, setCacheKey] = useState('');
  const [form, setForm] = useState({ start: '', end: '', asof: dateNY(), adjustment: '' });
  const [result, setResult] = useState(null);
  const [range, setRange] = useState('all');
  const [selTime, setSelTime] = useState(null);
  const [compareKey, setCompareKey] = useState('');
  const [other, setOther] = useState(null);
  const [anchor, setAnchor] = useState(null);
  const [priceKind, setPriceKind] = useState('close');
  const [destination, setDestination] = useState('');
  const [copyReview, setCopyReview] = useState(null);
  const [derivedOrigin, setDerivedOrigin] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [selId, setSelId] = useState('');
  const [newKind, setNewKind] = useState('horizontal-line');
  const [tool, setTool] = useState(null);
  const [placed, setPlaced] = useState(0);
  const [valueKind, setValueKind] = useState('c');
  const [statuses, setStatuses] = useState([]);
  const [notice, setNotice] = useState('');
  const [chartError, setChartError] = useState('');
  const points = useRef([]);
  const chartCtl = useRef(null);
  const formSeeded = useRef(false);
  const action = useAsyncAction();
  const drawAction = useAsyncAction();

  const ws = state?.workspace;
  const saved = state?.research?.[symbol];
  const allEntries = Object.values(state?.market_history?.data?.entries || {});
  const entries = allEntries.filter((e) => e.symbol === symbol && e.timeframe === timeframe);
  const jobs = Object.values(state?.market_history?.data?.jobs || {});
  const historyRevision = state?.market_history?.revision;
  const missing = missingCapabilities();

  useEffect(() => {
    if (!on || !symbol) return undefined;
    if (mode === 'saved' && !saved?.run_id) { setResult(null); return undefined; }
    const ctl = new AbortController();
    const path = mode === 'saved'
      ? `/api/instruments/${encodeURIComponent(symbol)}?run_id=${encodeURIComponent(saved.run_id)}`
      : `/api/market-history?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}${cacheKey ? `&key=${encodeURIComponent(cacheKey)}` : ''}`;
    api(path, undefined, { signal: ctl.signal }).then((r) => {
      if (r?.symbol !== symbol || !Array.isArray(r.bars)) throw new Error('Chart response does not match the selected stock.');
      if (mode === 'saved' && r.run_id !== saved.run_id) throw new Error('Saved chart belongs to a different run.');
      if (mode === 'current' && (r.context !== 'current' || r.run_id || r.timeframe !== timeframe || (cacheKey && r.key !== cacheKey))) throw new Error('Current-market chart response does not match the requested cache.');
      setResult(r); action.setError(''); onLoaded?.(r);
      if (mode === 'current' && !formSeeded.current) {
        formSeeded.current = true;
        setForm((f) => ({ start: r.start || f.start, end: r.end || f.end, asof: r.asof || f.asof, adjustment: r.adjustment || f.adjustment }));
      }
    }).catch((e) => { if (!ctl.signal.aborted) { setResult(null); onLoaded?.(null); action.setError(errMessage(e)); } });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, symbol, mode, timeframe, cacheKey, saved?.run_id, historyRevision]);

  const compareEntry = allEntries.find((e) => e.key === compareKey);
  useEffect(() => {
    if (!on || !compareEntry || mode !== 'current') { setOther(null); return undefined; }
    const ctl = new AbortController();
    api(`/api/market-history?symbol=${encodeURIComponent(compareEntry.symbol)}&timeframe=${encodeURIComponent(compareEntry.timeframe)}&key=${encodeURIComponent(compareEntry.key)}`, undefined, { signal: ctl.signal }).then((r) => {
      if (r?.symbol !== compareEntry.symbol || r.context !== 'current' || r.key !== compareEntry.key || r.timeframe !== compareEntry.timeframe) throw new Error('Comparison response does not match the selected cache.');
      setOther(r);
    }).catch((e) => { if (!ctl.signal.aborted) { setOther(null); action.setError(errMessage(e)); } });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, compareKey, mode, historyRevision]);

  const h = result;
  const tf = h ? (h.context === 'current' ? h.timeframe : h.timeframe || '1Day') : '1Day';
  const all = h?.bars;
  const cutoff = all?.length && range !== 'all' ? epochMs(all.at(-1).t, tf) - Number(range) * 86400000 : null;
  const view = useMemo(() => {
    if (!h || !all?.length) return { bars: [], comparison: null, error: '' };
    let bars = all.filter((b) => cutoff === null || epochMs(b.t, tf) >= cutoff);
    if (!compareKey) return { bars, comparison: null, error: '' };
    try {
      if (!other) throw new Error('Selected comparison cache has not been read or is unavailable.');
      const c = window.DeskMarketChart.compare({ ...h, bars: all }, other, anchor);
      const series = c.series.map((item) => ({ ...item, points: item.points.filter((p) => cutoff === null || epochMs(p.time, tf) >= cutoff) }));
      const common = new Set(series[0].points.map((p) => p.time));
      bars = bars.filter((b) => common.has(b.t));
      return { bars, comparison: { ...c, series }, error: '' };
    } catch (e) { return { bars: [], comparison: null, error: errMessage(e) }; }
  }, [h, all, cutoff, tf, compareKey, other, anchor]);
  const indicators = useMemo(() => h?.indicators || [], [h]);
  const scope = useMemo(() => (h ? drawingScope(h) : null), [h]);
  const pin = useMemo(() => (h ? chartPin(h) : null), [h]);

  const bar = view.bars.find((b) => String(b.t) === String(selTime)) || view.bars.at(-1);
  const priorIndex = all && bar ? all.findIndex((b) => b.t === bar.t) - 1 : -1;
  const prior = priorIndex >= 0 ? all[priorIndex] : null;
  const closeNow = number(bar?.raw?.c ?? bar?.c);
  const closePrior = number(prior?.raw?.c ?? prior?.c);
  const movement = closeNow !== null && closePrior !== null && closePrior > 0 ? (closeNow / closePrior - 1) * 100 : null;
  const rawOf = (b, k) => text(b?.raw?.[k] ?? b?.[k]);

  const post = (body) => action.run(async () => { await api('/api/market-history', body); await refresh({fresh: true}); });

  /* Drawings: saved revisions come from the workspace; edits stay local drafts until an explicit Save or Remove. */
  const savedDrawings = ws?.data?.drawings || {};
  const paneDrawings = scope ? Object.values({ ...savedDrawings, ...drafts }).filter((d) => !d.deleted && paneMatches(d.scope, scope)) : [];
  const selected = (() => {
    const d = drafts[selId] ?? savedDrawings[selId];
    return d && (!d.deleted || drafts[selId]) && scope && paneMatches(d.scope, scope) ? d : null;
  })();
  const comparing = !!view.comparison;
  const incompatible = !!selected && scope && scopeId(selected.scope) !== scopeId(scope);
  const stage = (d, push = true) => {
    setDrafts((p) => ({ ...p, [d.id]: structuredClone(d) })); setSelId(d.id);
    setNotice('Unsaved annotation; exact Save is required.');
    if (push) chartCtl.current?.update?.(d);
  };
  const edit = (fn) => { if (!selected) return; const d = structuredClone(selected); fn(d); stage(d); };
  const newDrawing = (pts) => {
    const d = { id: crypto.randomUUID(), revision: 0, kind: newKind, scope: drawingScope(h), points: pts, text: '', style: { color: '#4dabf7', width: 2 }, deleted: false };
    stage(d); chartCtl.current?.add?.(d); chartCtl.current?.select?.(d.id);
  };
  const saveDrawing = (remove) => drawAction.run(async () => {
    if (!selected || !ws) return;
    const d = structuredClone(selected);
    if (remove) d.deleted = true;
    await api('/api/workspace', { expected_revision: ws.revision, changes: { drawings: { [d.id]: d } } });
    if (remove) chartCtl.current?.remove?.(d.id);
    await refresh({fresh: true});
    setDrafts((p) => { const n = { ...p }; delete n[d.id]; return n; });
    setNotice(remove ? 'Removal saved as a tombstone revision.' : 'Annotation revision saved.');
  });
  const requestAlert = () => drawAction.run(async () => {
    const d = savedDrawings[selId];
    if (!d || drafts[d.id] || d.deleted || d.kind === 'text') throw new Error('Save a numeric annotation revision first.');
    const record = await api('/api/attention');
    const option = record.drawing_options?.find((o) => o.drawing_ref.drawing_id === d.id && o.drawing_ref.revision === d.revision);
    if (!option) throw new Error('This exact saved drawing revision is not eligible for a numeric alert. No latest geometry was substituted.');
    const payload = { kind: 'drawing-alert', option, drawing_ref: option.drawing_ref, symbol, context: scope.context, timeframe: scope.timeframe, history_key: h.key || '', run_id: h.run_id || '' };
    if (onDrawingAlert) onDrawingAlert(payload); else navigate('alerts', payload);
  });
  const handlers = {
    select: (t) => { setSelTime(t); onSelectBar?.(t); },
    drawingSelect: (id) => setSelId(id || ''),
    drawingChange: (d) => stage(d, false),
    drawingPoint: (p) => {
      if (!live.current.tool) return;
      points.current.push(p);
      if (points.current.length === (live.current.tool === 'trend-line' ? 2 : 1)) { newDrawing(points.current); points.current = []; setTool(null); setPlaced(0); } else setPlaced(points.current.length);
    },
    drawingStatus: setStatuses,
    error: setChartError,
  };
  const live = useRef({});
  live.current = { tool };

  /* Chart copy: review is a read; the host applies the reviewed value explicitly. */
  const copyField = PRICE_FIELD[priceKind];
  const copyCurrency = h?.currency || h?.source?.currency;
  const copyUsable = !!copyTarget && !!bar && typeof bar.raw?.[copyField] === 'string' && copyCurrency === 'USD' && copyTarget.instrumentId && h?.source?.sha256 && h?.derivation_identity && copyTarget.symbol === symbol;
  const copyKey = [pin && JSON.stringify(pin), bar?.t, priceKind, destination, JSON.stringify(copyTarget?.terms), copyTarget?.expectedRevision, deskIdentity(state)].join('|');
  const reviewCopy = () => action.run(async () => {
    const origin = derivedOrigin && derivedOrigin.time === bar.t && samePin(derivedOrigin.pin, pin) ? derivedOrigin.reference : undefined;
    const ref = {
      pin, bar_time: bar.t, value_kind: priceKind, raw_value: String(bar.raw[copyField]), approximate: false,
      ...(origin ? { derived_origin: origin } : {}), currency: copyCurrency, instrument: copyTarget.instrumentId, destination,
    };
    const r = await api('/api/investor', { action: 'chart_copy', terms: structuredClone(copyTarget.terms), price_ref: ref, expected_revision: copyTarget.expectedRevision });
    setCopyReview({ key: copyKey, response: r.chart_copy });
  });

  const openSource = ({ chart, time, reference }) => {
    const p = chartPin(chart);
    if (!p || chart.symbol !== symbol) return;
    if (p.context === 'saved' && saved?.run_id !== chart.run_id) { action.setError('This raw source is not the latest retained research for this stock.'); return; }
    setDerivedOrigin(reference ? { pin: p, time, reference } : null);
    setMode(p.context); if (p.context === 'current') { setTimeframe(chart.timeframe); setCacheKey(chart.key); }
    setCompareKey(''); setRange('all'); setSelTime(time); setCopyReview(null);
  };

  const dayFields = (label, key) => <TextField size="small" type="date" label={label} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} slotProps={{ inputLabel: { shrink: true } }} />;
  const cmpOptions = allEntries.filter((e) => e.key !== h?.key && e.timeframe === timeframe);

  return (
    <Section title="Chart evidence">
      {action.error && <Alert severity="error" sx={{ mb: 1 }} onClose={() => action.setError('')}>{action.error}</Alert>}
      {missing.length > 0 && <Alert severity="error" sx={{ mb: 1 }}>Chart unavailable: missing {missing.join(', ')}. No substitute chart is drawn.</Alert>}
      {chartError && <Alert severity="error" sx={{ mb: 1 }}>{chartError}</Alert>}
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
        <TextField size="small" select label="Context" value={mode} onChange={(e) => { setMode(e.target.value); setCompareKey(''); setCopyReview(null); }} sx={{ minWidth: 220 }}>
          <MenuItem value="saved" disabled={!saved?.run_id}>Saved research inputs</MenuItem>
          <MenuItem value="current">Current-market cache (IEX)</MenuItem>
        </TextField>
        {mode === 'current' && <>
          <TextField size="small" select label="Interval" value={timeframe} onChange={(e) => { setTimeframe(e.target.value); setCacheKey(''); setCompareKey(''); }}>
            {TIMEFRAMES.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
          </TextField>
          <TextField size="small" select label="Retained cache" value={cacheKey} onChange={(e) => setCacheKey(e.target.value)} sx={{ minWidth: 260 }}>
            <MenuItem value="">Latest retained</MenuItem>
            {entries.map((e) => <MenuItem key={e.key} value={e.key}>{e.start} to {e.end} · {e.adjustment} · {e.captured_at}</MenuItem>)}
          </TextField>
          <TextField size="small" select label="Compare close index with" value={compareKey} onChange={(e) => { setCompareKey(e.target.value); setAnchor(null); }} sx={{ minWidth: 260 }}>
            <MenuItem value="">No comparison</MenuItem>
            {cmpOptions.map((e) => <MenuItem key={e.key} value={e.key}>{e.symbol} · {e.start} to {e.end} · {e.adjustment}</MenuItem>)}
          </TextField>
        </>}
        <TextField size="small" select label="Range" value={range} onChange={(e) => { setRange(e.target.value); setCopyReview(null); }}>
          {RANGES.map(([v, l]) => <MenuItem key={v} value={v}>{l}</MenuItem>)}
        </TextField>
      </Stack>
      {view.error && <Alert severity="warning" sx={{ mb: 1 }}>Comparison unavailable: {view.error}</Alert>}
      {view.comparison && <Box sx={{ mb: 1 }}>
        <TextField size="small" select label="Common anchor" value={view.comparison.anchor} onChange={(e) => setAnchor(isDaily(tf) ? e.target.value : Number(e.target.value))} sx={{ minWidth: 220 }}>
          {view.comparison.anchors.map((t) => <MenuItem key={t} value={t}>{fmtTime(t, tf)}</MenuItem>)}
        </TextField>
        <Typography variant="body2">{view.comparison.meaning}</Typography>
        {view.comparison.series.map((item) => {
          const p = item.points.find((x) => String(x.time) === String(bar?.t));
          return <Typography key={item.symbol} variant="body2">{item.symbol} source close / index: {text(p?.source_close)} / {text(p?.value)} · anchor close {text(item.anchor_close)} · unmatched bars excluded {text(item.excluded)}</Typography>;
        })}
        {other && <Evidence title="Comparison source artifact" data={other.source} />}
      </Box>}
      {view.bars.length > 0 && missing.length === 0 && scope ? (
        <MarketChartCanvas bars={view.bars} indicators={indicators} timeframe={tf} comparison={view.comparison}
          mountKey={`${h.context}:${h.key || h.run_id}:${range}:${compareKey}`} scope={scope} drawings={paneDrawings}
          selectedId={selId} tool={comparing ? null : tool} handlers={handlers} ctlRef={chartCtl} />
      ) : <Typography>{h ? 'No bars retained for this selection. Missing evidence is not fetched.' : 'No chart loaded.'}</Typography>}
      {h && <Typography variant="caption" component="p">
        {h.context === 'current' ? `Current data cache ${h.key}` : `Run ${h.run_id} · research date ${text(h.research_date)}`} · {text(h.price_basis)} · {all?.length ?? 0} bars · captured {dateTime(h.captured_at)}.
        TradingView Lightweight Charts™ · © 2025 TradingView, Inc.
      </Typography>}
      {h?.problems?.map((p) => <Alert key={p} severity="warning" sx={{ mt: 1 }}>{p}</Alert>)}

      {bar && <Box sx={{ mt: 1 }}>
        <Autocomplete size="small" disableClearable options={view.bars.map((b) => String(b.t))} value={String(bar.t)} sx={{ maxWidth: 320, mb: 1 }}
          getOptionLabel={(t) => fmtTime(isDaily(tf) ? t : Number(t), tf)}
          onChange={(_, t) => { const b = view.bars.find((x) => String(x.t) === t); handlers.select(b?.t ?? null); setCopyReview(null); }}
          renderInput={(p) => <TextField {...p} label={isDaily(tf) ? 'Recorded business day' : 'Recorded bar time'} />} />
        <Typography>O {rawOf(bar, 'o')} · H {rawOf(bar, 'h')} · L {rawOf(bar, 'l')} · C {rawOf(bar, 'c')} · V {rawOf(bar, 'v')}</Typography>
        <Typography variant="body2">Prior saved close {rawOf(prior, 'c')} · {prior ? fmtTime(prior.t, tf) : 'No prior bar recorded'} · close-to-close {pct(movement)}. This compares recorded closes, not the live last trade.</Typography>
        <Evidence title="OHLCV source artifact" data={h?.source} />
      </Box>}

      <Typography variant="subtitle2" sx={{ mt: 2 }}>Recorded indicators · {bar ? fmtTime(bar.t, tf) : 'no selected date'}</Typography>
      {indicators.length ? indicators.map((i) => {
        const p = i.points?.find((x) => String(x.t) === String(bar?.t));
        return (
          <Stack key={i.name} direction="row" spacing={1}  sx={{alignItems: "center"}}>
            <Typography sx={{ flex: 1 }}>{i.name} · {text(p?.raw ?? p?.value ?? 'Not recorded for this date')} · window {text(i.window_start)} to {text(i.window_end)}</Typography>
            <Button size="small" onClick={() => navigate('alerts', { kind: 'indicator-alert', indicator: i.name, symbol, context: h.context === 'current' ? 'current' : 'research', timeframe: h.timeframe || '1Day', history_key: h.context === 'current' ? h.key : '', run_id: h.run_id || '' })}>Prepare indicator alert</Button>
          </Stack>);
      }) : <Typography variant="body2">No recorded indicators. Missing values are not zero.</Typography>}
      {h?.claims?.length > 0 && <Box sx={{ mt: 1 }}>
        <Typography variant="subtitle2">Claims attributed to the saved market report</Typography>
        {h.claims.map((c, i) => <Box key={i}><Typography component="blockquote" sx={{ m: 0, pl: 1, fontStyle: 'italic' }}>{typeof c === 'string' ? c : text(c.text)}</Typography><Evidence title="Claim attribution" data={c} /></Box>)}
      </Box>}

      {copyTarget && bar && <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2">Prepare a manual ticket from an exact historical price</Typography>
        <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  my: 1 }}>
          <TextField size="small" select label="Recorded value" value={priceKind} onChange={(e) => { setPriceKind(e.target.value); setCopyReview(null); }}>
            {Object.keys(PRICE_FIELD).map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
          </TextField>
          <TextField size="small" select label="Compatible ticket field" value={destination} sx={{ minWidth: 240 }} onChange={(e) => { setDestination(e.target.value); setCopyReview(null); }}>
            {(copyTarget.fields || []).map(([k, l]) => <MenuItem key={k} value={k}>{l}</MenuItem>)}
          </TextField>
          <Button variant="outlined" disabled={action.busy || !copyUsable || !(copyTarget.fields || []).some(([k]) => k === destination)} onClick={reviewCopy}>Review price normalization</Button>
        </Stack>
        <Typography variant="body2">Exact {priceKind} {rawOf(bar, copyField)} · {text(copyCurrency)} · bar {text(bar.t)}. Historical selection; it does not imply execution.{!copyUsable && ' Copy unavailable: exact source currency, instrument, price evidence or ticket symbol is missing.'}</Typography>
        {copyReview && (copyReview.key === copyKey ? <Box>
          <Typography>Raw {text(copyReview.response.raw_value)} → normalized {text(copyReview.response.value)} · increment {text(copyReview.response.increment)} · {copyReview.response.rounded ? 'rounded' : 'unchanged'}</Typography>
          <Evidence title="Reviewed price reference" data={copyReview.response} />
          <Button variant="contained" onClick={() => { copyTarget.onApply?.(copyReview.response, { symbol }); setCopyReview(null); }}>Copy reviewed historical price into ticket</Button>
        </Box> : <Alert severity="warning">The ticket, bar or source changed since this review. Review again.</Alert>)}
      </Box>}

      {h && scope && <Accordion disableGutters sx={{ mt: 2 }}>
        <AccordionSummary><Typography>Price annotations · {text(scope.currency || 'Currency unverified')}</Typography></AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2">Scope {scope.symbol} / {scope.timeframe} / {scope.context} / {scope.feed || 'feed unknown'} / {scope.adjustment || 'adjustment unknown'}. {comparing ? 'Price drawings are unavailable on the indexed comparison.' : 'Pointer coordinates are manual approximations; exact observed anchors need the retained OHLC action.'} Saving an annotation starts no alert.</Typography>
          {drawAction.error && <Alert severity="error" sx={{ my: 1 }}>{drawAction.error}</Alert>}
          <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  my: 1 }}>
            <TextField size="small" select label="New annotation" value={newKind} onChange={(e) => { setNewKind(e.target.value); setTool(null); points.current = []; setPlaced(0); }}>
              {DRAWING_KINDS.map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
            </TextField>
            <Button variant="outlined" onClick={() => { const p = { basis: 'manual_time', time: bar?.t, price: '' }; newDrawing(Array.from({ length: newKind === 'trend-line' ? 2 : 1 }, () => ({ ...p }))); }}>Create numeric draft</Button>
            <Button variant="outlined" disabled={comparing} onClick={() => { points.current = []; setPlaced(0); setTool(tool ? null : newKind); }}>{tool ? 'Stop pointer placement' : 'Place with pointer'}</Button>
            <TextField size="small" select label="Annotations and drafts" value={selected ? selected.id : ''} sx={{ minWidth: 280 }} onChange={(e) => { setSelId(e.target.value); chartCtl.current?.select?.(e.target.value); }}>
              <MenuItem value="">Choose annotation</MenuItem>
              {paneDrawings.map((d) => <MenuItem key={d.id} value={d.id}>{d.kind} · {d.id.slice(0, 8)} · revision {d.revision}{drafts[d.id] ? ' · unsaved' : ''}</MenuItem>)}
            </TextField>
          </Stack>
          <Typography variant="caption" component="p">Pointer: {tool ? `${tool} · ${placed} anchor(s) placed` : 'Off'}. Delete on the chart stages removal; Escape ends placement.</Typography>
          {selected ? <Box>
            <Evidence title="Original saved scope and current pane" data={{ original: selected.scope, current: scope }} />
            {incompatible && <Alert severity="warning" sx={{ my: 1 }}>Original scope is incompatible with this pane. The annotation stays inspectable and unresolved; no automatic rebind is performed.</Alert>}
            <Typography>{selected.kind} · {selected.deleted ? 'Pending removal; Save confirms the tombstone' : drafts[selected.id] ? 'Unsaved local draft' : `Saved revision ${selected.revision}`}</Typography>
            {selected.points.map((p, i) => (
              <Stack key={i} direction="row" spacing={1}  useFlexGap  sx={{flexWrap: "wrap", alignItems: "center",  my: 1 }}>
                <TextField size="small" select label={`Anchor ${i + 1} basis`} value={p.basis} sx={{ minWidth: 190 }}
                  onChange={(e) => edit((d) => { const q = d.points[i]; d.points[i] = e.target.value === 'logical_offset' ? { basis: 'logical_offset', origin_time: bar?.t, offset: 0, price: q.price } : { basis: 'manual_time', time: q.time ?? q.origin_time, price: q.price }; })}>
                  <MenuItem value="manual_time">Manual time</MenuItem><MenuItem value="logical_offset">Projected bar offset</MenuItem>
                  {p.basis === 'observed' && <MenuItem value="observed">Exact retained OHLC</MenuItem>}
                </TextField>
                {p.basis === 'logical_offset' ? <>
                  <TextField size="small" select label="Actual origin bar" value={p.origin_time ?? ''} sx={{ minWidth: 190 }} onChange={(e) => edit((d) => { d.points[i].origin_time = timeInput(e.target.value, scope.timeframe); })}>
                    {(h.bars || []).map((b) => <MenuItem key={b.t} value={b.t}>{String(b.t)}</MenuItem>)}
                  </TextField>
                  <TextField size="small" label="Signed logical bar offset" value={p.offset ?? ''} onChange={(e) => edit((d) => { d.points[i].offset = e.target.value === '' ? '' : Number(e.target.value); })} />
                </> : <TextField size="small" label={isDaily(scope.timeframe) ? 'Time YYYY-MM-DD' : 'Time UTC epoch seconds'} value={p.time ?? ''}
                  disabled={p.basis === 'observed'} onChange={(e) => edit((d) => { const q = d.points[i]; d.points[i] = q.basis === 'manual_time' ? { ...q, time: timeInput(e.target.value, scope.timeframe) } : q; })} />}
                <TextField size="small" label={`Exact price · ${scope.currency || 'units unverified'}`} value={p.price ?? ''} onChange={(e) => edit((d) => { const q = d.points[i]; d.points[i] = q.basis === 'observed' ? { basis: 'manual_time', time: q.time, price: e.target.value } : { ...q, price: e.target.value }; })} />
                <Button size="small" disabled={comparing || incompatible || !pin || !bar} onClick={() => {
                  const price = bar?.raw?.[valueKind];
                  if (!pin || price == null) { setNotice('Exact retained OHLC provenance is unavailable.'); return; }
                  edit((d) => { d.points[i] = { basis: 'observed', time: bar.t, price: String(price), source_pin: pin, value_kind: valueKind }; });
                }}>Use selected retained {valueKind.toUpperCase()}</Button>
                {p.basis === 'observed' && <Evidence title="Exact observed provenance" data={p} />}
              </Stack>))}
            <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  my: 1 }}>
              <TextField size="small" select label="Retained value for snap" value={valueKind} onChange={(e) => setValueKind(e.target.value)}>
                {[['c', 'Close'], ['o', 'Open'], ['h', 'High'], ['l', 'Low']].map(([k, l]) => <MenuItem key={k} value={k}>{l}</MenuItem>)}
              </TextField>
              <TextField size="small" label="Text" value={selected.text ?? ''} slotProps={{ htmlInput: { maxLength: 500 } }} onChange={(e) => edit((d) => { d.text = e.target.value; })} />
              <TextField size="small" type="color" label="Color" value={selected.style.color} onChange={(e) => edit((d) => { d.style.color = e.target.value; })} slotProps={{ inputLabel: { shrink: true } }} sx={{ width: 90 }} />
              <TextField size="small" select label="Line width" value={selected.style.width} onChange={(e) => edit((d) => { d.style.width = Number(e.target.value); })}>
                {[1, 2, 3, 4].map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
              </TextField>
            </Stack>
            <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap"}}>
              <Button variant="contained" disabled={drawAction.busy || !ws} onClick={() => saveDrawing(false)}>Save exact annotation revision</Button>
              <Button color="error" disabled={drawAction.busy || !ws} onClick={() => saveDrawing(true)}>Remove annotation and save tombstone</Button>
              <Button disabled={SCOPE_KEYS.some((k) => !scope[k]) || comparing} onClick={() => { edit((d) => { d.scope = structuredClone(scope); }); setNotice('Explicit source-scope rebind staged. Save a new annotation revision; alerts need a separate explicit rebind.'); }}>Stage rebind to this retained source scope</Button>
              <Button disabled={drawAction.busy || !!drafts[selected.id] || selected.deleted || selected.kind === 'text' || incompatible || comparing} onClick={requestAlert}>Create alert from this saved geometry</Button>
              <Button onClick={() => {
                const sv = savedDrawings[selId];
                setDrafts((p) => { const n = { ...p }; delete n[selId]; return n; });
                if (sv && !sv.deleted) chartCtl.current?.update?.(sv); else chartCtl.current?.remove?.(selId);
                setNotice('Reopened saved annotation; local edits discarded.');
              }}>Discard local edits</Button>
            </Stack>
          </Box> : <Typography variant="body2">Select or create an annotation to edit its anchors.</Typography>}
          <Typography role="status" variant="body2" sx={{ mt: 1 }}>{notice || 'Annotations are saved only with an explicit Save or Remove action.'}</Typography>
          <Evidence title="Unresolved annotation coordinates" data={statuses} />
        </AccordionDetails>
      </Accordion>}

      {h && pin && <Box sx={{ mt: 2 }}><ChartAnalysis key={JSON.stringify(pin)} h={h} pin={pin} desk={desk} onOpenSource={openSource} /></Box>}

      {mode === 'current' && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2">Request data (explicit)</Typography>
          <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  my: 1 }}>
            {dayFields('Start', 'start')}{dayFields('End', 'end')}{dayFields('Symbol as-of (NY)', 'asof')}
            <TextField size="small" select label="Adjustment" value={form.adjustment} sx={{ minWidth: 130 }} onChange={(e) => setForm({ ...form, adjustment: e.target.value })}>
              {['raw', 'split', 'dividend', 'all'].map((a) => <MenuItem key={a} value={a}>{a}</MenuItem>)}
            </TextField>
            <Button variant="outlined" disabled={action.busy || !form.start || !form.end || !form.adjustment}
              onClick={() => post({ action: 'start', symbols: [symbol], ...form, timeframe })}>Request this stock&apos;s range</Button>
            <Button variant="outlined" disabled={action.busy || !form.start || !form.end || !form.adjustment}
              onClick={() => post({ action: 'start', symbols: (copyTarget?.requestSymbols || universeOf(state)), ...form, timeframe })}>Request selected list</Button>
            <Button variant="outlined" disabled={action.busy} onClick={() => post({ action: 'baseline', symbols: [symbol], ...form, timeframe })}>Get 252 daily bars</Button>
          </Stack>
          {jobs.map((j) => (
            <Stack key={j.id} direction="row" spacing={1}  sx={{alignItems: "center"}}>
              <Typography>{j.status} · {j.request?.timeframe || 'legacy'} · {String(j.id).slice(0, 8)}</Typography>
              {['queued', 'running', 'cancelling'].includes(j.status) && <Button size="small" onClick={() => post({ action: 'cancel', id: j.id })}>Stop future requests</Button>}
              {['interrupted', 'canceled', 'failed', 'completed_with_gaps'].includes(j.status) && <Button size="small" onClick={() => post({ action: 'resume', id: j.id })}>Resume unfinished</Button>}
            </Stack>
          ))}
        </Box>
      )}
    </Section>
  );
}

/**
 * Plain retained-bar candlestick renderer (LightweightCharts via ref). Draws only the bars it is given.
 * Props: symbol, bars [{t|time, o|open, h|high, l|low, c|close}], period (days to show; omitted/'all' = every bar).
 * Missing library or empty bars is reported explicitly; nothing is fetched, collected or calculated.
 */
export function StockChart({ symbol, bars, period }) {
  const host = useRef(null);
  const L = window.LightweightCharts;
  const data = useMemo(() => {
    const rows = (bars || []).map((b) => ({
      time: b.time ?? b.t, open: Number(b.open ?? b.o ?? b.raw?.o), high: Number(b.high ?? b.h ?? b.raw?.h),
      low: Number(b.low ?? b.l ?? b.raw?.l), close: Number(b.close ?? b.c ?? b.raw?.c),
    })).filter((r) => r.time != null && [r.open, r.high, r.low, r.close].every(Number.isFinite));
    const days = Number(period);
    if (!rows.length || !Number.isFinite(days) || days <= 0) return rows;
    const ms = (t) => (typeof t === 'number' ? t * 1000 : Date.parse(`${t}T00:00:00Z`));
    const cut = ms(rows.at(-1).time) - days * 86400000;
    return rows.filter((r) => ms(r.time) >= cut);
  }, [bars, period]);
  useEffect(() => {
    const el = host.current;
    if (!el || !L || !data.length) return undefined;
    const cs = getComputedStyle(el);
    const chart = L.createChart(el, {
      autoSize: true, height: 320,
      layout: { background: { color: 'transparent' }, textColor: cs.color },
      grid: { vertLines: { color: 'rgba(128,128,128,.15)' }, horzLines: { color: 'rgba(128,128,128,.15)' } },
      timeScale: { timeVisible: typeof data[0].time === 'number' },
    });
    const series = L.CandlestickSeries ? chart.addSeries(L.CandlestickSeries, {}) : chart.addCandlestickSeries();
    series.setData(data);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [L, data]);
  if (!L) return <Alert severity="error">Chart unavailable: LightweightCharts is not loaded.</Alert>;
  if (!data.length) return <Typography>{symbol ? `${symbol}: ` : ''}No retained bars available. Nothing is fetched or estimated here.</Typography>;
  return <Box ref={host} role="img" aria-label={`${symbol || 'Stock'} price chart`} sx={{ height: 320, width: '100%' }} />;
}
/* ------------------------------------------------------------------ Markets */

const COLUMN_OPTIONS = [
  ['price', 'Last price'], ['change', 'Change'], ['age', 'Quote age'], ['research', 'Research'], ['bidask', 'Bid / ask size'], ['spread', 'Spread bps'],
  ['position', 'Position'], ['upl', 'Unrealized P/L'], ['working', 'Working orders'], ['savedOpen', 'Saved open'], ['savedHigh', 'Saved high'],
  ['savedLow', 'Saved low'], ['savedClose', 'Saved close'], ['savedVolume', 'Saved volume'],
];
const DEFAULT_COLUMNS = ['price', 'change', 'age', 'research'];
const CORE_COLUMNS = ['price', 'change', 'bidask', 'spread', 'position', 'upl', 'working', 'research'];
const TERMINAL = ['filled', 'canceled', 'cancelled', 'expired', 'rejected', 'replaced'];
const symbolList = (t) => t.split(/[\s,]+/).map((s) => s.toUpperCase()).filter(Boolean);

function useDiscoveryMeta(desk) {
  const { api, page } = desk;
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (page !== 'markets') return undefined;
    const ctl = new AbortController();
    api('/api/discovery', undefined, { signal: ctl.signal }).then((r) => { setMeta(r); setError(''); })
      .catch((e) => { if (!ctl.signal.aborted) setError(errMessage(e)); });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, tick]);
  return { meta, error, reload: useCallback(() => setTick((n) => n + 1), []) };
}

function Watchlists({ desk, target, setTarget, checked }) {
  const { state, api, refresh } = desk;
  const ws = state?.workspace;
  const lists = ws?.data?.watchlists || [];
  const [name, setName] = useState('');
  const [rename, setRename] = useState('');
  const action = useAsyncAction();
  const current = lists.find((l) => l.id === target);
  const save = (next) => action.run(async () => {
    await api('/api/workspace', { expected_revision: ws.revision, changes: { watchlists: next } });
    await refresh({fresh: true});
  });
  const picked = [...checked];
  const createFromSelected = async () => {
    const n = name.trim().slice(0, 60);
    if (!n || lists.some((l) => l.name.toLowerCase() === n.toLowerCase())) { action.setError('Enter a unique list name.'); return; }
    if (lists.length >= 100) { action.setError('At most 100 lists.'); return; }
    const id = crypto.randomUUID();
    await save([...lists, { id, name: n, symbols: picked }]);
    setTarget(id); setName('');
  };
  const edit = (fn) => save(lists.map((l) => (l.id === target ? { ...l, symbols: fn(l.symbols) } : l)));
  return (
    <Section title="Saved lists">
      {action.error && <Alert severity="error" onClose={() => action.setError('')}>{action.error}</Alert>}
      <Stack direction="row" spacing={1}  useFlexGap  sx={{flexWrap: "wrap", alignItems: "center"}}>
        <TextField size="small" select label="Target list" value={current ? target : ''} sx={{ minWidth: 200 }} onChange={(e) => setTarget(e.target.value)}>
          {lists.map((l) => <MenuItem key={l.id} value={l.id}>{l.name} · {l.symbols.length}</MenuItem>)}
        </TextField>
        <Button variant="outlined" disabled={action.busy || !current || !picked.length} onClick={() => edit((s) => [...new Set([...s, ...picked])])}>Add {picked.length} checked</Button>
        <Button variant="outlined" disabled={action.busy || !current || !picked.length} onClick={() => edit((s) => s.filter((x) => !picked.includes(x)))}>Remove {picked.length} checked</Button>
        <Button color="error" disabled={action.busy || !current || lists.length <= 1 || target === 'shortlist'} onClick={() => save(lists.filter((l) => l.id !== target))}>Delete list</Button>
      </Stack>
      {current && <Typography variant="body2" sx={{ my: 1 }}>{current.symbols.join(', ') || 'No symbols.'}</Typography>}
      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
        <TextField size="small" label="Rename target list" value={rename} onChange={(e) => setRename(e.target.value)} />
        <Button disabled={action.busy || !current || !rename.trim()} onClick={() => save(lists.map((l) => (l.id === target ? { ...l, name: rename.trim().slice(0, 60) } : l))).then(() => setRename(''))}>Rename</Button>
      </Stack>
      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
        <TextField size="small" label="New list name" value={name} onChange={(e) => setName(e.target.value)} />
        <Button variant="outlined" disabled={action.busy || !ws} onClick={createFromSelected}>Create from {picked.length} checked</Button>
      </Stack>
    </Section>
  );
}

function ColumnPicker({ desk, cols, setCols }) {
  const { state, api, refresh } = desk;
  const ws = state?.workspace;
  const action = useAsyncAction();
  const order = cols.order;
  const move = (i, d) => setCols((c) => { const o = [...c.order]; const j = i + d; if (j < 0 || j >= o.length) return c; [o[i], o[j]] = [o[j], o[i]]; return { ...c, order: o }; });
  const save = () => action.run(async () => {
    await api('/api/workspace', { expected_revision: ws.revision, changes: { preferences: { columns: { order, visible: cols.visible } } } });
    await refresh({fresh: true});
  });
  return (
    <Accordion disableGutters>
      <AccordionSummary><Typography>Columns</Typography></AccordionSummary>
      <AccordionDetails>
        {action.error && <Alert severity="error">{action.error}</Alert>}
        {order.map((k, i) => (
          <Stack key={k} direction="row"  sx={{alignItems: "center"}}>
            <FormControlLabel sx={{ flex: 1 }} label={COLUMN_OPTIONS.find(([id]) => id === k)?.[1] || k}
              control={<Checkbox checked={cols.visible.includes(k)} onChange={(e) => setCols((c) => ({ ...c, visible: e.target.checked ? [...c.visible, k] : c.visible.filter((x) => x !== k) }))} />} />
            <Button size="small" disabled={i === 0} onClick={() => move(i, -1)}>Up</Button>
            <Button size="small" disabled={i === order.length - 1} onClick={() => move(i, 1)}>Down</Button>
          </Stack>))}
        <Button variant="outlined" disabled={action.busy || !ws} onClick={save}>Save column layout</Button>
      </AccordionDetails>
    </Accordion>
  );
}

function Notes({ symbol, desk }) {
  const { state, api, refresh } = desk;
  const ws = state?.workspace;
  const [draft, setDraft] = useState({});
  const action = useAsyncAction();
  const savedText = ws?.data?.notes?.[symbol]?.text ?? '';
  const value = draft[symbol] ?? savedText;
  const save = () => action.run(async () => {
    await api('/api/workspace', { expected_revision: ws.revision, changes: { notes: { [symbol]: { text: value } } } });
    setDraft((d) => { const n = { ...d }; delete n[symbol]; return n; });
    await refresh({fresh: true});
  });
  return (
    <Section title="Notes" actions={<Button disabled={action.busy || !ws || value === savedText} onClick={save}>Save note</Button>}>
      {action.error && <Alert severity="error">{action.error}</Alert>}
      <TextField multiline minRows={3} fullWidth value={value} slotProps={{ htmlInput: { maxLength: 20000 } }}
        onChange={(e) => setDraft({ ...draft, [symbol]: e.target.value })} />
    </Section>
  );
}

const BLANK_CRIT = { min_price: '', max_price: '', min_market_cap: '', min_volume: '', sector: '', sort: 'ticker', ascending: true };

function Screener({ desk, discovery, target }) {
  const { state, api, refresh } = desk;
  const { meta, reload } = discovery;
  const ws = state?.workspace;
  const [crit, setCrit] = useState(BLANK_CRIT);
  const [obs, setObs] = useState(null);
  const [pick, setPick] = useState('');
  const [inspected, setInspected] = useState(null);
  const [saveName, setSaveName] = useState('');
  const [savedId, setSavedId] = useState('');
  const action = useAsyncAction();
  const screens = ws?.data?.saved_screens || [];
  const lists = ws?.data?.watchlists || [];
  const universe = universeOf(state);

  const criteria = () => {
    const c = { sort: crit.sort, ascending: crit.ascending };
    ['min_price', 'max_price', 'min_market_cap', 'min_volume'].forEach((k) => {
      if (crit[k] === '') return;
      if (!(Number(crit[k]) >= 0)) throw new Error('Numeric criteria must be nonnegative.');
      c[k] = Number(crit[k]);
    });
    if (crit.sector) c.sector = crit.sector;
    return c;
  };
  const screen = (offset = 0) => action.run(async () => { setObs(await api('/api/discovery', { criteria: criteria(), offset })); setInspected(null); });
  const add = () => action.run(async () => {
    await api('/api/discovery', { action: 'add_to_universe', observation_id: obs.id, symbol: pick, config_revision: state.config_revision });
    await refresh({fresh: true});
  });
  const addToList = () => action.run(async () => {
    const list = lists.find((l) => l.id === target);
    if (!list) throw new Error('Choose a target watchlist in the Universe tab.');
    const next = lists.map((l) => (l.id === target ? { ...l, symbols: [...new Set([...l.symbols, pick])] } : l));
    await api('/api/workspace', { expected_revision: ws.revision, changes: { watchlists: next } });
    await refresh({fresh: true});
  });
  const inspect = (symbol) => action.run(async () => {
    const q = obs ? `observation=${encodeURIComponent(obs.id)}&symbol=${encodeURIComponent(symbol)}` : `symbol=${encodeURIComponent(symbol)}`;
    setInspected(await api(`/api/discovery?${q}`));
  });
  const saveCriteria = () => action.run(async () => {
    const n = saveName.trim().slice(0, 60);
    if (!n) throw new Error('Name the criteria.');
    const same = screens.find((s) => s.name === n);
    const item = { id: same?.id || crypto.randomUUID(), name: n, criteria: criteria() };
    await api('/api/workspace', { expected_revision: ws.revision, changes: { saved_screens: [...screens.filter((s) => s !== same), item] } });
    await refresh({fresh: true}); setSavedId(item.id);
  });
  const load = () => {
    const s = screens.find((x) => x.id === savedId);
    if (!s) return;
    setCrit({ ...BLANK_CRIT, ...Object.fromEntries(Object.entries(s.criteria).map(([k, v]) => [k, typeof v === 'number' ? String(v) : v])) });
    setSaveName(s.name);
  };
  const columns = [
    { id: 'symbol', label: 'Symbol', render: (r) => r.symbol },
    { id: 'name', label: 'Name', render: (r) => r.shortName || r.longName || UNAVAILABLE },
    { id: 'price', label: 'Price', numeric: true, render: (r) => money(r.regularMarketPrice) },
    { id: 'chg', label: 'Change', numeric: true, render: (r) => pct(r.regularMarketChangePercent) },
    { id: 'vol', label: 'Volume', numeric: true, render: (r) => count(r.regularMarketVolume) },
    { id: 'cap', label: 'Market cap', numeric: true, render: (r) => count(r.marketCap) },
  ];
  const nextDisabled = !obs || obs.status !== 'completed' || !(obs.rows || []).length || (obs.total != null && obs.offset + obs.rows.length >= obs.total);
  const row = inspected?.row || inspected?.observation?.row || inspected;
  return (
    <Section title="Yahoo screener" actions={<Button variant="contained" disabled={action.busy} onClick={() => screen(0)}>Run screen</Button>}>
      {action.error && <Alert severity="error" onClose={() => action.setError('')}>{action.error}</Alert>}
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
        {[['min_price', 'Min price'], ['max_price', 'Max price'], ['min_market_cap', 'Min market cap'], ['min_volume', 'Min avg volume']].map(([k, l]) => (
          <TextField key={k} size="small" type="number" label={l} value={crit[k]} onChange={(e) => setCrit({ ...crit, [k]: e.target.value })} slotProps={{ htmlInput: { min: 0 } }} />))}
        <TextField size="small" select label="Sector" value={crit.sector} sx={{ minWidth: 160 }} onChange={(e) => setCrit({ ...crit, sector: e.target.value })}>
          <MenuItem value="">Any</MenuItem>
          {(meta?.sectors || []).map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
        </TextField>
        <TextField size="small" select label="Sort" value={crit.sort} onChange={(e) => setCrit({ ...crit, sort: e.target.value })}>
          {(meta?.sorts || ['ticker']).map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
        </TextField>
        <FormControlLabel control={<Checkbox checked={crit.ascending} onChange={(e) => setCrit({ ...crit, ascending: e.target.checked })} />} label="Ascending" />
      </Stack>
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
        <TextField size="small" select label="Saved criteria" value={savedId} sx={{ minWidth: 200 }} onChange={(e) => setSavedId(e.target.value)}>
          <MenuItem value="">None</MenuItem>
          {screens.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
        </TextField>
        <Button disabled={!savedId} onClick={load}>Load (replace draft)</Button>
        <TextField size="small" label="Name" value={saveName} onChange={(e) => setSaveName(e.target.value)} />
        <Button variant="outlined" disabled={action.busy || !ws || !saveName.trim()} onClick={saveCriteria}>Save as named criteria</Button>
      </Stack>
      {obs?.status === 'failed' && <Alert severity="error">{obs.error}</Alert>}
      {obs && obs.status !== 'failed' && <>
        <DataTable rows={obs.rows || []} columns={columns} getRowId={(r) => r.symbol} onRowClick={(r) => setPick(r.symbol)} selectedIds={pick ? [pick] : []} empty="No rows on this page." />
        <Typography variant="caption">{obs.limitation} · {text(obs.provider)} · captured {dateTime(obs.captured_at)} · total {count(obs.total)}</Typography>
        <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mt: 1 }}>
          <Button disabled={action.busy || obs.offset === 0} onClick={() => screen(Math.max(0, obs.offset - (obs.page_size || 25)))}>Previous</Button>
          <Button disabled={action.busy || nextDisabled} onClick={() => screen(obs.offset + (obs.page_size || 25))}>Next</Button>
          <Button disabled={!pick || action.busy} onClick={() => inspect(pick)}>Inspect {pick || 'selected'}</Button>
          <Button variant="outlined" disabled={!pick || action.busy || state?.browse_only || obs.status !== 'completed' || universe.includes(pick) || !SYMBOL.test(pick)} onClick={add}>Add {pick || 'selected'} to universe</Button>
          <Button variant="outlined" disabled={!pick || action.busy || !SYMBOL.test(pick)} onClick={addToList}>Add to target watchlist</Button>
        </Stack>
      </>}
      {inspected && <Box sx={{ mt: 1 }}>
        <Typography>{text(row?.longName || row?.shortName)} · {money(row?.regularMarketPrice)} · {pct(row?.regularMarketChangePercent)} · cap {count(row?.marketCap)} · volume {count(row?.regularMarketVolume)} · 3-month avg {count(row?.averageDailyVolume3Month)} · {text(row?.currency)} {text(row?.fullExchangeName || row?.exchange)}</Typography>
        <Evidence title="Provider observation" data={inspected} />
      </Box>}
      {meta == null && <Button onClick={reload}>Load screener options</Button>}
    </Section>
  );
}

function Options({ desk, discovery }) {
  const { state, api, refresh } = desk;
  const { meta, reload } = discovery;
  const options = meta?.options;
  const [query, setQuery] = useState('{"status":"active","limit":25}');
  const [obsId, setObsId] = useState('');
  const [expiry, setExpiry] = useState('');
  const [type, setType] = useState('');
  const [feed, setFeed] = useState('');
  const action = useAsyncAction();
  const obs = options?.observations?.[obsId] || Object.values(options?.observations || {}).at(-1);
  const selections = Object.values(options?.selections || {});
  const idn = deskIdentity(state);
  const guarded = (fn) => action.run(async () => {
    const before = idn;
    await fn();
    if (before !== deskIdentity(desk.state)) throw new Error('Desk connection changed during this request; review the result before continuing.');
    reload();
  });
  const fetchContracts = () => guarded(async () => {
    const r = await api('/api/discovery', { action: 'option_contracts', query: JSON.parse(query) });
    if (r.option_observation?.id) setObsId(r.option_observation.id);
  });
  const select = (symbol) => guarded(async () => {
    if (!feed) throw new Error('Choose an explicit option feed first.');
    await api('/api/discovery', { action: 'option_select', observation_id: obs.id, symbol, feed, expected_revision: options.revision });
    await refresh({fresh: true});
  });
  const applyFeed = () => guarded(async () => {
    if (!feed) throw new Error('Choose an explicit option feed first.');
    await api('/api/discovery', { action: 'option_feed', feed, expected_revision: options.revision });
    await refresh({fresh: true});
  });
  const contracts = (obs?.contracts || []).map((c) => c.raw).filter((r) => (!expiry || r.expiration_date === expiry) && (!type || r.type === type));
  const expiries = [...new Set((obs?.contracts || []).map((c) => c.raw.expiration_date))].sort();
  const quoteOf = (s) => state?.nautilus?.market_data?.[s]?.quote;
  const columns = [
    { id: 'symbol', label: 'Contract', render: (r) => r.symbol },
    { id: 'type', label: 'Type', render: (r) => r.type },
    { id: 'exp', label: 'Expiry', render: (r) => r.expiration_date },
    { id: 'strike', label: 'Strike', numeric: true, render: (r) => text(r.strike_price) },
    { id: 'quote', label: 'Bid / ask', render: (r) => { const q = quoteOf(r.symbol); return q ? `${money(q.bid_price)} × ${text(q.bid_size)} / ${money(q.ask_price)} × ${text(q.ask_size)}` : UNAVAILABLE; } },
    { id: 'sel', label: '', render: (r) => <Button size="small" disabled={action.busy} onClick={(e) => { e.stopPropagation(); select(r.symbol); }}>{options?.selections?.[r.symbol] ? 'Selected' : 'Select'}</Button> },
  ];
  return (
    <Section title="Option contracts">
      {action.error && <Alert severity="error" onClose={() => action.setError('')}>{action.error}</Alert>}
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
        <TextField size="small" label="Contract query (JSON)" value={query} onChange={(e) => setQuery(e.target.value)} sx={{ minWidth: 300 }} />
        <Button variant="contained" disabled={action.busy} onClick={fetchContracts}>Discover contracts</Button>
        <TextField size="small" select label="Feed" value={feed} sx={{ minWidth: 130 }} onChange={(e) => setFeed(e.target.value)}>
          {['opra', 'indicative'].map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
        </TextField>
        <Button disabled={action.busy || !feed || !selections.length || !options} onClick={applyFeed}>Apply feed to selected</Button>
        <TextField size="small" select label="Expiry" value={expiry} sx={{ minWidth: 140 }} onChange={(e) => setExpiry(e.target.value)}>
          <MenuItem value="">All</MenuItem>{expiries.map((x) => <MenuItem key={x} value={x}>{x}</MenuItem>)}
        </TextField>
        <TextField size="small" select label="Type" value={type} sx={{ minWidth: 100 }} onChange={(e) => setType(e.target.value)}>
          <MenuItem value="">All</MenuItem><MenuItem value="call">Call</MenuItem><MenuItem value="put">Put</MenuItem>
        </TextField>
      </Stack>
      <DataTable rows={contracts} columns={columns} getRowId={(r) => r.symbol} empty="No contracts discovered." />
      <Typography variant="subtitle2" sx={{ mt: 1 }}>Selected contracts</Typography>
      {selections.map((s) => (
        <Stack key={s.symbol} direction="row" spacing={1}  sx={{alignItems: "center"}}>
          <Typography sx={{ flex: 1 }}>{s.symbol} · feed {s.feed} · {state?.nautilus?.market_data?.[s.symbol]?.error || ''}</Typography>
          <Button size="small" onClick={() => desk.navigate('orders', { kind: 'option-ticket', symbol: s.symbol })}>Open manual premium ticket</Button>
        </Stack>))}
      <Button disabled={selections.length < 2 || selections.length > 4} onClick={() => desk.navigate('orders', { kind: 'option-package', symbols: selections.map((s) => s.symbol) })}>Prepare atomic package (2–4 contracts)</Button>
      {obs && <Evidence title="Contract discovery observation" data={{ id: obs.id, received_at: obs.received_at, next_page_token: obs.next_page_token, query: obs.query, artifact: obs.artifact, sha256: obs.sha256 }} />}
    </Section>
  );
}

/* ---- Scanner authoring */
const ACTIVE_SCAN = ['queued', 'running', 'cancelling', 'canceling'];
const NAME_RE = /^[A-Za-z][A-Za-z0-9_]*$/;
const COMPARISONS = ['gt', 'gte', 'lt', 'lte', 'eq', 'cross_above', 'cross_below'];
const newProgram = () => ({
  version: 'scanner-program-v1', anchor_input: 'price',
  inputs: { price: { timeframe: '1Day', session: 'provider_day', source_profile: { provider: 'Alpaca', feed: 'iex', adjustment: 'raw', currency: 'USD' }, history_key: null, value: { kind: 'field', field: 'close' }, max_staleness_buckets: 0 } },
  parameters: {}, operator: 'ALL', conditions: [], time_basis: 'evaluate_now',
});
const newDefinition = () => ({
  name: '', query: null, target: { mode: 'fixed', symbols: [] }, operator: 'ALL', atoms: [],
  collection: { mode: 'retained', feed: 'iex', adjustment: 'raw', lookback_days: 365, max_symbols: 25, max_intervals: 1, max_pages: 1, max_requests: 25, max_seconds: 600 },
  schedule: { enabled: false, timezone: 'America/New_York', cadence_minutes: 60, session: 'any' }, alert: false,
});

function ProgramEditor({ program, setProgram, formulas }) {
  const mut = (fn) => setProgram((p) => { const n = structuredClone(p); fn(n); return n; });
  const inputs = Object.keys(program.inputs);
  const operandEditor = (cond, side, i) => {
    const o = cond[side];
    return (
      <Stack direction="row" spacing={0.5}>
        <TextField size="small" select label={`${side} kind`} value={o.kind} sx={{ minWidth: 110 }}
          onChange={(e) => mut((n) => { n.conditions[i][side] = e.target.value === 'constant' ? { kind: 'constant', value: '0', units: 'scalar' } : { kind: e.target.value, name: '' }; })}>
          {['input', 'parameter', 'constant'].map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
        </TextField>
        {o.kind === 'constant' ? <>
          <TextField size="small" label="Value" value={o.value} onChange={(e) => mut((n) => { n.conditions[i][side].value = e.target.value; })} />
          <TextField size="small" select label="Units" value={o.units} onChange={(e) => mut((n) => { n.conditions[i][side].units = e.target.value; })}>
            {['price', 'volume', 'scalar', 'percent'].map((u) => <MenuItem key={u} value={u}>{u}</MenuItem>)}
          </TextField>
        </> : <TextField size="small" select label="Name" value={o.name} sx={{ minWidth: 130 }} onChange={(e) => mut((n) => { n.conditions[i][side].name = e.target.value; })}>
          {(o.kind === 'input' ? inputs : Object.keys(program.parameters)).map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
        </TextField>}
      </Stack>
    );
  };
  const renameInput = (from, to) => {
    if (!NAME_RE.test(to) || (to !== from && program.inputs[to])) return;
    mut((n) => {
      n.inputs = Object.fromEntries(Object.entries(n.inputs).map(([k, v]) => [k === from ? to : k, v]));
      if (n.anchor_input === from) n.anchor_input = to;
      n.conditions.forEach((c) => ['left', 'right'].forEach((s) => { if (c[s].kind === 'input' && c[s].name === from) c[s].name = to; }));
    });
  };
  return (
    <Box sx={{ my: 1 }}>
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
        <TextField size="small" select label="Anchor input" value={program.anchor_input} onChange={(e) => mut((n) => { n.anchor_input = e.target.value; })} sx={{ minWidth: 140 }}>
          {inputs.map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
        </TextField>
        <TextField size="small" select label="Operator" value={program.operator} onChange={(e) => mut((n) => { n.operator = e.target.value; })}>
          {['ALL', 'ANY'].map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
        </TextField>
        <TextField size="small" select label="Time basis" value={program.time_basis} onChange={(e) => mut((n) => { n.time_basis = e.target.value; })}>
          {['evaluate_now', 'known_then'].map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
        </TextField>
      </Stack>
      <Typography variant="subtitle2">Inputs</Typography>
      {inputs.map((name) => {
        const inp = program.inputs[name];
        const set = (fn) => mut((n) => fn(n.inputs[name]));
        return (
          <Stack key={name} direction="row" spacing={0.5}  useFlexGap sx={{flexWrap: "wrap",  my: 0.5 }}>
            <TextField size="small" label="Name" defaultValue={name} onBlur={(e) => renameInput(name, e.target.value)} />
            <TextField size="small" select label="Timeframe" value={inp.timeframe} onChange={(e) => set((i) => { i.timeframe = e.target.value; })}>
              {TIMEFRAMES.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </TextField>
            <TextField size="small" select label="Session" value={inp.session} onChange={(e) => set((i) => { i.session = e.target.value; })}>
              {['regular', 'provider_day'].map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </TextField>
            <TextField size="small" select label="Adjustment" value={inp.source_profile.adjustment} onChange={(e) => set((i) => { i.source_profile.adjustment = e.target.value; })}>
              {['raw', 'split', 'dividend', 'all'].map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </TextField>
            <TextField size="small" label="History key" value={inp.history_key ?? ''} onChange={(e) => set((i) => { i.history_key = e.target.value || null; })} />
            <TextField size="small" label="Max stale buckets" value={inp.max_staleness_buckets} onChange={(e) => set((i) => { i.max_staleness_buckets = e.target.value === '' ? '' : Number(e.target.value); })} />
            <TextField size="small" select label="Value" value={inp.value.kind} onChange={(e) => set((i) => { i.value = e.target.value === 'field' ? { kind: 'field', field: 'close' } : { kind: 'definition', definition: formulas[0] ? { id: formulas[0].definition.id, revision: formulas[0].definition.revision, sha256: formulas[0].sha256 } : null, output: '' }; })}>
              <MenuItem value="field">OHLCV field</MenuItem><MenuItem value="definition" disabled={!formulas.length}>Saved definition</MenuItem>
            </TextField>
            {inp.value.kind === 'field'
              ? <TextField size="small" select label="Field" value={inp.value.field} onChange={(e) => set((i) => { i.value.field = e.target.value; })}>
                {['open', 'high', 'low', 'close', 'volume'].map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}</TextField>
              : <>
                <TextField size="small" select label="Definition revision" sx={{ minWidth: 220 }} value={inp.value.definition ? `${inp.value.definition.id}:${inp.value.definition.revision}:${inp.value.definition.sha256}` : ''}
                  onChange={(e) => { const r = formulas.find((f) => defKey(f) === e.target.value); if (r) set((i) => { i.value.definition = { id: r.definition.id, revision: r.definition.revision, sha256: r.sha256 }; i.value.output = ''; }); }}>
                  {formulas.map((f) => <MenuItem key={defKey(f)} value={defKey(f)}>{f.definition.name} · r{f.definition.revision}</MenuItem>)}
                </TextField>
                <TextField size="small" label="Output component" value={inp.value.output ?? ''} onChange={(e) => set((i) => { i.value.output = e.target.value; })} />
              </>}
            <Button size="small" disabled={inputs.length <= 1 || program.anchor_input === name} onClick={() => mut((n) => { delete n.inputs[name]; })}>Remove input</Button>
          </Stack>);
      })}
      <Button size="small" onClick={() => mut((n) => { let k = inputs.length + 1; while (n.inputs[`input${k}`]) k += 1; n.inputs[`input${k}`] = structuredClone(n.inputs[n.anchor_input]); })}>Add input</Button>
      <Typography variant="subtitle2" sx={{ mt: 1 }}>Parameters</Typography>
      {Object.entries(program.parameters).map(([k, p]) => (
        <Stack key={k} direction="row" spacing={0.5} sx={{ my: 0.5 }}>
          <Typography sx={{ minWidth: 110, alignSelf: 'center' }}>{k}</Typography>
          <TextField size="small" label="Value" value={p.value} onChange={(e) => mut((n) => { n.parameters[k].value = e.target.value; })} />
          <TextField size="small" select label="Units" value={p.units} onChange={(e) => mut((n) => { n.parameters[k].units = e.target.value; })}>
            {['price', 'volume', 'scalar', 'percent'].map((u) => <MenuItem key={u} value={u}>{u}</MenuItem>)}
          </TextField>
          <Button size="small" onClick={() => mut((n) => { delete n.parameters[k]; })}>Remove</Button>
        </Stack>))}
      <Button size="small" onClick={() => mut((n) => { let i = Object.keys(n.parameters).length + 1; while (n.parameters[`threshold${i}`]) i += 1; n.parameters[`threshold${i}`] = { value: '0', units: 'scalar' }; })}>Add parameter</Button>
      <Typography variant="subtitle2" sx={{ mt: 1 }}>Conditions</Typography>
      {program.conditions.map((c, i) => (
        <Stack key={i} direction="row" spacing={0.5}  useFlexGap sx={{flexWrap: "wrap",  my: 0.5 }}>
          {operandEditor(c, 'left', i)}
          <TextField size="small" select label="Comparison" value={c.comparison} onChange={(e) => mut((n) => { n.conditions[i].comparison = e.target.value; })}>
            {COMPARISONS.map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
          </TextField>
          {operandEditor(c, 'right', i)}
          <Button size="small" onClick={() => mut((n) => { n.conditions.splice(i, 1); })}>Remove</Button>
        </Stack>))}
      <Button size="small" onClick={() => mut((n) => { n.conditions.push({ left: { kind: 'input', name: n.anchor_input }, comparison: 'gt', right: { kind: 'constant', value: '0', units: 'scalar' } }); })}>Add condition</Button>
    </Box>
  );
}

function Scans({ desk, discovery, universeSymbols }) {
  const { api, state, page, refresh } = desk;
  const { meta, reload } = discovery;
  const scanner = meta?.scanner;
  const defs = Object.values(scanner?.data?.definitions || {});
  const runs = Object.values(scanner?.data?.runs || {});
  const formulas = (state?.chart_formulas || []);
  const [draft, setDraft] = useState(newDefinition);
  const [symbolsText, setSymbolsText] = useState('');
  const [selId, setSelId] = useState('');
  const [consent, setConsent] = useState('');
  const [detail, setDetail] = useState(null);
  const [obsIdx, setObsIdx] = useState(0);
  const [json, setJson] = useState('');
  const [cutoff, setCutoff] = useState('');
  const [defRows, setDefRows] = useState([]);
  const action = useAsyncAction();
  const idn = deskIdentity(state);
  const selected = defs.find((d) => d.id === selId);
  const consentKey = `${idn}|${selId}|${selected?.revision}`;
  const collect = selected?.collection?.mode === 'collect';
  const consented = !collect || consent === consentKey;
  const anyActive = runs.some((r) => ACTIVE_SCAN.includes(r.status));

  useEffect(() => {
    if (page !== 'markets') return undefined;
    const ctl = new AbortController();
    api('/api/market-history', undefined, { signal: ctl.signal }).then((r) => setDefRows((r.chart_analysis?.history || []).filter((x) => ['formula', 'study'].includes(x.definition.kind)))).catch(() => {});
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);
  useEffect(() => {
    if (page !== 'markets' || !anyActive) return undefined;
    const t = setInterval(reload, 5000);
    return () => clearInterval(t);
  }, [page, anyActive, reload]);

  const post = (body, then) => action.run(async () => { const r = await api('/api/discovery', body); await then?.(r); reload(); });
  const loadDef = (d) => {
    const n = structuredClone(d);
    delete n.id; delete n.revision; delete n.sha256; delete n.created_at;
    n.schedule = { ...(n.schedule || newDefinition().schedule), enabled: false };
    setDraft({ ...newDefinition(), ...n }); setSymbolsText((n.target?.symbols || []).join(', ')); setConsent('');
  };
  const save = () => post({
    action: 'scan_save', expected_revision: scanner.revision,
    definition: { ...draft, name: draft.name.trim(), target: { mode: 'fixed', symbols: symbolList(symbolsText) } },
  }, (r) => { if (r.scanner?.saved_definition?.id) setSelId(r.scanner.saved_definition.id); });
  const run = () => post({ action: 'scan_run', id: selected.id, revision: selected.revision, ...(cutoff ? { market_cutoff: cutoff } : {}) }, (r) => { if (r?.run) setDetail(r.run); });
  const schedule = (enabled) => post({ action: 'scan_schedule', id: selected.id, revision: selected.revision, enabled, expected_revision: scanner.revision });
  const exportDefs = () => post({ action: 'scan_export', ...(selected ? { id: selected.id, revision: selected.revision } : {}) }, (r) => download(JSON.stringify(r.bundle, null, 2), 'scanner-definitions.json', 'application/json'));
  const importDefs = (file) => action.run(async () => {
    await api('/api/discovery', { action: 'scan_import', bundle: JSON.parse(await file.text()), expected_revision: scanner.revision, workspace_revision: state.workspace.revision });
    await refresh({fresh: true}); reload();
  });

  const setCollection = (k) => (e) => setDraft((d) => ({ ...d, collection: { ...d.collection, [k]: e.target.value } }));
  const setSchedule = (k, v) => setDraft((d) => ({ ...d, schedule: { ...d.schedule, [k]: v } }));
  const run0 = detail?.results ? detail : null;
  const programOf = (res) => res?.program || res?.program_result || res?.calculation?.result || res?.calculation;
  const resultEntries = Object.entries(run0?.results || {});
  const [pickedSym, setPickedSym] = useState('');
  const resSym = pickedSym && run0?.results?.[pickedSym] ? pickedSym : resultEntries[0]?.[0];
  const prog = programOf(run0?.results?.[resSym]);
  const obs = prog?.observations?.[obsIdx] ?? prog?.observations?.[0];

  return (
    <Section title="Scanner" actions={<Button onClick={reload}>Refresh</Button>}>
      {action.error && <Alert severity="error" onClose={() => action.setError('')}>{action.error}</Alert>}
      <Typography variant="subtitle2">Saved definitions</Typography>
      <Stack direction="row" spacing={1}  useFlexGap  sx={{flexWrap: "wrap", alignItems: "center",  my: 1 }}>
        <TextField size="small" select label="Saved revision" value={selId} sx={{ minWidth: 260 }} onChange={(e) => { setSelId(e.target.value); setConsent(''); }}>
          {defs.map((d) => <MenuItem key={d.id} value={d.id}>{d.name || d.id} · r{d.revision}</MenuItem>)}
        </TextField>
        <Button disabled={!selected} onClick={() => loadDef(selected)}>Load into draft</Button>
        <TextField size="small" label="Market cutoff (optional)" value={cutoff} onChange={(e) => setCutoff(e.target.value)} />
        <Button variant="contained" disabled={action.busy || !selected || !consented} onClick={run}>Run saved revision</Button>
        <Button disabled={action.busy || !selected || !consented} onClick={() => schedule(!selected.schedule?.enabled)}>{selected?.schedule?.enabled ? 'Disable schedule' : 'Enable schedule'}</Button>
        <Button disabled={action.busy || !scanner} onClick={exportDefs}>Export</Button>
        <Button component="label" disabled={action.busy || !scanner}>Import bundle
          <input hidden type="file" accept="application/json,.json" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) importDefs(f); }} />
        </Button>
      </Stack>
      {selected && <>
        <Typography variant="body2">r{selected.revision} · {selected.target?.mode} · collection {selected.collection?.mode} {selected.collection?.feed}/{selected.collection?.adjustment} · lookback {selected.collection?.lookback_days}d · limits {selected.collection?.max_symbols} symbols / {selected.collection?.max_intervals} intervals / {selected.collection?.max_pages} pages / {selected.collection?.max_requests} requests / {selected.collection?.max_seconds}s · schedule {selected.schedule?.enabled ? 'on' : 'off'} every {selected.schedule?.cadence_minutes}m {selected.schedule?.timezone} {selected.schedule?.session} · alert {selected.alert ? 'opted in' : 'off'}</Typography>
        {collect && <FormControlLabel control={<Checkbox checked={consent === consentKey} onChange={(e) => setConsent(e.target.checked ? consentKey : '')} />} label="I authorize provider data collection for this exact revision" />}
      </>}
      <Typography variant="subtitle2" sx={{ mt: 2 }}>Draft definition</Typography>
      <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  my: 1 }}>
        <TextField size="small" label="Name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <TextField size="small" label="Fixed symbols" value={symbolsText} onChange={(e) => setSymbolsText(e.target.value)} sx={{ minWidth: 240 }} />
        <TextField size="small" select label="Collection" value={draft.collection.mode} onChange={setCollection('mode')}>
          {['retained', 'collect'].map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
        </TextField>
        {['lookback_days', 'max_symbols', 'max_intervals', 'max_pages', 'max_requests', 'max_seconds'].map((k) => (
          <TextField key={k} size="small" type="number" label={k} value={draft.collection[k]} sx={{ width: 130 }}
            onChange={(e) => setDraft((d) => ({ ...d, collection: { ...d.collection, [k]: Number(e.target.value) } }))} />))}
        <TextField size="small" type="number" label="Cadence minutes" value={draft.schedule.cadence_minutes} onChange={(e) => setSchedule('cadence_minutes', Number(e.target.value))} sx={{ width: 140 }} />
        <TextField size="small" select label="Schedule session" value={draft.schedule.session} onChange={(e) => setSchedule('session', e.target.value)}>
          {['any', 'regular'].map((k) => <MenuItem key={k} value={k}>{k}</MenuItem>)}
        </TextField>
        <FormControlLabel control={<Checkbox checked={draft.alert} onChange={(e) => setDraft({ ...draft, alert: e.target.checked })} />} label="Alert opt-in" />
        <Button size="small" onClick={() => setSymbolsText(universeSymbols.join(', '))}>Use universe</Button>
      </Stack>
      {draft.program
        ? <><ProgramEditor program={draft.program} setProgram={(fn) => setDraft((d) => ({ ...d, program: fn(d.program) }))} formulas={defRows.length ? defRows : formulas} />
          <Button size="small" color="error" onClick={() => setDraft((d) => { const n = { ...d }; delete n.program; return n; })}>Remove program</Button></>
        : <Button size="small" onClick={() => setDraft((d) => ({ ...d, program: newProgram() }))}>Add program</Button>}
      <Accordion disableGutters sx={{ mt: 1 }}>
        <AccordionSummary><Typography>Advanced JSON</Typography></AccordionSummary>
        <AccordionDetails>
          <TextField multiline minRows={6} fullWidth value={json || JSON.stringify(draft, null, 2)} onChange={(e) => setJson(e.target.value)} slotProps={{ htmlInput: { spellCheck: false } }} />
          <Button onClick={() => action.run(async () => { const d = JSON.parse(json || JSON.stringify(draft)); setDraft({ ...newDefinition(), ...d }); setSymbolsText((d.target?.symbols || []).join(', ')); setJson(''); })}>Apply JSON to draft</Button>
        </AccordionDetails>
      </Accordion>
      <Button variant="contained" sx={{ mt: 1 }} disabled={action.busy || !scanner || !draft.name.trim()} onClick={save}>Save new revision</Button>

      <Typography variant="subtitle2" sx={{ mt: 2 }}>Runs</Typography>
      {runs.length ? runs.map((r) => (
        <Stack key={r.id} direction="row" spacing={1}  sx={{alignItems: "center"}}>
          <Typography sx={{ flex: 1 }}>{String(r.id).slice(0, 8)} · {r.status}</Typography>
          <Button size="small" onClick={() => post({ action: 'scan_detail', run_id: r.id }, (x) => { setDetail(x.run); setObsIdx(0); })}>Detail</Button>
          {ACTIVE_SCAN.includes(r.status) && <Button size="small" onClick={() => post({ action: 'scan_cancel', run_id: r.id })}>Cancel</Button>}
        </Stack>)) : <Typography variant="body2">No runs.</Typography>}
      {run0 && <Box sx={{ mt: 1 }}>
        <Typography>Run {String(run0.id).slice(0, 8)} · {run0.status}</Typography>
        <TextField size="small" select label="Symbol result" value={resSym ?? ''} sx={{ minWidth: 200, my: 1 }} onChange={(e) => { setPickedSym(e.target.value); setObsIdx(0); }}>
          {resultEntries.map(([s, r]) => <MenuItem key={s} value={s}>{s} · {r.state}{r.coverage_complete === false ? ' · partial' : ''}</MenuItem>)}
        </TextField>
        {prog?.observations?.length > 0 && <TextField size="small" select label="Observation" value={obsIdx} sx={{ minWidth: 260, ml: 1 }} onChange={(e) => setObsIdx(Number(e.target.value))}>
          {prog.observations.map((o, i) => <MenuItem key={i} value={i}>{i + 1} · {text(o.anchor?.t ?? o.anchor?.closed_at)} · src {text(o.anchor?.source_ordinal)}</MenuItem>)}
        </TextField>}
        {obs && <Typography variant="body2">Evaluation {text(obs.evaluation)} · {Object.entries(obs.inputs || {}).map(([k, v]) => `${k}: ${v.fresh ? 'fresh' : 'stale'}`).join(', ')}</Typography>}
        {prog && <Typography variant="body2">{text(prog.evaluation)} · coverage {prog.coverage?.complete === false || run0.results[resSym]?.coverage_complete === false ? 'partial' : 'complete'}{prog.reasons?.length ? ` · ${prog.reasons.join('; ')}` : ''}</Typography>}
        <Evidence title="Run counts, coverage and provider operations" data={{ universe: run0.universe, counts: run0.counts, coverage: run0.coverage, unprocessed: run0.unprocessed, provider_operations: run0.provider_operations }} />
        <Evidence title="Raw run detail" data={run0} />
      </Box>}
    </Section>
  );
}

export function MarketsView() {
  const desk = useDesk();
  const { state, stateError, api, refresh, page, selectedSymbol, setSelectedSymbol, navigation, clearNavigation } = desk;
  const [tab, setTab] = useState('universe');
  const [query, setQuery] = useState('');
  const [listId, setListId] = useState('');
  const [target, setTarget] = useState('shortlist');
  const [minMove, setMinMove] = useState(0);
  const [sortKey, setSortKey] = useState('symbol');
  const [descending, setDescending] = useState(false);
  const [checked, setChecked] = useState(() => new Set());
  const [colDraft, setColDraft] = useState(null);
  const [savedBars, setSavedBars] = useState({});
  const exportAction = useAsyncAction();
  const discovery = useDiscoveryMeta(desk);

  useEffect(() => {
    if (!navigation || navigation.page !== 'markets') return;
    const sym = String(navigation.intent?.symbol || '').toUpperCase();
    if (SYMBOL.test(sym)) setSelectedSymbol(sym);
    if (['universe', 'screener', 'options', 'scans'].includes(navigation.intent?.tab)) setTab(navigation.intent.tab);
    clearNavigation(navigation.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigation?.id]);

  const universe = universeOf(state);
  const lists = state?.workspace?.data?.watchlists || [];
  const members = useMemo(() => (listId ? new Set(lists.find((l) => l.id === listId)?.symbols || []) : null), [listId, lists]);
  const held = useMemo(() => new Set((state?.positions || []).map((p) => p.symbol)), [state?.positions]);
  const posOf = useMemo(() => Object.fromEntries((state?.positions || []).map((p) => [p.symbol, p])), [state?.positions]);
  const exposureKnown = !stateError && state?.connection?.account_verified === true && state?.nautilus?.status === 'connected' && state?.nautilus?.reconciliation?.status === 'reconciled';
  const savedPref = state?.workspace?.data?.preferences?.columns;
  const cols = colDraft ?? { order: savedPref?.order || COLUMN_OPTIONS.map(([k]) => k), visible: savedPref?.visible || DEFAULT_COLUMNS };
  const visible = new Set([...cols.visible, ...CORE_COLUMNS.filter(() => false)]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const val = (s) => ({ symbol: s, price: state?.quotes?.[s]?.price, change: state?.quotes?.[s]?.change_pct,
      move: Math.abs(state?.quotes?.[s]?.change_pct ?? NaN), rating: state?.research?.[s]?.rating, researched: state?.research?.[s]?.trade_date })[sortKey];
    return universe.filter((s) => (!members || members.has(s)) && (!q || s.toLowerCase().includes(q) || (state?.company_names?.[s] || '').toLowerCase().includes(q))
      && (!minMove || Math.abs(state?.quotes?.[s]?.change_pct ?? 0) >= minMove))
      .sort((a, b) => {
        const x = val(a), y = val(b);
        if (x == null || Number.isNaN(x)) return 1;
        if (y == null || Number.isNaN(y)) return -1;
        const c = typeof x === 'number' ? x - y : String(x).localeCompare(String(y));
        return descending ? -c : c;
      });
  }, [universe, members, query, minMove, sortKey, descending, state?.quotes, state?.research, state?.company_names]);

  const exportCsv = () => exportAction.run(async () => {
    const rep = await api('/api/reporting');
    const out = await api('/api/reporting', { action: 'export_csv', kind: 'holdings', symbols: [...checked], expected_revision: rep.revision });
    download(out.csv, out.filename || 'holdings.csv', 'text/csv;charset=utf-8');
  });

  const quoteOf = (s) => state?.nautilus?.market_data?.[s]?.quote;
  const lastSaved = (s, f) => { const b = savedBars[s]?.bars?.at(-1); return b ? text(b.raw?.[f] ?? b[f]) : 'Not loaded · open stock'; };
  const spread = (s) => { const q = quoteOf(s); const b = Number(q?.bid_price), a = Number(q?.ask_price); return q && b > 0 && a >= b ? ((a - b) / ((a + b) / 2) * 10000).toFixed(1) : UNAVAILABLE; };
  const defs = {
    price: { label: 'Last', numeric: true, render: (s) => money(state?.quotes?.[s]?.price) },
    change: { label: 'Change', numeric: true, render: (s) => pct(state?.quotes?.[s]?.change_pct) },
    age: { label: 'Quote age', render: (s) => dateTime(state?.quotes?.[s]?.timestamp) },
    research: { label: 'Research', render: (s) => `${text(state?.research?.[s]?.rating)} · ${text(state?.research?.[s]?.trade_date)}` },
    bidask: { label: 'Bid / ask', render: (s) => { const q = quoteOf(s); return q ? `${money(q.bid_price)} × ${text(q.bid_size)} / ${money(q.ask_price)} × ${text(q.ask_size)}` : UNAVAILABLE; } },
    spread: { label: 'Spread bps', numeric: true, render: spread },
    position: { label: 'Position', render: (s) => (exposureKnown ? text(posOf[s]?.qty ?? '0') : 'Unknown') },
    upl: { label: 'Unrealized P/L', numeric: true, render: (s) => (!exposureKnown ? 'Unknown' : posOf[s] ? pct(Number(posOf[s].unrealized_plpc) * 100) : '—') },
    working: { label: 'Working', numeric: true, render: (s) => (Array.isArray(state?.orders) ? String(state.orders.filter((o) => o.symbol === s && !TERMINAL.includes(String(o.status).toLowerCase())).length) : 'Unknown') },
    savedOpen: { label: 'Saved open', render: (s) => lastSaved(s, 'o') },
    savedHigh: { label: 'Saved high', render: (s) => lastSaved(s, 'h') },
    savedLow: { label: 'Saved low', render: (s) => lastSaved(s, 'l') },
    savedClose: { label: 'Saved close', render: (s) => lastSaved(s, 'c') },
    savedVolume: { label: 'Saved volume', render: (s) => lastSaved(s, 'v') },
  };
  const columns = [
    { id: 'symbol', label: 'Symbol', render: (s) => s },
    { id: 'company', label: 'Company', render: (s) => state?.company_names?.[s] || UNAVAILABLE },
    ...cols.order.filter((k) => visible.has(k) && defs[k]).map((k) => ({ id: k, ...defs[k] })),
    { id: 'held', label: 'Held', render: (s) => (held.has(s) ? 'Held' : '') },
  ];
  const quote = state?.quotes?.[selectedSymbol];

  return (
    <Page title="Markets" subtitle="Universe, screener, options, scanner and instrument evidence." actions={<Button onClick={refresh}>Refresh</Button>}>
      {desk.error && <Alert severity="error" onClose={() => desk.setError('')} sx={{ mb: 2 }}>{desk.error}</Alert>}
      {discovery.error && <Alert severity="warning" sx={{ mb: 2 }}>{discovery.error}</Alert>}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="universe" label="Universe & watchlists" />
        <Tab value="screener" label="Yahoo screener" />
        <Tab value="options" label="Options" />
        <Tab value="scans" label="Scanner" />
      </Tabs>
      <Box hidden={tab !== 'universe'}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 7 }}>
            <Section title="Universe" actions={<Button disabled={!checked.size || exportAction.busy} onClick={exportCsv}>Export selected holdings CSV</Button>}>
              {exportAction.error && <Alert severity="error">{exportAction.error}</Alert>}
              <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
                <TextField size="small" label="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
                <TextField size="small" select label="List" value={listId} sx={{ minWidth: 150 }} onChange={(e) => setListId(e.target.value)}>
                  <MenuItem value="">All stocks</MenuItem>
                  {lists.map((l) => <MenuItem key={l.id} value={l.id}>{l.name}</MenuItem>)}
                </TextField>
                <TextField size="small" select label="Min move" value={minMove} onChange={(e) => setMinMove(Number(e.target.value))}>
                  {[0, 0.5, 1, 2, 3, 5].map((m) => <MenuItem key={m} value={m}>{m}%</MenuItem>)}
                </TextField>
                <TextField size="small" select label="Sort" value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
                  {[['symbol', 'Symbol'], ['price', 'Price'], ['change', 'Change %'], ['move', 'Move size'], ['rating', 'Rating'], ['researched', 'Research date']].map(([k, l]) => <MenuItem key={k} value={k}>{l}</MenuItem>)}
                </TextField>
                <FormControlLabel control={<Checkbox checked={descending} onChange={(e) => setDescending(e.target.checked)} />} label="Descending" />
                <Button onClick={() => setChecked(new Set(rows))}>Select all</Button>
                <Button onClick={() => setChecked(new Set())}>Clear</Button>
              </Stack>
              <DataTable rows={rows} columns={columns} getRowId={(s) => s} onRowClick={setSelectedSymbol}
                selectedIds={[...checked]} onSelectionChange={(ids) => setChecked(new Set(ids))} empty="No stocks match." />
              <Typography variant="caption">Working counts use the order list only; proposal receipts are not included.</Typography>
            </Section>
            <ColumnPicker desk={desk} cols={cols} setCols={(fn) => setColDraft((c) => fn(c ?? cols))} />
            <Watchlists desk={desk} target={target} setTarget={setTarget} checked={checked} />
          </Grid>
          <Grid size={{ xs: 12, md: 5 }}>
            {selectedSymbol ? (
              <>
                <Section title={`${selectedSymbol} · ${state?.company_names?.[selectedSymbol] || ''}`}>
                  <Typography>Last {money(quote?.price)} · {pct(quote?.change_pct)}</Typography>
                  <Typography>Research: {text(state?.research?.[selectedSymbol]?.rating)} · {text(state?.research?.[selectedSymbol]?.trade_date)}</Typography>
                </Section>
                <Notes symbol={selectedSymbol} desk={desk} />
              </>
            ) : <Typography>Select a stock to inspect.</Typography>}
          </Grid>
          {selectedSymbol && (
            <Grid size={12}>
              <InstrumentChart symbol={selectedSymbol} desk={desk} onLoaded={(r) => setSavedBars((b) => (b[selectedSymbol] === r ? b : { ...b, [selectedSymbol]: r }))} />
              <SupplementaryEvidence symbol={selectedSymbol} desk={desk} />
            </Grid>
          )}
        </Grid>
      </Box>
      <Box hidden={tab !== 'screener'}><Screener desk={desk} discovery={discovery} target={target} /></Box>
      <Box hidden={tab !== 'options'}><Options desk={desk} discovery={discovery} /></Box>
      <Box hidden={tab !== 'scans'}><Scans desk={desk} discovery={discovery} universeSymbols={universe} /></Box>
    </Page>
  );
}
