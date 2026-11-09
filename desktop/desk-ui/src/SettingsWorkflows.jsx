import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions,
  DialogContent, DialogContentText, DialogTitle, FormControl, FormControlLabel, FormLabel, Grid, InputLabel,
  LinearProgress, MenuItem, Radio, RadioGroup, Select, Stack, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import { useDesk } from './DeskContext.jsx';
import { Page, Evidence, DataTable, dateTime, Status } from './ui.jsx';

const TABS = [['Account', 'Account & Engine'], ['Research', 'Research & Models'], ['Trading rules', 'Trading Rules & Native Cache'], ['Integrations', 'Universe & Keys'], ['Diagnostics', 'Diagnostics & Backup']];
const CONFIG_KEYS = {
  Research: ['llm_provider', 'backend_url', 'deep_think_llm', 'quick_think_llm', 'deep_max_total_tokens', 'deep_max_output_tokens', 'deep_reasoning_effort', 'quick_max_total_tokens', 'quick_max_output_tokens', 'quick_reasoning_effort', 'research_concurrency', 'research_retries', 'llm_retries', 'llm_retry_seconds', 'social_screen_timeout_seconds', 'social_screen_max_posts', 'laya_device', 'research_stop_on_failure', 'max_tokens', 'max_debate_rounds', 'max_risk_discuss_rounds', 'max_tool_rounds', 'selected_analysts', 'allocation_pct', 'max_position_pct', 'max_order_notional', 'reserve_pct', 'price_buffer_bps'],
  Integrations: ['name', 'universe', 'maenifold_port', 'maenifold_root'],
};
const SIGN_IN = ['codex', 'chatgpt'];
const REASONING = ['codex', 'chatgpt', 'openai', 'openai_compatible'];
const FANGMAN = 'META, AAPL, NVDA, GOOGL, MSFT, AMZN, NFLX';
const RULE_COPY = {
  cash_reserve_pct: ['Cash reserve', 'Minimum cash left (% of account equity)', 'Cash after reserving pending and proposed buys and fees; sale proceeds are not credited before they arrive.'],
  max_position_pct: ['Single-stock exposure', 'Maximum for one stock (% of account equity)', 'Includes current exposure plus pending and proposed buys, without assuming sales fill.'],
  max_gross_exposure_pct: ['Total stock exposure', 'Maximum total exposure (% of account equity)', 'Adds current stock exposure and pending/proposed buys; planned sales do not reduce this check.'],
  loss_limit_pct: ['Current unrealized loss', 'Maximum unrealized loss (% of reported cost)', 'Aggregate broker-reported unrealized loss divided by reported cost basis. Not a daily stop-loss or future-loss guarantee.'],
  scenario_loss_pct: ['Price-fall scenario', 'Maximum estimated loss (% of account equity)', 'Models your chosen price fall across long stocks, including pending/proposed buys and fees. Not a guaranteed loss cap.'],
  max_sector_pct: ['Sector exposure', 'Maximum per sector (% of account equity)', 'Groups exposure by provider-reported sector. Missing or outdated sector data blocks this check.'],
  max_correlation_pct: ['Stock-return correlation', 'Maximum absolute correlation (0–100)', 'Compares matching daily returns. A value of 100 means an absolute correlation of 1.'],
  max_spread_bps: ['Bid/ask spread', 'Maximum spread (basis points)', 'Ask minus bid over their midpoint, from the same IEX quote. Not a consolidated-market liquidity measure.'],
  min_quote_size: ['Displayed quote size', 'Minimum displayed quantity (shares)', 'IEX ask shares for a buy or bid shares for a sale. Displayed size does not guarantee a fill.'],
  session_freshness: ['Quote freshness', 'Maximum quote age while open (seconds)', 'Closed-market age limit and review permission are separate.'],
};
const CHOICE_COPY = { unset: 'Decide later', enabled: 'Apply this rule', disabled: 'Do not apply', parallel_long_equity_price_shock: 'Same percentage fall across long stock positions', pearson_daily_close_returns: 'Pearson correlation of daily closing-price returns', provider_sector: 'Sectors reported by the data provider', split: 'Adjust for stock splits only', all: 'All corporate-action adjustments supplied by the provider', regular_session_required: 'Require the regular market session to be open', allow_closed_session_review: 'Allow review while the regular market is closed' };
const PARAM_COPY = { shock_pct: 'Price fall to model (%)', classification: 'Sector grouping', max_classification_age_seconds: 'Oldest sector data allowed (seconds)', window_sessions: 'Return window (trading sessions)', max_history_age_seconds: 'Oldest correlation history allowed (seconds)', minimum_pairs: 'Minimum matching daily return dates', adjustment: 'Historical price adjustment', max_quote_age_seconds: 'Oldest quote allowed (seconds)', closed_max_age_seconds: 'Oldest closed-market quote allowed (seconds)', session: 'When review is allowed' };

const errText = (e) => (e && e.message) || 'The action failed.';
const keyed = (v) => String(v ?? '');
const saveFile = (content, name, type) => {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

// Same symbol rules as the saved universe: US equity syntax, de-duplicated, at most 1,000.
function parseSymbols(input, { preview = false, file = false } = {}) {
  const text = String(input || '').replace(/^\uFEFF/, '');
  if (text.length > 1048576) throw new Error('Use a CSV or text file smaller than 1 MB.');
  const lines = text.split(/\r\n|\n|\r/).filter((l) => l.trim());
  const cells = (l) => l.split(',').map((c) => c.trim().replace(/^"(.*)"$/, '$1'));
  const head = lines.length ? cells(lines[0]).findIndex((c) => ['symbol', 'ticker', 'stocksymbol'].includes(c.toLowerCase().replace(/[\s_]/g, ''))) : -1;
  let values;
  if (head >= 0) values = lines.slice(1).map((l, i) => ({ value: cells(l)[head] || '', row: i + 2 }));
  else {
    if (file && lines.length > 1 && lines.some((l) => l.includes(','))) throw new Error('Add a Symbol or Ticker header to a multi-column CSV. A one-column list also works.');
    values = lines.flatMap((l, i) => l.split(/[\s,;]+/).filter(Boolean).map((value) => ({ value, row: i + 1 })));
  }
  const seen = new Set();
  const rows = values.map((item) => {
    const symbol = item.value.trim().toUpperCase();
    const status = !/^[A-Z][A-Z0-9.-]{0,9}$/.test(symbol) ? 'rejected' : seen.has(symbol) ? 'duplicate' : 'accepted';
    if (status === 'accepted') seen.add(symbol);
    return { ...item, symbol, status, reason: status === 'accepted' ? 'Valid syntax; broker support is checked separately' : status === 'duplicate' ? 'Already accepted earlier' : symbol ? 'Unsupported US equity symbol syntax' : 'Symbol field is empty' };
  });
  const bad = rows.filter((r) => r.status === 'rejected');
  if (!preview && bad.length) throw new Error('Rejected symbol rows: ' + bad.slice(0, 5).map((r) => `${r.row} (${r.value || 'empty'})`).join(', ') + '.');
  if (!preview && !seen.size) throw new Error('Enter at least one stock symbol.');
  if (seen.size > 1000) throw new Error('This workspace supports up to 1,000 stock symbols.');
  return { symbols: [...seen], rejected: bad.length, duplicates: rows.filter((r) => r.status === 'duplicate').length, rows };
}

function buildChanges(category, base, draft) {
  const c = { ...base, ...draft };
  const keys = CONFIG_KEYS[category];
  const num = (k) => Number(c[k]);
  for (const k of ['allocation_pct', 'max_position_pct', 'reserve_pct', 'max_order_notional', 'social_screen_timeout_seconds', 'social_screen_max_posts', 'price_buffer_bps', 'max_debate_rounds', 'max_risk_discuss_rounds', 'max_tool_rounds', 'research_concurrency', 'research_retries', 'llm_retries', 'llm_retry_seconds']) if (k in c) c[k] = num(k);
  if (keys.includes('max_tokens')) c.max_tokens = SIGN_IN.includes(c.llm_provider) || !keyed(c.max_tokens).trim() ? null : Number(c.max_tokens);
  if (keys.includes('maenifold_port')) c.maenifold_port = Number(c.maenifold_port);
  if (keys.includes('maenifold_root')) c.maenifold_root = keyed(c.maenifold_root).trim();
  for (const k of ['deep_max_total_tokens', 'deep_max_output_tokens', 'quick_max_total_tokens', 'quick_max_output_tokens']) if (keys.includes(k)) c[k] = keyed(c[k]).trim() ? Number(c[k]) : null;
  if (c.llm_provider !== 'openai_compatible') for (const k of ['deep_max_total_tokens', 'quick_max_total_tokens']) if (keys.includes(k)) c[k] = null;
  if (SIGN_IN.includes(c.llm_provider)) for (const k of ['deep_max_output_tokens', 'quick_max_output_tokens']) if (keys.includes(k)) c[k] = null;
  for (const k of ['deep_reasoning_effort', 'quick_reasoning_effort']) if (keys.includes(k)) c[k] = REASONING.includes(c.llm_provider) ? c[k] || null : null;
  if (keys.includes('backend_url')) c.backend_url = c.llm_provider === 'codex' ? null : keyed(c.backend_url).trim() || null;
  if (keys.includes('universe')) {
    c.universe = parseSymbols(Array.isArray(c.universe) ? c.universe.join(',') : c.universe).symbols;
    if (!c.universe.length) throw new Error('Enter at least one stock symbol.');
  }
  if (keys.includes('allocation_pct')) {
    if (c.allocation_pct + c.reserve_pct > 100) throw new Error('Invested allocation plus cash reserve cannot exceed 100%.');
    if (c.max_position_pct > c.allocation_pct) throw new Error('The single-position limit cannot exceed total invested allocation.');
  }
  return Object.fromEntries(keys.map((k) => [k, c[k]]));
}

function useConfirm() {
  const [req, setReq] = useState(null);
  const ask = (title, body, onYes, yes = 'Confirm') => setReq({ title, body, onYes, yes });
  const dialog = (
    <Dialog open={!!req} onClose={() => setReq(null)}>
      <DialogTitle>{req?.title}</DialogTitle>
      <DialogContent><DialogContentText>{req?.body}</DialogContentText></DialogContent>
      <DialogActions>
        <Button onClick={() => setReq(null)} autoFocus>Keep editing</Button>
        <Button color="warning" onClick={() => { const f = req.onYes; setReq(null); f(); }}>{req?.yes}</Button>
      </DialogActions>
    </Dialog>
  );
  return [ask, dialog];
}

function Section({ title, children, actions }) {
  return (
    <Box component="section" sx={{ mb: 3 }}>
      <Stack direction="row"   sx={{justifyContent: "space-between", alignItems: "center",  mb: 1 }}>
        <Typography variant="h6" component="h2">{title}</Typography>
        <Stack direction="row" spacing={1}>{actions}</Stack>
      </Stack>
      {children}
    </Box>
  );
}

function Facts({ rows }) {
  return (
    <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'minmax(160px,max-content) 1fr', gap: '4px 16px', m: 0 }}>
      {rows.map(([k, v]) => (
        <React.Fragment key={k}>
          <Typography component="dt" variant="body2" color="text.secondary">{k}</Typography>
          <Typography component="dd" variant="body2" sx={{ m: 0, wordBreak: 'break-word' }}>{v === null || v === undefined || v === '' ? 'Unknown' : String(v)}</Typography>
        </React.Fragment>
      ))}
    </Box>
  );
}

function Credentials({ kind, status, onStatus, available, api }) {
  const [keyId, setKeyId] = useState('');
  const [secret, setSecret] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [service, setService] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [ask, dialog] = useConfirm();
  const dirty = !!(keyId || secret || apiKey || endpoint);
  useEffect(() => {
    const h = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [dirty]);
  const a = status?.alpaca || {};
  const keys = status?.keys || [];
  const selected = service || keys[0]?.id || '';
  const selectedKey = keys.find((k) => k.id === selected);
  const ep = endpoint || (a.mode === 'live' ? 'https://api.alpaca.markets' : 'https://paper-api.alpaca.markets');
  const run = async (action) => {
    if (busy) return;
    const group = kind === 'alpaca' ? 'alpaca' : selected;
    const values = action !== 'save' ? {} : kind === 'alpaca' ? { APCA_API_KEY_ID: keyId, APCA_API_SECRET_KEY: secret, APCA_API_BASE_URL: ep } : { value: apiKey };
    if (action === 'save' && kind !== 'alpaca' && !apiKey) { setMsg('Enter an API key to save.'); return; }
    setBusy(true); setMsg('');
    try {
      const result = await api('/api/credentials', { action, group, values });
      onStatus(result.status || result);
      setKeyId(''); setSecret(''); setApiKey(''); setEndpoint('');
      setMsg(action === 'save' ? 'Credentials saved.' : 'Credentials removed.');
    } catch {
      setMsg('Could not update credentials. Check the system credential store and try again.');
    } finally { setBusy(false); }
  };
  const disabled = !available || busy;
  return (
    <Section title={kind === 'alpaca' ? 'Alpaca credentials' : 'Service API keys'}>
      {dialog}
      <Stack spacing={2} component="form" onSubmit={(e) => { e.preventDefault(); run('save'); }} autoComplete="off">
        {kind === 'alpaca' ? (
          <>
            <Typography variant="body2">Key ID: {a.key_id_configured ? 'Saved' : 'Not saved'} · Secret: {a.secret_configured ? 'Saved' : 'Not saved'}</Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 4 }}><TextField fullWidth size="small" type="password" label="Key ID" value={keyId} onChange={(e) => setKeyId(e.target.value)} disabled={disabled} helperText="Leave blank to keep the saved key ID." slotProps={{ htmlInput: { autoComplete: 'off' } }} /></Grid>
              <Grid size={{ xs: 12, md: 4 }}><TextField fullWidth size="small" type="password" label="Secret key" value={secret} onChange={(e) => setSecret(e.target.value)} disabled={disabled} helperText="Leave blank to keep the saved secret." slotProps={{ htmlInput: { autoComplete: 'new-password' } }} /></Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField select fullWidth size="small" label="Alpaca endpoint" value={ep} onChange={(e) => setEndpoint(e.target.value)} disabled={disabled}>
                  <MenuItem value="https://paper-api.alpaca.markets">Paper</MenuItem>
                  <MenuItem value="https://api.alpaca.markets">Live</MenuItem>
                </TextField>
              </Grid>
            </Grid>
            <Typography variant="body2" color="text.secondary">Saving does not connect. Apply changes to a running account with an explicit reconnect.</Typography>
          </>
        ) : (
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField select fullWidth size="small" label="Service" value={selected} onChange={(e) => { if (apiKey) setApiKey(''); setService(e.target.value); }} disabled={disabled || !keys.length}>
                {keys.map((k) => <MenuItem key={k.id} value={k.id}>{k.label} · {k.configured ? 'Saved' : 'Not saved'}</MenuItem>)}
              </TextField>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth size="small" type="password" label="New API key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} disabled={disabled || !keys.length} slotProps={{ htmlInput: { autoComplete: 'new-password' } }} /></Grid>
          </Grid>
        )}
        <Stack direction="row" spacing={1}>
          <Button type="submit" variant="contained" disabled={disabled || (kind !== 'alpaca' && !keys.length)}>{kind === 'alpaca' ? 'Save Alpaca credentials' : 'Save API key'}</Button>
          <Button disabled={disabled || (kind === 'alpaca' ? !(a.key_id_configured || a.secret_configured) : !selectedKey?.configured)} onClick={() => ask('Remove saved credentials?', 'The saved credentials are removed from the system credential store.', () => run('remove'), 'Remove')}>
            {kind === 'alpaca' ? 'Remove saved Alpaca credentials' : 'Remove saved API key'}
          </Button>
        </Stack>
        <Typography role="status" variant="body2">{msg}</Typography>
      </Stack>
    </Section>
  );
}

export function SettingsView() {
  const { state, api, act, refresh, page, navigate, error: deskError, stateError, navigation, clearNavigation } = useDesk();
  const config = state?.config || {};
  const [tab, setTab] = useState('Account');
  // Handoff intent {tab, focus?}: selects a category and optionally focuses a Nautilus control; never acts.
  useEffect(() => {
    if (!navigation || navigation.page !== 'settings') return;
        const { tab: want, focus, reportKind: wantedReport } = navigation.intent || {};
    if (TABS.some(([k]) => k === want)) setTab(want);
        if (wantedReport === 'positions' || wantedReport === 'orders') setReportKind(wantedReport);
        if (focus === 'nautilus-start' || focus === 'nautilus-stop' || focus === 'session_freshness' || focus === 'native-report') {
          setTimeout(() => document.getElementById(focus)?.focus(), 0);
        }
        clearNavigation(navigation.id);
  }, [navigation, clearNavigation]);
  const [draft, setDraft] = useState(null);
  const baseRev = useRef(null);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const providerDrafts = useRef(new Map());
  const [ask, confirmDialog] = useConfirm();

  const val = (k) => (draft && k in draft ? draft[k] : config[k]);
  const set = (k, v) => {
    if (!draft) baseRev.current = state?.config_revision ?? null;
    setDraft((d) => ({ ...(d || {}), [k]: v }));
  };
  const conflict = !!draft && baseRev.current !== (state?.config_revision ?? null);
  const dirtyKeys = (cat) => (draft ? CONFIG_KEYS[cat].filter((k) => k in draft) : []);
  const discard = (cat) => setDraft((d) => {
    if (!d) return d;
    const next = { ...d };
    CONFIG_KEYS[cat].forEach((k) => delete next[k]);
    if (cat === 'Research') providerDrafts.current.clear();
    if (!Object.keys(next).length) { baseRev.current = null; return null; }
    return next;
  });
  const discardAll = () => { providerDrafts.current.clear(); baseRev.current = null; setDraft(null); setFormError(''); };

  const save = async (cat) => {
    if (saving || conflict) return;
    setFormError('');
    let changes;
    try { changes = buildChanges(cat, config, draft || {}); } catch (e) { setFormError(errText(e)); return; }
    setSaving(true);
    try {
      await act('config', '/api/config', { changes, expected_revision: baseRev.current ?? state.config_revision });
      setDraft((d) => {
        if (!d) return d;
        const next = { ...d };
        CONFIG_KEYS[cat].forEach((k) => delete next[k]);
        if (!Object.keys(next).length) { baseRev.current = null; return null; }
        baseRev.current = state.config_revision ?? baseRev.current;
        return next;
      });
    } catch (e) { setFormError(errText(e)); } finally { setSaving(false); }
  };

  const onProvider = (next) => {
    const prev = val('llm_provider');
    if (prev !== 'codex') providerDrafts.current.set(prev, Object.fromEntries(['backend_url', 'quick_think_llm', 'deep_think_llm'].map((k) => [k, val(k)])));
    const restore = next === 'codex' ? { backend_url: '', quick_think_llm: 'gpt-6-luna', deep_think_llm: 'gpt-6-sol' } : providerDrafts.current.get(next) || { backend_url: '', quick_think_llm: '', deep_think_llm: '' };
    if (!draft) baseRev.current = state?.config_revision ?? null;
    setDraft((d) => ({ ...(d || {}), ...restore, llm_provider: next }));
  };

  // Credentials stay in component memory only; this is the sole bridge to the API.
  const [credStatus, setCredStatus] = useState(null);
  const [credBusy, setCredBusy] = useState(false);
  const loadCred = async () => {
    setCredBusy(true);
    try { const r = await api('/api/credentials'); setCredStatus(r.status || r); } catch { setCredStatus({ available: false, message: 'Credential status is unavailable.' }); } finally { setCredBusy(false); }
  };
  const credPanel = (kind) => (
    <>
      <Section title="Credential status" actions={<Button size="small" onClick={loadCred} disabled={credBusy}>{credStatus ? 'Refresh status' : 'Check credential status'}</Button>}>
        <Typography variant="body2" role="status">
          {credStatus ? (credStatus.message || (credStatus.available ? `${credStatus.backend || 'System credential store'} · ${credStatus.profile || 'current'} profile` : 'The system credential store is unavailable.')) : 'Select Check credential status to read saved flags. Values are never shown.'}
        </Typography>
      </Section>
      {credStatus && <Credentials kind={kind} status={credStatus} onStatus={setCredStatus} api={api} available={!!credStatus.available} />}
    </>
  );

  const identity = state?.connection?.identity || {};
  const nautilus = state?.nautilus || {};
  const stale = !!stateError;

  // Account & Engine
  const [nativeBusy, setNativeBusy] = useState(false);
  const [profile, setProfile] = useState(null);
  const status = nautilus.status || 'stopped';
  const stopped = ['stopped', 'disconnected'].includes(status);
  const selectedProfile = profile || nautilus.execution_profile || nautilus.profile_transition?.selected_profile || 'long_only';
  const nativeAct = async (action) => {
    if (nativeBusy) return;
    setNativeBusy(true);
    try { await act('native', '/api/nautilus/' + action, action === 'start' ? { execution_profile: selectedProfile } : {}); setProfile(null); } catch { /* reported by act */ } finally { setNativeBusy(false); }
  };
  const account = nautilus.account || {};
  const acctConfig = nautilus.account_configuration || {};
  const flags = ['status', 'trading_blocked', 'account_blocked', 'trade_suspended_by_user', 'shorting_enabled', 'multiplier', 'disable_overnight_trading'].map((k) => {
    const v = k === 'disable_overnight_trading' ? acctConfig[k] : account[k];
    return [k.replaceAll('_', ' '), stale ? 'UNKNOWN — last snapshot' : v === true ? 'Yes' : v === false ? 'No' : v];
  });
  const accountPanel = (
    <>
      <Section title="Account & Engine">
        <Facts rows={[['Observed mode / account', stale ? 'Unconfirmed — last snapshot' : `${identity.observed_mode || 'Unverified'} / ${identity.observed_account_id || 'Unavailable'}`], ['Configured mode', identity.configured_mode], ['Market feed', state?.health?.feed]]} />
        <Typography variant="subtitle2" sx={{ mt: 2 }}>Observed account status flags</Typography>
        <Typography variant="body2" color="text.secondary">{state?.connection?.account_verified && !stale ? 'Current observed account' : 'Last observed or unavailable account'} · captured {dateTime(nautilus.account_at)}</Typography>
        <Facts rows={flags} />
        <Typography variant="body2" sx={{ mt: 1 }}>Review and approve each order, then submit separately from Orders.</Typography>
        <Button sx={{ mt: 1 }} onClick={() => navigate('orders')}>Orders: {state?.paused ? 'Paused' : 'Active'} · Manage</Button>
      </Section>
      {credPanel('alpaca')}
      <Section title="Native engine (Nautilus)">
        <Stack spacing={2}>
          <Typography variant="body2" role="status">{stale ? 'Nautilus connection unconfirmed · last snapshot shown' : `Nautilus ${nautilus.version || ''}: ${status}${nautilus.error ? ' · ' + nautilus.error : ''}`}</Typography>
          <TextField select size="small" label="Native execution profile" value={selectedProfile} onChange={(e) => setProfile(e.target.value)} disabled={!stopped || nativeBusy} sx={{ maxWidth: 360 }}
            helperText="Profile changes apply only after an explicit Start from a stopped session and fresh eligibility validation. This does not enable a broker account or permissions.">
            <MenuItem value="long_only">Long-only default</MenuItem>
            <MenuItem value="bounded_risk_spread_v1">Bounded-risk option spreads</MenuItem>
          </TextField>
          <Typography variant="body2" color="text.secondary">
            Session profile: {nautilus.execution_profile || 'Unavailable'} · eligibility: {stale ? 'unconfirmed · last snapshot' : nautilus.profile_transition?.eligibility?.eligible === true ? 'supported at the recorded observation' : nautilus.profile_transition?.eligibility?.eligible === false ? 'blocked' : 'unverified'}.
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button id="nautilus-start" variant="contained" disabled={nativeBusy || ['starting', 'connected', 'stale', 'error'].includes(status)} onClick={() => nativeAct('start')}>{nativeBusy ? 'Working…' : 'Start Nautilus'}</Button>
            <Button id="nautilus-stop" disabled={nativeBusy || stopped} onClick={() => nativeAct('stop')}>Stop Nautilus</Button>
          </Stack>
          <Evidence title="Actual account, eligibility and native session evidence" data={{ profile_transition: nautilus.profile_transition, native_balance: nautilus.native_balance ?? null, account_observed_at: nautilus.account_at, broker_reported: { account_id: account.id ?? null, cash: account.cash ?? null, buying_power: account.buying_power ?? null, options_buying_power: account.options_buying_power ?? null, initial_margin: account.initial_margin ?? null, maintenance_margin: account.maintenance_margin ?? null } }} />
        </Stack>
      </Section>
      <Accordion disableGutters>
        <AccordionSummary>Alpaca funding and official documents</AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2">Configured account mode: {identity.configured_mode || 'unknown'} · observed: {!stale && state?.connection?.connected ? identity.observed_mode : 'unknown / stale'}.</Typography>
          <Typography variant="body2" sx={{ mt: 1 }}><a href="https://app.alpaca.markets/account/login" target="_blank" rel="noopener noreferrer">Open Alpaca dashboard</a>. Sign in and select the intended account; the portal selection is independent of this desk connection.</Typography>
          <Facts rows={[['Funding', 'On the live account, choose Funds & Wallet for deposits, withdrawals and bank linking. Paper balances use virtual funds.'], ['Official documents', 'Choose Account for statements, trade confirmations and available tax forms.']]} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Local CSV exports and activity records are not official broker statements or tax documents. This link does not log in, transfer funds or change the desk&apos;s account.</Typography>
        </AccordionDetails>
      </Accordion>
    </>
  );

  // Field helper (stable component identity: defined outside render via function call, not as component)
  const fld = (name, label, { type = 'text', help, disabled, min, max, step, placeholder } = {}) => (
    <Grid size={{ xs: 12, md: 6 }} key={name}>
      <TextField fullWidth size="small" name={name} label={label} type={type} value={keyed(val(name))} disabled={disabled}
        placeholder={placeholder} helperText={help} onChange={(e) => set(name, e.target.value)}
        slotProps={{ htmlInput: { min, max, step } }} />
    </Grid>
  );

  // Model limits (read-only)
  const [limits, setLimits] = useState(null);
  const [limitNonce, setLimitNonce] = useState(0);
  const limitQuery = [val('llm_provider'), val('backend_url'), val('deep_think_llm'), val('quick_think_llm')].map(keyed).join('\u0001');
  useEffect(() => {
    if (page !== 'settings' || tab !== 'Research' || !state?.config) return undefined;
    const [provider, backend_url, deep_think_llm, quick_think_llm] = limitQuery.split('\u0001');
    const ctl = new AbortController();
    setLimits({ pending: true });
    const t = setTimeout(async () => {
      try {
        const q = new URLSearchParams({ provider, backend_url, deep_think_llm, quick_think_llm });
        const data = await api('/api/model-limits?' + q, undefined, { timeoutMs: 120000, signal: ctl.signal });
        setLimits({ data });
      } catch (e) { if (!ctl.signal.aborted) setLimits({ error: errText(e) }); }
    }, 600);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [page, tab, limitQuery, limitNonce, !!state?.config]); // eslint-disable-line react-hooks/exhaustive-deps

  const roleControls = (role, label) => {
    const provider = val('llm_provider');
    const signIn = SIGN_IN.includes(provider);
    return [
      fld(`${role}_max_total_tokens`, `${label} max total tokens`, { type: 'number', min: 1, step: 1, placeholder: 'Use default', disabled: provider !== 'openai_compatible', help: 'Requires server template and tokenizer endpoints. Reserves output plus a 1% buffer; oversized evidence is chunked. Full sources are retained.' }),
      fld(`${role}_max_output_tokens`, `${label} max output tokens`, { type: 'number', min: 1, step: 1, placeholder: 'Use default', disabled: signIn, help: 'Blank reserves a quarter of the total, or uses the server default. Sign-in providers manage their own limits.' }),
      <Grid size={{ xs: 12, md: 6 }} key={`${role}_re`}>
        <TextField select fullWidth size="small" label={`${label} reasoning level`} value={val(`${role}_reasoning_effort`) || ''} disabled={!REASONING.includes(provider)} onChange={(e) => set(`${role}_reasoning_effort`, e.target.value)} helperText="Supported levels depend on the server and model.">
          {[['', 'Default'], ['none', 'None'], ['minimal', 'Minimal'], ['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['xhigh', 'Extra high']].map(([v, t]) => <MenuItem key={v} value={v}>{t}</MenuItem>)}
        </TextField>
      </Grid>,
    ];
  };

  const providerChoices = new Map([['codex', 'Codex (existing sign-in)'], ['openai_compatible', 'OpenAI-compatible (including Unsloth)']]);
  [config.llm_provider, val('llm_provider')].forEach((v) => { if (v && !providerChoices.has(v)) providerChoices.set(v, v); });
  const laya = state?.health?.local_laya;
  const layaText = (stale ? 'Unconfirmed · last snapshot · ' : '') + (laya ? `Status: ${laya.status || 'unknown'} · Requested: ${laya.requested_device || 'unknown'} · Actual: ${laya.device || 'Not loaded'}${laya.fallback_reason ? ' · Fallback: ' + laya.fallback_reason : ''}${laya.error ? ' · Error: ' + laya.error : ''}` : 'Laya status unavailable');

  // Portfolio prompt (active workflow joint prompt)
  const [pp, setPp] = useState({ bundle: null, draft: '', loading: false, message: '', error: false });
  const ppDirty = !!pp.bundle && pp.draft !== pp.bundle.files[pp.bundle.joint_portfolio_file];
  useEffect(() => {
    const h = (e) => { if (ppDirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [ppDirty]);
  const loadPrompt = useCallback(async () => {
    setPp((p) => ({ ...p, loading: true }));
    try {
      const cat = await api('/api/workflows');
      const bundle = await api('/api/workflows?name=' + encodeURIComponent(cat.active));
      if (!bundle.joint_portfolio_file || !Object.hasOwn(bundle.files, bundle.joint_portfolio_file)) throw new Error('Portfolio prompt mapping is unavailable.');
      setPp({ bundle, draft: bundle.files[bundle.joint_portfolio_file], loading: false, message: '', error: false });
    } catch (e) { setPp((p) => ({ ...p, loading: false, message: errText(e), error: true })); }
  }, [api]);
  const loadedPrompt = useRef(false);
  useEffect(() => {
    if (page === 'settings' && tab === 'Research' && !loadedPrompt.current) { loadedPrompt.current = true; loadPrompt(); }
  }, [page, tab, loadPrompt]);
  const savePrompt = async () => {
    const { bundle, draft: text } = pp;
    setPp((p) => ({ ...p, loading: true }));
    try {
      const cat = await api('/api/workflows');
      if (cat.active !== bundle.name) throw new Error('The active workflow changed. Your draft is retained; discard it to load the current workflow.');
      const r = await api('/api/workflows', { action: 'save', name: bundle.name, expected_active: bundle.name, revision: bundle.revision, files: { ...bundle.files, [bundle.joint_portfolio_file]: text } });
      setPp((p) => ({ bundle: { ...r, joint_portfolio_file: bundle.joint_portfolio_file }, draft: p.draft === text ? r.files[bundle.joint_portfolio_file] : p.draft, loading: false, message: 'Portfolio prompt saved.' + (r.warning ? ' ' + r.warning : ''), error: false }));
    } catch (e) {
      setPp((p) => ({ ...p, loading: false, error: true, message: e.status === 409 ? 'This workflow changed elsewhere. Your draft is retained. Discard it to load the latest version. ' + errText(e) : errText(e) }));
    }
  };

  const saveBar = (cat) => (
    <Stack direction="row" spacing={1}  sx={{alignItems: "center",  my: 1 }}>
      <Button variant="contained" disabled={saving || conflict || !dirtyKeys(cat).length || (cat === 'Research' && state?.browse_only)} onClick={() => save(cat)}>{saving ? 'Saving…' : 'Save settings'}</Button>
      <Button disabled={!dirtyKeys(cat).length} onClick={() => discard(cat)}>Discard changes</Button>
      <Typography variant="body2" color="text.secondary">{dirtyKeys(cat).length ? 'Unsaved draft' : 'Changes apply to future runs'}</Typography>
    </Stack>
  );
  const conflictAlert = conflict && (
    <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={() => ask('Discard your draft?', 'Settings changed elsewhere since you began editing. Discarding loads the latest saved values and loses your edits.', discardAll, 'Discard draft')}>Discard and load latest</Button>}>
      Settings changed since you started editing (revision {String(baseRev.current)} → {String(state?.config_revision)}). Your draft is kept; saving is blocked until you discard it.
    </Alert>
  );

  const limitRows = limits?.data?.models;
  const nf = (n) => (Number.isInteger(n) && n > 0 ? n.toLocaleString() : 'Unknown');
  const researchPanel = (
    <Box component="form" onSubmit={(e) => { e.preventDefault(); save('Research'); }}>
      {conflictAlert}
      <Section title="Core research models">
        <fieldset disabled={!!state?.browse_only} style={{ border: 0, padding: 0, margin: 0 }}>
          {saveBar('Research')}
          <Typography variant="body2" sx={{ mb: 1 }}>Applies to future research runs.</Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField select fullWidth size="small" label="Provider" value={val('llm_provider') || ''} onChange={(e) => onProvider(e.target.value)} helperText="Codex uses your existing sign-in. OpenAI-compatible includes local Unsloth endpoints.">
                {[...providerChoices].map(([v, t]) => <MenuItem key={v} value={v}>{t}</MenuItem>)}
              </TextField>
            </Grid>
            {fld('backend_url', 'Provider endpoint', { type: 'url', disabled: val('llm_provider') === 'codex', help: 'Not used by Codex. Other providers use their configured endpoint.' })}
            {fld('deep_think_llm', 'Deep reasoning model')}
            {roleControls('deep', 'Deep')[2]}
            {fld('quick_think_llm', 'Fast analysis model')}
            {roleControls('quick', 'Fast')[2]}
          </Grid>
        </fieldset>
        <Typography variant="subtitle2" sx={{ mt: 2 }}>Server model limits</Typography>
        <Box role="status" aria-live="polite">
          {limits?.pending && <LinearProgress />}
          {limits?.error && <Alert severity="error">Could not check model limits: {limits.error}</Alert>}
          {limitRows && ['deep', 'quick'].map((role) => {
            const m = limitRows.find((i) => i.role === role);
            return (
              <Box key={role} sx={{ my: 1 }}>
                <Typography variant="body2" fontWeight={600}>{role === 'deep' ? 'Deep reasoning' : 'Fast analysis'} · {m?.model || 'Unknown model'}</Typography>
                <Typography variant="body2">Loaded context: {nf(m?.context_tokens)} · Server output maximum: {nf(m?.max_output_tokens)} · Server output default: {nf(m?.default_output_tokens)}</Typography>
                {m?.message && <Typography variant="body2" color="text.secondary">{m.message}</Typography>}
              </Box>
            );
          })}
          {!limits && <Typography variant="body2">Change a model or endpoint to check its limits.</Typography>}
        </Box>
        <Button size="small" onClick={() => setLimitNonce((n) => n + 1)} disabled={!!limits?.pending}>Refresh model limits</Button>
      </Section>
      <Accordion disableGutters sx={{ mb: 3 }}>
        <AccordionSummary>Advanced token budgets, rounds, concurrency, retries &amp; local Laya router</AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            {roleControls('deep', 'Deep').slice(0, 2)}
            {roleControls('quick', 'Fast').slice(0, 2)}
            {fld('max_tokens', 'Legacy output token default', { type: 'number', min: 1, step: 1, disabled: SIGN_IN.includes(val('llm_provider')), help: 'Optional legacy default; explicit per-model limits take precedence.' })}
            {fld('max_debate_rounds', 'Research debate rounds', { type: 'number', min: 1, max: 3, step: 1 })}
            {fld('max_risk_discuss_rounds', 'Risk debate rounds', { type: 'number', min: 1, max: 3, step: 1 })}
            {fld('max_tool_rounds', 'Tool rounds', { type: 'number', min: 1, max: 20, step: 1 })}
            {fld('research_concurrency', 'Concurrent stocks', { type: 'number', min: 1, max: 100, step: 1 })}
            {fld('research_retries', 'Research data retries', { type: 'number', min: 0, step: 1, help: 'Bounded exponential backoff. Applies to new runs.' })}
            {fld('llm_retries', 'Inference retries', { type: 'number', min: 0, max: 10, step: 1, help: 'Extra attempts per model call when rate limited.' })}
            {fld('llm_retry_seconds', 'Inference retry wait / seconds', { type: 'number', min: 0, max: 600, step: 1 })}
            {fld('social_screen_timeout_seconds', 'Social screening limit / seconds', { type: 'number', min: 1, step: 1 })}
            {fld('social_screen_max_posts', 'Social screening post limit', { type: 'number', min: 1, step: 1 })}
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField select fullWidth size="small" label="Laya device" value={val('laya_device') ?? 'cpu'} onChange={(e) => set('laya_device', e.target.value)}
                helperText="GPU uses CUDA on Windows or MPS on Mac; Laya falls back to CPU when unavailable. Save after research and local screening finish.">
                <MenuItem value="cpu">CPU</MenuItem>
                <MenuItem value="gpu">GPU</MenuItem>
              </TextField>
              <Typography variant="caption" role="status" aria-live="polite">{layaText}</Typography>
            </Grid>
            <Grid size={12}><FormControlLabel control={<Checkbox checked={!!val('research_stop_on_failure')} onChange={(e) => set('research_stop_on_failure', e.target.checked)} />} label="Stop cycle if a stock fails" /></Grid>
            <Grid size={12}>
              <Typography variant="subtitle2">Saved research defaults</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>The active workflow overrides analyst selection and graph round limits for actual launches; <Button size="small" onClick={() => navigate('workflows')}>edit it in Workflows</Button>. These defaults do not change investor policy or grant order authority.</Typography>
              <Grid container spacing={2}>
                {fld('allocation_pct', 'Research allocation / %', { type: 'number', min: 0, max: 100, step: 'any' })}
                {fld('max_position_pct', 'Research single-position limit / %', { type: 'number', min: 0, max: 100, step: 'any' })}
                {fld('max_order_notional', 'Research order notional limit / USD', { type: 'number', min: 0, max: 1000000, step: 'any' })}
                {fld('reserve_pct', 'Research cash reserve / %', { type: 'number', min: 0, max: 100, step: 'any' })}
                {fld('price_buffer_bps', 'Research price buffer / bps', { type: 'number', min: 0, max: 100, step: 'any' })}
              </Grid>
              <FormControl sx={{ mt: 2 }}>
                <FormLabel>Saved default analysts</FormLabel>
                <Stack direction="row"  sx={{flexWrap: "wrap"}}>
                  {['market', 'social', 'news', 'fundamentals'].map((a) => {
                    const cur = val('selected_analysts') || [];
                    return <FormControlLabel key={a} label={a} control={<Checkbox checked={cur.includes(a)} onChange={(e) => set('selected_analysts', e.target.checked ? [...cur, a] : cur.filter((x) => x !== a))} />} />;
                  })}
                </Stack>
              </FormControl>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>
      {formError && tab === 'Research' && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
      <Section title="Portfolio modeling prompt">
        <Typography variant="body2" sx={{ mb: 1 }}>Edits the active workflow&apos;s saved prompt for future portfolio models. Existing custom workflows are not replaced by shipped defaults.</Typography>
        {pp.bundle ? (
          <Stack spacing={1}>
            <Typography variant="body2">Workflow: {pp.bundle.name}</Typography>
            <TextField multiline minRows={8} fullWidth label="Joint portfolio prompt" value={pp.draft} disabled={pp.loading || !!state?.browse_only} onChange={(e) => setPp((p) => ({ ...p, draft: e.target.value }))} slotProps={{ htmlInput: { spellCheck: false } }} />
            <Stack direction="row" spacing={1}>
              <Button disabled={pp.loading || !ppDirty} onClick={() => setPp({ bundle: null, draft: '', loading: false, message: '', error: false }) || loadPrompt()}>Discard changes</Button>
              <Button variant="contained" disabled={pp.loading || !ppDirty || !!state?.browse_only} onClick={savePrompt}>Save prompt</Button>
            </Stack>
          </Stack>
        ) : <Button onClick={loadPrompt} disabled={pp.loading}>{pp.loading ? 'Loading…' : 'Load prompt'}</Button>}
        <Typography role={pp.error ? 'alert' : 'status'} variant="body2" color={pp.error ? 'error' : 'text.secondary'}>{pp.message}</Typography>
      </Section>
    </Box>
  );

  // Trading rules (investor risk policy)
  const investor = state?.investor;
  const [policyDraft, setPolicyDraft] = useState(null);
  const [policyReason, setPolicyReason] = useState('');
  const policyBase = useRef(null);
  const [policyError, setPolicyError] = useState('');
  const [policyBusy, setPolicyBusy] = useState(false);
  const rules = policyDraft || investor?.data?.policy?.rules || {};
  const policyConflict = !!policyDraft && policyBase.current !== investor?.revision;
  const editRule = (key, field, value) => {
    if (!policyDraft) policyBase.current = investor?.revision ?? null;
    setPolicyDraft((d) => {
      const next = structuredClone(d || investor.data.policy.rules);
      next[key] = { state: 'unset', value: '', reason: '', ...(next[key] || {}), [field]: value };
      return next;
    });
  };
  const savePolicy = async () => {
    if (policyBusy || policyConflict) return;
    setPolicyBusy(true); setPolicyError('');
    try {
      const out = structuredClone(rules);
      for (const k of Object.keys(investor.rule_labels)) if (!out[k]) out[k] = { state: 'unset', value: null, reason: '' };
      await act('investor', '/api/investor', { action: 'policy', rules: out, reason: policyReason, expected_revision: policyBase.current ?? investor.revision });
      setPolicyDraft(null); setPolicyReason(''); policyBase.current = null;
    } catch (e) { setPolicyError(errText(e)); } finally { setPolicyBusy(false); }
  };
  const choiceGroup = (key, field, label, choices, value) => (
    <FormControl>
      <FormLabel>{label}</FormLabel>
      <RadioGroup row value={value ?? ''} onChange={(e) => editRule(key, field, e.target.value)}>
        {choices.map((c) => <FormControlLabel key={c} value={c} control={<Radio size="small" />} label={CHOICE_COPY[c] || c} />)}
      </RadioGroup>
    </FormControl>
  );

  const [nativeReport, setNativeReport] = useState(null);
  const [reportKind, setReportKind] = useState('orders');
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState('');
  const capture = async () => {
    setReportBusy(true); setReportError('');
    try { setNativeReport(await api('/api/native-report', { report_kind: reportKind }, { timeoutMs: 50000 })); } catch (e) { setReportError(errText(e)); } finally { setReportBusy(false); }
  };
  const risk = nautilus.native_risk || {};
  const riskValues = !stale && nautilus.status === 'connected' && risk.status === 'available' ? risk.values : null;
  const reportCurrent = nativeReport && !stale && nautilus.status === 'connected' && nativeReport.native_epoch === nautilus.native_epoch && nativeReport.store_generation === state?.store_generation;
  const reportRows = useMemo(() => (nativeReport ? nativeReport.data.slice(0, 200).map((cells, i) => ({ id: i, index: nativeReport.index[i], cells })) : []), [nativeReport]);
  const cell = (v) => (v === null || v === undefined ? 'Unavailable' : typeof v === 'object' ? JSON.stringify(v) : String(v));

  const rulesPanel = (
    <>
      <Section title="Your risk checks" actions={investor?.data?.policy ? <Chip size="small" label={`Policy revision ${investor.data.policy.revision}`} /> : null}>
        {!investor?.data?.policy ? <Typography>Trading rules are unavailable in the current observation.</Typography> : (
          <Stack spacing={2}>
            <Typography variant="body2">You can decide later and keep browsing. Only configured checks apply. Unset optional checks do not block orders; they are not treated as disabled or assigned defaults. Saving does not approve or submit orders; exact-revision review and the account order block still apply.</Typography>
            {policyConflict && <Alert severity="warning" action={<Button color="inherit" size="small" onClick={() => { setPolicyDraft(null); setPolicyReason(''); policyBase.current = null; }}>Discard and load latest</Button>}>Risk checks changed elsewhere. Your edits are kept; saving is blocked until you discard them.</Alert>}
            {Object.entries(investor.rule_labels).map(([key, label]) => {
              const rule = rules[key] || { state: 'unset', value: '', reason: '' };
              const copy = RULE_COPY[key] || [label, label, ''];
              const params = Object.entries(investor.rule_parameters?.[key] || {});
              return (
                <Box key={key} id={key === 'session_freshness' ? 'session_freshness' : undefined} tabIndex={key === 'session_freshness' ? -1 : undefined} component="fieldset" sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2 }}>
                  <Typography component="legend" variant="subtitle2">{copy[0]}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{copy[2]}</Typography>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 4 }}>
                      <TextField select fullWidth size="small" label="Use this rule" value={rule.state || 'unset'} onChange={(e) => editRule(key, 'state', e.target.value)}>
                        {['unset', 'enabled', 'disabled'].map((v) => <MenuItem key={v} value={v}>{CHOICE_COPY[v]}</MenuItem>)}
                      </TextField>
                    </Grid>
                    <Grid size={{ xs: 12, md: 4 }}><TextField fullWidth size="small" label={copy[1]} value={keyed(rule.value)} onChange={(e) => editRule(key, 'value', e.target.value)} slotProps={{ htmlInput: { inputMode: 'decimal' } }} /></Grid>
                    <Grid size={{ xs: 12, md: 4 }}><TextField fullWidth size="small" label="Optional note about this choice" value={keyed(rule.reason)} onChange={(e) => editRule(key, 'reason', e.target.value)} /></Grid>
                    {params.map(([name, def]) => (
                      <Grid size={{ xs: 12, md: 4 }} key={name}>
                        {key === 'session_freshness' && name === 'session' ? choiceGroup(key, name, PARAM_COPY[name], def.choices, rule[name])
                          : def.choices ? (
                            <TextField select fullWidth size="small" label={PARAM_COPY[name] || def.label} value={rule[name] ?? ''} onChange={(e) => editRule(key, name, e.target.value)}>
                              <MenuItem value="">Choose an option</MenuItem>
                              {def.choices.map((v) => <MenuItem key={v} value={v}>{CHOICE_COPY[v] || v}</MenuItem>)}
                            </TextField>
                          ) : <TextField fullWidth size="small" label={PARAM_COPY[name] || def.label} value={keyed(rule[name])} onChange={(e) => editRule(key, name, e.target.value)} slotProps={{ htmlInput: { inputMode: 'decimal' } }} />}
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              );
            })}
            <TextField multiline minRows={2} label="Optional note about these changes" value={policyReason} onChange={(e) => { if (!policyDraft && !policyReason) policyBase.current = investor?.revision ?? null; setPolicyReason(e.target.value); }} />
            {policyError && <Alert severity="error">{policyError}</Alert>}
            <Stack direction="row" spacing={1}>
              <Button variant="contained" disabled={policyBusy || policyConflict || (!policyDraft && !policyReason)} onClick={savePolicy}>{policyBusy ? 'Saving…' : 'Save risk-check choices'}</Button>
              <Button disabled={!policyDraft && !policyReason} onClick={() => { setPolicyDraft(null); setPolicyReason(''); policyBase.current = null; }}>Discard policy edits</Button>
            </Stack>
            <Typography variant="body2" color="text.secondary">Saving a policy revision invalidates dependent approval records. Missing source data can block an applied rule; a price-fall estimate is not a guaranteed loss cap.</Typography>
            <Button onClick={() => navigate('orders')}>Saved proposals and approvals: open Orders</Button>
            <Evidence title="Policy history" data={investor.data.policy_history} />
          </Stack>
        )}
      </Section>
      <Accordion id="native-report" tabIndex={-1} disableGutters>
        <AccordionSummary>Native risk limits and cached reports</AccordionSummary>
        <AccordionDetails>
          <Typography variant="subtitle2">Actual native risk configuration</Typography>
          {riskValues ? (
            <>
              <Facts rows={[['Pre-trade checks bypassed', riskValues.bypassed ? 'Yes' : 'No'], ['Trading state', riskValues.trading_state], ['Submit rate', `${riskValues.submit_rate.commands} commands / ${riskValues.submit_rate.interval_ns} ns`], ['Modify rate', `${riskValues.modify_rate.commands} commands / ${riskValues.modify_rate.interval_ns} ns`]]} />
              <Typography variant="body2">Per-instrument order notional caps: {riskValues.max_notional_per_order.length ? riskValues.max_notional_per_order.map((c) => `${c.instrument_id} · ${c.amount === null ? 'explicitly disabled' : c.amount}`).join('; ') : 'No per-instrument caps configured'}</Typography>
            </>
          ) : <Typography variant="body2">Risk configuration unavailable: {stale ? 'last refresh failed' : risk.reason || nautilus.status || 'No current native observation'}</Typography>}
          <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>Native public getters · {risk.engine_version || 'Version unavailable'} · captured {dateTime(risk.captured_at)} · epoch {risk.native_epoch || 'Unavailable'}. Engine settings only; account approval and reconciliation remain separate.</Typography>
          <Typography variant="subtitle2">Native cached tables</Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>Capture reads the existing native cache and does not refresh a provider. Native tables are separate from broker actual performance and simulations; modeled native fees do not establish actual zero fees.</Typography>
          <Stack direction="row" spacing={1}  sx={{alignItems: "center"}}>
            <TextField select size="small" label="Table" value={reportKind} onChange={(e) => setReportKind(e.target.value)} sx={{ minWidth: 200 }}>
              {['orders', 'order_fills', 'fills', 'positions', 'account'].map((k) => <MenuItem key={k} value={k}>{k.replaceAll('_', ' ')}</MenuItem>)}
            </TextField>
            <Button onClick={capture} disabled={reportBusy || stale || nautilus.status !== 'connected'}>{reportBusy ? 'Capturing…' : 'Capture native table'}</Button>
          </Stack>
          {reportError && <Alert severity="error" sx={{ mt: 1 }}>{reportError}</Alert>}
          {nativeReport && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2">Captured {nativeReport.report_kind} · {nativeReport.row_count} rows</Typography>
              <Typography variant="body2" color="text.secondary">{reportCurrent ? 'Capture belongs to the current worker; it does not update automatically.' : 'Historical capture: worker, connection or application generation changed.'} Captured {dateTime(nativeReport.captured_at)} · epoch {nativeReport.native_epoch}</Typography>
              <Typography variant="body2" sx={{ my: 1 }}>Native table figures may include modeled position reconstruction: reduction P&amp;L, zero model commissions and processing chronology are not actual broker execution economics.</Typography>
              {nativeReport.row_count > reportRows.length && <Alert severity="info" sx={{ mb: 1 }}>Showing the first {reportRows.length} rows; the download contains the complete table.</Alert>}
              <DataTable rows={reportRows} getRowId={(r) => r.id} empty="The requested native cache table is empty. This does not establish complete broker history."
                columns={[{ id: 'index', label: (nativeReport.index_names || []).map((n) => n || 'Index').join(' / '), render: (r) => cell(r.index) }, ...nativeReport.columns.map((name, i) => ({ id: name, label: name, render: (r) => cell(r.cells[i]) }))]} />
              <Button sx={{ mt: 1 }} onClick={() => saveFile(JSON.stringify(nativeReport, null, 2), `native-${nativeReport.report_kind}.json`, 'application/json')}>Download complete captured table JSON</Button>
              <Evidence title="Capture, reconciliation and fee provenance" data={{ ...nativeReport, data: undefined, index: undefined }} />
            </Box>
          )}
        </AccordionDetails>
      </Accordion>
    </>
  );

  // Universe & Keys
  const [importPreview, setImportPreview] = useState(null);
  const [importPage, setImportPage] = useState(0);
  const [importError, setImportError] = useState('');
  const fileRef = useRef(null);
  const universeText = Array.isArray(val('universe')) ? val('universe').join(', ') : keyed(val('universe'));
  const onFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setImportError('');
    try {
      if (file.size > 1048576) throw new Error('Use a file smaller than 1 MB.');
      setImportPreview(parseSymbols(await file.text(), { file: true, preview: true }));
      setImportPage(0);
    } catch (err) { setImportError(errText(err)); }
  };
  const applyImport = (replace) => {
    const current = (() => { try { return parseSymbols(universeText, { preview: true }).symbols; } catch { return []; } })();
    const next = replace ? importPreview.symbols : [...new Set([...current, ...importPreview.symbols])];
    if (next.length > 1000) { setImportError('This workspace supports up to 1,000 stock symbols.'); return; }
    set('universe', next.join(', '));
    setImportPreview(null);
  };
  const mf = state?.maenifold || {};
  const mfStatus = mf.status || 'not_running';
  const [mfBusy, setMfBusy] = useState('');
  const mfAct = async (a) => {
    if (mfBusy) return;
    setMfBusy(a);
    try { await act('maenifold-' + a, '/api/maenifold/' + a, {}); } catch { /* reported by act */ } finally { setMfBusy(''); }
  };
  const pageRows = importPreview ? importPreview.rows.slice(importPage * 100, importPage * 100 + 100) : [];
  const integrationsPanel = (
    <Box component="form" onSubmit={(e) => { e.preventDefault(); save('Integrations'); }}>
      {conflictAlert}
      <Section title="Stock universe">
        {saveBar('Integrations')}
        <Grid container spacing={2}>
          {fld('name', 'Universe name')}
          <Grid size={{ xs: 12, md: 6 }}>
            <Button onClick={() => { set('name', 'FANGMAN'); set('universe', FANGMAN); }}>Use FANGMAN · 7 stocks</Button>
            <Typography variant="caption" display="block">Meta, Apple, NVIDIA, Alphabet, Microsoft, Amazon, Netflix.</Typography>
          </Grid>
          <Grid size={12}>
            <TextField multiline minRows={3} fullWidth required label="Stock symbols" value={universeText} onChange={(e) => set('universe', e.target.value)} helperText="Up to 1,000 symbols, separated by commas or spaces." slotProps={{ htmlInput: { spellCheck: false } }} />
            <Stack direction="row" spacing={1}  sx={{alignItems: "center",  mt: 1 }}>
              <Button onClick={() => fileRef.current?.click()}>Import CSV / text</Button>
              <input ref={fileRef} type="file" accept=".csv,.txt,text/csv,text/plain" hidden onChange={onFile} />
              <Button onClick={() => saveFile('Symbol\r\n' + (config.universe || []).join('\r\n'), 'stock-index.csv', 'text/csv;charset=utf-8')}>Export saved index</Button>
              <Typography variant="body2" role="status">{(config.universe || []).length} saved stocks</Typography>
            </Stack>
            {importError && <Alert severity="error" sx={{ mt: 1 }}>{importError}</Alert>}
          </Grid>
        </Grid>
        {importPreview && (
          <Box sx={{ mt: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="subtitle2">Universe import preview</Typography>
            <Typography variant="body2">{importPreview.symbols.length} accepted · {importPreview.rejected} rejected · {importPreview.duplicates} duplicate rows. The current universe is unchanged.</Typography>
            <DataTable rows={pageRows} getRowId={(r) => `${r.row}-${r.value}`} columns={[{ id: 'row', label: 'Row', render: (r) => r.row }, { id: 'value', label: 'Original', render: (r) => r.value }, { id: 'symbol', label: 'Symbol', render: (r) => r.symbol }, { id: 'status', label: 'Disposition / reason', render: (r) => `${r.status} · ${r.reason}` }]} />
            <Typography variant="body2" sx={{ my: 1 }}>Rows {importPreview.rows.length ? importPage * 100 + 1 : 0}–{Math.min(importPreview.rows.length, importPage * 100 + 100)} of {importPreview.rows.length}. Only accepted rows are applied to the editable draft; save settings separately to commit.</Typography>
            <Stack direction="row" spacing={1}  sx={{flexWrap: "wrap"}}>
              <Button disabled={!importPage} onClick={() => setImportPage((p) => p - 1)}>Previous rows</Button>
              <Button disabled={(importPage + 1) * 100 >= importPreview.rows.length} onClick={() => setImportPage((p) => p + 1)}>Next rows</Button>
              <Button disabled={!importPreview.symbols.length} onClick={() => applyImport(false)}>Merge accepted rows with draft universe</Button>
              <Button disabled={!importPreview.symbols.length} onClick={() => applyImport(true)}>Replace draft universe with accepted rows</Button>
              <Button onClick={() => setImportPreview(null)}>Discard import preview</Button>
            </Stack>
          </Box>
        )}
      </Section>
      <Section title="Maenifold service">
        <Grid container spacing={2}>
          {fld('maenifold_port', 'Maenifold port', { type: 'number', min: 1024, max: 65535, step: 1 })}
          {fld('maenifold_root', 'Maenifold data root', { placeholder: 'Leave blank to use the desk default folder' })}
        </Grid>
        <Typography variant="body2" role="status" sx={{ my: 1 }}>
          {mfBusy ? (mfBusy === 'start' ? 'Starting Maenifold…' : 'Stopping Maenifold…') : `Status: ${{ not_running: 'Not running', starting: 'Starting', running: 'Running', error: 'Error' }[mfStatus] || 'Unknown'} · Port ${mf.port ?? 'Unavailable'} · Data root: ${mf.root || 'Desk default folder'}${mf.pid ? ' · PID ' + mf.pid : ''}`}
        </Typography>
        {mfStatus === 'error' && mf.error && <Alert severity="error">{mf.error}</Alert>}
        <Typography variant="body2">Start uses the saved port and folder. Save any changes before starting.</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
          <Button disabled={!!mfBusy || ['starting', 'running'].includes(mfStatus)} onClick={() => mfAct('start')}>Start Maenifold</Button>
          <Button disabled={!!mfBusy || mfStatus === 'not_running'} onClick={() => mfAct('stop')}>Stop Maenifold</Button>
        </Stack>
      </Section>
      {formError && tab === 'Integrations' && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
      {credPanel('service')}
    </Box>
  );

  // Diagnostics & Backup
  const h = state?.health || {};
  const store = h.store || {};
  const stream = nautilus.trade_stream || {};
  const sourceId = [state?.server_instance_id, state?.store_generation, state?.nautilus?.connection_session].join('|');
  const [rec, setRec] = useState({ busy: false, message: '', backup: null, file: null, preview: null, confirm: '' });
  const recFile = useRef(null);
  const recRun = async (action) => {
    if (rec.busy) return;
    setRec((r) => ({ ...r, busy: true, message: action === 'preview' ? 'Inspecting archive; current records are unchanged…' : action === 'backup' ? 'Creating application backup…' : 'Restoring application records…' }));
    try {
      if (action === 'backup') { const backup = await api('/api/recovery', { action: 'backup' }); setRec((r) => ({ ...r, backup, message: 'Consistent application backup saved. Download it above.' })); }
      if (action === 'preview') {
        const f = rec.file;
        if (!f || f.size > 64 * 1024 * 1024) throw new Error('Choose an application ZIP no larger than 64 MiB.');
        const source = sourceId;
        const bytes = new Uint8Array(await f.arrayBuffer());
        let bin = '';
        for (let i = 0; i < bytes.length; i += 32768) bin += String.fromCharCode(...bytes.subarray(i, i + 32768));
        const preview = await api('/api/recovery', { action: 'preview', archive: btoa(bin) });
        setRec((r) => ({ ...r, preview, source, message: 'Archive staged for review; current records are unchanged.' }));
      }
      if (action === 'restore') {
        const result = await api('/api/recovery', { action: 'restore', token: rec.preview?.token, confirmation: rec.confirm });
        setRec((r) => ({ ...r, message: result.message, preview: null, confirm: '', file: null }));
        await refresh({fresh: true});
      }
    } catch (e) {
      setRec((r) => ({ ...r, message: `${action === 'preview' ? 'Archive inspection' : action === 'backup' ? 'Backup' : 'Restore'}: ${errText(e)}` }));
    } finally { setRec((r) => ({ ...r, busy: false })); }
  };
  const [restoreOpen, setRestoreOpen] = useState(false);
  useEffect(() => { // the staged token belongs to one server, store and connection; keep the chosen file
    if (rec.preview && rec.source !== sourceId) { setRec((r) => ({ ...r, preview: null, confirm: '', message: 'The workspace source changed; inspect the archive again.' })); setRestoreOpen(false); }
  }, [sourceId, rec.preview, rec.source]);
  const mani = rec.preview?.manifest;
  const diagnosticsPanel = (
    <>
      {(stateError || deskError) && <Alert severity="warning" sx={{ mb: 2 }}>{String(stateError || deskError)}</Alert>}
      <Section title="Diagnostics & Backup">
        <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap",  mb: 1 }}>
          {[['Engine', h.engine], ['Reconciliation', h.reconciliation?.status], ['SQLite', store.status], ['Trade stream', stream.state]].map(([k, v]) => <Chip key={k} variant="outlined" label={`${k}: ${stale ? 'Unconfirmed' : v || 'Unknown'}`} />)}
        </Stack>
        {nautilus.error && <Alert severity="error" sx={{ mb: 1 }}>{nautilus.error}</Alert>}
        {state?.readiness?.ready === false && <Alert severity="info" sx={{ mb: 1 }} action={<Button color="inherit" size="small" onClick={() => setTab('Research')}>Research settings</Button>}>{state.readiness.message || 'Research models need configuration.'}</Alert>}
        <Typography variant="body2">Current desk: {window.location.origin}. Open the installed desktop shortcut; use its tray for service restart, logs and graceful quit.</Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>{stale ? 'Transport unconfirmed' : h.execution_enabled ? 'Command transport available' : 'Command transport unavailable in this session'}. Stale observations are not current balances.</Typography>
        <Accordion disableGutters>
          <AccordionSummary>Service and observation details</AccordionSummary>
          <AccordionDetails>
            <Facts rows={[['Account mode', h.account_mode], ['Local service', stale ? 'Unconfirmed · refresh failed' : h.service], ['Engine', stale ? 'Unconfirmed · last snapshot' : h.engine], ['Engine version', h.engine_version], ['Provider / feed', `${h.provider || 'Unknown'} / ${h.feed || 'Unknown'}`], ['Account observation', h.account_observed_at], ['Prices checked', h.prices_checked_at], ['Engine heartbeat', h.runtime_heartbeat_at], ['Account import', h.reconciliation?.status || 'unknown'], ['Local Laya', layaText], ['Maenifold', h.gateway_status || 'Not requested'], ['Startup errors', (h.startup_errors || []).join('; ') || (h.gateway_status === 'checking' ? 'Checking services…' : 'None reported')], ['Local store', store.status || 'unknown'], ['Database schema', store.schema], ['Journal revision', store.journal_revision]]} />
            <ul>{(h.reconciliation?.gaps || []).map((g) => <li key={g}>{g}</li>)}</ul>
            <Evidence title="Configured capabilities" data={h.capabilities || {}} />
            <Button sx={{ mt: 1 }} onClick={() => saveFile(JSON.stringify(h, null, 2), 'tradingagents-diagnostics.json', 'application/json')}>Download diagnostics</Button>
          </AccordionDetails>
        </Accordion>
        <Accordion disableGutters>
          <AccordionSummary>Native cache and reconciliation evidence</AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" sx={{ mb: 1 }}>Official Nautilus uses an in-memory cache. SQLite application records, research, proposals and command history remain saved. Restarting never replays commands.</Typography>
            <Evidence title="Native reconciliation" data={{ status: nautilus.reconciliation?.status, epoch: nautilus.native_epoch, receipts: nautilus.native_reconstruction || {}, gaps: nautilus.reconciliation?.gaps || h.reconciliation?.gaps }} />
            <Typography variant="body2" sx={{ mt: 1 }}>If reconstruction is required, explicitly use Stop Nautilus then Start Nautilus in Account &amp; Engine to rebuild from current broker facts.</Typography>
            <Button sx={{ mt: 1 }} onClick={() => setTab('Account')}>Account &amp; Engine controls</Button>
          </AccordionDetails>
        </Accordion>
        <Accordion disableGutters>
          <AccordionSummary>Broker trade update details</AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2">{!stale && nautilus.status === 'connected' ? 'Latest worker observation' : 'Historical or unavailable worker observation'} · updates {stream.state || 'not reported'}</Typography>
            <Typography variant="body2">{stream.gap || 'No trade-stream observation recorded'}</Typography>
            {Object.entries(stream.identity_reconciliation?.unresolved || {}).map(([id, it]) => <Typography key={id} variant="body2">Command {id} · {it.reason} · attempted {dateTime(it.attempted_at)}</Typography>)}
            {(stream.identity_reconciliation?.pending || []).length > 0 && <Typography variant="body2">Orders awaiting status: {stream.identity_reconciliation.pending.join(', ')}</Typography>}
            <Button sx={{ mt: 1 }} disabled={stale || nautilus.status !== 'connected' || !!state?.browse_only} onClick={() => act('reconcile', '/api/commands/reconcile', {}).catch(() => {})}>Refresh account and order status</Button>
          </AccordionDetails>
        </Accordion>
      </Section>
      <Section title="Application backup">
        <Typography variant="body2" sx={{ mb: 1 }}>Includes the application database and referenced immutable research evidence, plus configured saved history. Credentials, environment contents and unrelated files are excluded. Active research writers must finish before backup or restore.</Typography>
        <Stack direction="row" spacing={1}  sx={{alignItems: "center"}}>
          <Button variant="outlined" disabled={rec.busy} onClick={() => recRun('backup')}>Export Workspace Backup</Button>
          {rec.backup && <Button component="a" href={`/api/backups/${encodeURIComponent(rec.backup.id)}`} download>Download saved backup</Button>}
        </Stack>
        {rec.backup && <Typography variant="caption">SHA-256 {rec.backup.sha256}</Typography>}
        {rec.busy && <LinearProgress sx={{ mt: 1 }} />}
        <Typography variant="body2" role="status" sx={{ mt: 1 }}>{rec.message}</Typography>
      </Section>
      <Section title="Danger zone: restore workspace from backup">
        <Box sx={{ border: 1, borderColor: 'error.main', borderRadius: 1, p: 2 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>Broker history is unchanged. Current records are retained before cutover. Restored approvals are invalidated, the engine stops, and fresh reconciliation and new exact approvals are required; your saved pause choice is preserved.</Typography>
          <Stack direction="row" spacing={1}  sx={{alignItems: "center"}}>
            <Button onClick={() => recFile.current?.click()}>Choose application ZIP (max 64 MiB)</Button>
            <input ref={recFile} type="file" accept=".zip,application/zip" hidden onChange={(e) => { const f = e.target.files?.[0] || null; e.target.value = ''; setRec((r) => ({ ...r, file: f, preview: null, confirm: '', message: '' })); }} />
            <Typography variant="body2">{rec.file?.name || 'No archive selected'}</Typography>
            <Button disabled={!rec.file || rec.busy} onClick={() => recRun('preview')}>Inspect restore archive</Button>
          </Stack>
          {mani && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2">Restore preview</Typography>
              <Typography variant="body2">Backup date {mani.created_at} · format {mani.version} · database {mani.database_version}</Typography>
              <Typography variant="body2">Records: {(mani.records || []).join(', ')} · {Object.keys(mani.files || {}).length} files · saved history {mani.history_included ? 'included' : 'not included'}</Typography>
              <Typography variant="body2">Archive SHA-256 {rec.preview.archive_sha256}</Typography>
              <Alert severity="warning" sx={{ my: 1 }}>{rec.preview.warning}</Alert>
              <Button color="error" variant="contained" disabled={rec.busy} onClick={() => setRestoreOpen(true)}>Restore the reviewed local records</Button>
            </Box>
          )}
        </Box>
      </Section>
      <Dialog open={restoreOpen} onClose={() => setRestoreOpen(false)}>
        <DialogTitle>Restore local records?</DialogTitle>
        <DialogContent>
          <DialogContentText>Type RESTORE LOCAL RECORDS to replace the current application records with the reviewed archive.</DialogContentText>
          <TextField autoFocus fullWidth size="small" sx={{ mt: 2 }} value={rec.confirm} onChange={(e) => setRec((r) => ({ ...r, confirm: e.target.value }))} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreOpen(false)}>Cancel</Button>
          <Button color="error" disabled={rec.confirm !== 'RESTORE LOCAL RECORDS' || rec.busy} onClick={() => { setRestoreOpen(false); recRun('restore'); }}>Restore</Button>
        </DialogActions>
      </Dialog>
    </>
  );

  const panels = { Account: accountPanel, Research: researchPanel, 'Trading rules': rulesPanel, Integrations: integrationsPanel, Diagnostics: diagnosticsPanel };
  const anyDirty = !!draft || ppDirty || !!policyDraft;
  useEffect(() => {
    const hd = (e) => { if (draft || policyDraft) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', hd);
    return () => window.removeEventListener('beforeunload', hd);
  }, [draft, policyDraft]);

  return (
    <Page title="Settings" subtitle={anyDirty ? 'You have unsaved edits; they stay here when you switch categories.' : undefined}>
      {confirmDialog}
      {!state?.config ? <LinearProgress /> : (
        <>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" aria-label="Settings categories" sx={{ mb: 2 }}>
            {TABS.map(([k, label]) => <Tab key={k} value={k} label={label} />)}
          </Tabs>
          {TABS.map(([k]) => <Box key={k} role="tabpanel" hidden={tab !== k} sx={{ display: tab === k ? 'block' : 'none' }}>{panels[k]}</Box>)}
        </>
      )}
    </Page>
  );
}

// ---------------------------------------------------------------- Workflows

const MISSION_FILE = 'prompts/investment_mission.txt';
const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$/;
const RESERVED = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i;
const promptLabel = (p) => p.replace(/^prompts\//, '').replace(/\.[^.]+$/, '').replace(/_/g, ' ');
const promptGroup = (p) => {
  const n = p.replace(/^prompts\//, '');
  if (n.startsWith('shared_')) return 'Shared context and tools';
  if (n.startsWith('schema_')) return 'Output schemas';
  if (/(conditional|memory|tool|follow|revision|no_graph)/i.test(n)) return 'Conditional fragments';
  return 'Primary and other prompts';
};
const sameFiles = (a, b) => { const ka = Object.keys(a), kb = Object.keys(b); return ka.length === kb.length && ka.every((k) => Object.hasOwn(b, k) && a[k] === b[k]); };

// Hosts a WorkflowTools (CodeMirror) editor; remounts only when editorKey changes and retains per-key editor state.
function CodeEditor({ editorKey, getText, language, label, readOnly, onChange }) {
  const host = useRef(null);
  const saved = useRef(new Map());
  const change = useRef(onChange);
  change.current = onChange;
  const text = useRef(getText);
  text.current = getText;
  useEffect(() => {
    const tools = window.WorkflowTools;
    if (!host.current || !tools?.createEditor) return undefined;
    const ed = tools.createEditor(host.current, { text: text.current(), state: saved.current.get(editorKey), language, label, readOnly, onChange: (v) => change.current(v) });
    return () => { try { saved.current.set(editorKey, ed.getState()); } catch { /* editor already gone */ } ed.destroy(); };
  }, [editorKey, language, label, readOnly]);
  return <Box ref={host} sx={{ minHeight: 320, border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'auto' }} />;
}

function Diagram({ diagram, files, onNode, selectedNode }) {
  const host = useRef(null);
  const seq = useRef(0);
  const [err, setErr] = useState('');
  const [zoom, setZoom] = useState(null);
  const [retry, setRetry] = useState(0);
  const cb = useRef(onNode);
  cb.current = onNode;
  const filesRef = useRef(files);
  filesRef.current = files;
  useEffect(() => {
    const el = host.current;
    if (!el || !diagram || !window.WorkflowTools?.renderDiagram) return undefined;
    const n = ++seq.current;
    let alive = true;
    const cs = getComputedStyle(el);
    const tok = (name, fallback) => cs.getPropertyValue(name).trim() || fallback;
    setErr('');
    window.WorkflowTools.renderDiagram('workflow-graph-' + n, diagram.mermaid, { primaryColor: tok('--paper', '#16213a'), primaryTextColor: tok('--ink', '#e8edf7'), primaryBorderColor: tok('--accent', '#3ddc84'), lineColor: tok('--muted', '#8c9ab5'), secondaryColor: tok('--accent-wash', '#12301f'), tertiaryColor: tok('--paper', '#16213a'), background: tok('--ground', cs.backgroundColor), fontFamily: cs.fontFamily })
      .then((svg) => {
        if (!alive || n !== seq.current) return;
        el.innerHTML = svg; // markup is produced by the bundled Mermaid renderer
        const s = el.querySelector('svg');
        if (s) { s.style.maxWidth = 'none'; s.style.height = 'auto'; s.dataset.natural = String(s.viewBox?.baseVal?.width || 800); }
        for (const [id, node] of Object.entries(diagram.nodes || {})) {
          const g = [...el.querySelectorAll('g.node')].find((i) => i.id === id || i.id.startsWith('flowchart-' + id + '-') || i.id.includes('-flowchart-' + id + '-'));
          if (!g) continue;
          g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button'); g.style.cursor = 'pointer';
          g.setAttribute('aria-label', `${node.name}: show details`);
          g.dataset.workflowNode = id;
          const go = () => cb.current(id);
          g.addEventListener('click', go);
          g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
        }
        setZoom((z) => z ?? 'fit');
      })
      .catch((e) => { if (alive && n === seq.current) setErr(errText(e)); });
    return () => { alive = false; };
  }, [diagram, retry]);
  useEffect(() => {
    const s = host.current?.querySelector('svg');
    if (!s) return;
    const nat = Number(s.dataset.natural) || 800;
    s.style.width = zoom === 'fit' || zoom === null ? '100%' : Math.round(nat * zoom) + 'px';
  }, [zoom, diagram]);
  useEffect(() => {
    host.current?.querySelectorAll('g.node').forEach((g) => g.setAttribute('aria-pressed', String(g.dataset.workflowNode === selectedNode)));
  }, [selectedNode, diagram]);
  const nat = () => { const s = host.current?.querySelector('svg'); return (Number(s?.dataset.natural) || 800) * (s ? s.getBoundingClientRect().width / (Number(s.dataset.natural) || 800) / 1 : 1) / (Number(s?.dataset.natural) || 800); };
  const step = (d) => setZoom((z) => { const base = typeof z === 'number' ? z : Math.max(0.15, Math.min(2, nat() || 1)); return Math.max(0.15, Math.min(2, +(base + d).toFixed(2))); });
  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
        <Button size="small" onClick={() => step(-0.2)}>Zoom out</Button>
        <Button size="small" onClick={() => step(0.2)}>Zoom in</Button>
        <Button size="small" onClick={() => setZoom('fit')}>Fit width</Button>
      </Stack>
      {err && <Alert severity="error" action={<Button size="small" color="inherit" onClick={() => setRetry((r) => r + 1)}>Retry diagram</Button>}>Unable to render the workflow: {err}</Alert>}
      <Box ref={host} sx={{ overflow: 'auto', maxHeight: 520, border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }} />
    </Box>
  );
}

export function WorkflowsView() {
  const { api, page, state } = useDesk();
  const [cat, setCat] = useState({ names: [], active: '', loaded: false });
  const [selected, setSelected] = useState('');
  const [bundle, setBundle] = useState(null);
  const [files, setFiles] = useState({});
  const [saved, setSaved] = useState({});
  const [epoch, setEpoch] = useState(0);
  const [diagram, setDiagram] = useState(null);
  const [diagramFiles, setDiagramFiles] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ text: '', error: false });
  const [view, setView] = useState('prompts');
  const [prompt, setPrompt] = useState('');
  const [search, setSearch] = useState('');
  const [node, setNode] = useState('');
  const [previewMsg, setPreviewMsg] = useState('');
  const [saveAs, setSaveAs] = useState(null);
  const [pending, setPending] = useState(null);
  const [toolsTick, setToolsTick] = useState(0);

  const dirty = bundle ? !sameFiles(files, saved) : false;
  const toolsReady = typeof window.WorkflowTools?.createEditor === 'function' && typeof window.WorkflowTools?.renderDiagram === 'function';
  void toolsTick;

  useEffect(() => {
    const h = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [dirty]);

  const loadCatalog = useCallback(async () => {
    try {
      const r = await api('/api/workflows');
      setCat({ names: r.workflows, active: r.active || '', loaded: true });
      setSelected((s) => s || r.active || r.workflows[0] || '');
    } catch (e) { setCat((c) => ({ ...c, loaded: true })); setMsg({ text: errText(e), error: true }); }
  }, [api]);
  const started = useRef(false);
  useEffect(() => { if (page === 'workflows' && !started.current) { started.current = true; loadCatalog(); } }, [page, loadCatalog]);

  const adopt = (r, text) => {
    setBundle(r); setFiles({ ...r.files }); setSaved({ ...r.files }); setSelected(r.name);
    setDiagram(r.diagram || null); setDiagramFiles(JSON.stringify(r.files));
    setPrompt((p) => (Object.hasOwn(r.files, p) && p !== MISSION_FILE ? p : Object.keys(r.files).filter((k) => k !== 'workflow.yaml' && k !== MISSION_FILE).sort()[0] || ''));
    if (r.active !== undefined) setCat((c) => ({ ...c, active: r.active || '' }));
    setEpoch((n) => n + 1); setNode('');
    setMsg({ text, error: false });
  };
  const failure = (e) => setMsg({ text: e.status === 409 ? `This workflow changed in another session. Your draft is still here. Use Save as to preserve your complete draft as a new workflow, or discard it and load the latest version. ${errText(e)}` : errText(e), error: true });

  const doLoad = async (name) => {
    setBusy(true);
    try { adopt(await api('/api/workflows?name=' + encodeURIComponent(name)), 'Workflow loaded.'); } catch (e) { failure(e); } finally { setBusy(false); }
  };
  const guarded = (fn, title) => { if (dirty) setPending({ fn, title }); else fn(); };

  const act = async (action, name) => {
    if (!bundle || busy) return;
    if (action === 'activate' && dirty) { setMsg({ text: 'Save or discard changes before selecting this workflow for new research.', error: true }); return; }
    const body = action === 'activate' ? { action, name: bundle.name, revision: bundle.revision } : action === 'save_as' ? { action, name, files } : { action, name: bundle.name, files, revision: bundle.revision };
    setBusy(true);
    try {
      const r = await api('/api/workflows', body);
      adopt(r, (action === 'activate' ? 'Selected for new research.' : 'Workflow saved.') + (r.warning ? ' ' + r.warning : ''));
      setCat((c) => ({ ...c, names: c.names.includes(r.name) ? c.names : [...c.names, r.name].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())) }));
      setSaveAs(null);
    } catch (e) { failure(e); if (action === 'save_as') setSaveAs((s) => ({ ...s, error: errText(e) })); } finally { setBusy(false); }
  };

  const submitSaveAs = () => {
    const name = saveAs.name;
    const bad = !NAME_RE.test(name) || / $/.test(name) ? 'Use 1–64 letters, numbers, spaces, underscores or hyphens; start with a letter or number.' : RESERVED.test(name) ? 'Choose a different workflow name.' : '';
    if (bad) { setSaveAs({ ...saveAs, error: bad }); return; }
    act('save_as', name);
  };

  const preview = async () => {
    if (!bundle) return;
    const snap = JSON.stringify(files), snapFiles = { ...files };
    setPreviewMsg('Validating draft…');
    try {
      const r = await api('/api/workflows', { action: 'preview', files: snapFiles });
      setDiagram(r.diagram); setDiagramFiles(snap); setPreviewMsg('');
    } catch (e) { setPreviewMsg('Preview unavailable: ' + errText(e)); }
  };
  const previewState = !diagram ? 'No preview yet' : diagramFiles !== JSON.stringify(files) ? 'Preview is stale' : dirty ? 'Preview of draft' : 'Preview of loaded workflow';

  const discard = () => { setFiles({ ...saved }); setEpoch((n) => n + 1); setMsg({ text: 'Changes discarded.', error: false }); };

  const setMission = (v) => setFiles((f) => {
    const next = { ...f };
    if (!v && !Object.hasOwn(saved, MISSION_FILE)) delete next[MISSION_FILE]; else next[MISSION_FILE] = v;
    return next;
  });

  const promptPaths = useMemo(() => Object.keys(files).filter((p) => p !== 'workflow.yaml' && p !== MISSION_FILE).sort(), [files]);
  const grouped = useMemo(() => {
    const q = search.trim().toLowerCase(), g = {};
    promptPaths.filter((p) => !q || `${p} ${promptLabel(p)}`.toLowerCase().includes(q)).forEach((p) => (g[promptGroup(p)] ||= []).push(p));
    return g;
  }, [promptPaths, search]);
  const nodeInfo = diagram?.nodes?.[node];
  const nodeFiles = (list) => (list || []).filter((i) => Object.hasOwn(files, i.file));
  const groups = nodeInfo?.prompt_groups || {};
  const agent = nodeFiles(groups.agent || (nodeInfo?.prompt_files || []).map((file, i) => ({ file, description: i ? 'Related agent prompt' : 'Primary prompt' })));
  const onNode = (id) => {
    setNode(id);
    const first = (diagram?.nodes?.[id]?.prompt_files || []).find((f) => Object.hasOwn(saved, f) || Object.hasOwn(files, f));
    if (first && first !== MISSION_FILE) { setView('prompts'); setPrompt(first); }
  };
  const missionRoles = bundle?.mission_roles || {};
  const mission = files[MISSION_FILE] || '';

  return (
    <Page title="Workflows" subtitle="Inspect and edit the workflow used for research."
      actions={<Stack direction="row" spacing={1}  sx={{alignItems: "center"}}><Typography variant="body2">Active: <strong>{cat.active || 'None selected'}</strong></Typography></Stack>}>
      <Dialog open={!!pending} onClose={() => setPending(null)}>
        <DialogTitle>{pending?.title || 'Discard unsaved workflow changes?'}</DialogTitle>
        <DialogContent><DialogContentText>Your unsaved draft will be replaced. Saved workflows are not changed.</DialogContentText></DialogContent>
        <DialogActions>
          <Button autoFocus onClick={() => setPending(null)}>Keep editing</Button>
          <Button color="warning" onClick={() => { const f = pending.fn; setPending(null); f(); }}>{pending?.yes || 'Discard changes'}</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={!!saveAs} onClose={() => setSaveAs(null)}>
        <DialogTitle>Save as a new workflow</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth margin="dense" label="New workflow name" value={saveAs?.name || ''} error={!!saveAs?.error} helperText={saveAs?.error} onChange={(e) => setSaveAs({ name: e.target.value, error: '' })} onKeyDown={(e) => { if (e.key === 'Enter') submitSaveAs(); }} />
        </DialogContent>
        <DialogActions><Button onClick={() => setSaveAs(null)}>Cancel</Button><Button variant="contained" disabled={busy} onClick={submitSaveAs}>Save copy</Button></DialogActions>
      </Dialog>

      <Stack spacing={2}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}  sx={{alignItems: { md: 'center' }}}>
          <TextField select size="small" label="Load saved workflow" value={selected} onChange={(e) => setSelected(e.target.value)} disabled={busy} sx={{ minWidth: 260 }}>
            {cat.names.map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
          </TextField>
          <Button variant={bundle ? 'outlined' : 'contained'} disabled={busy || !selected} onClick={() => guarded(() => doLoad(selected), 'Discard unsaved changes and load another workflow?')}>{bundle ? 'Load' : `Load ${selected || 'Default'} workflow`}</Button>
          <Button disabled={busy} onClick={() => guarded(loadCatalog, 'Refresh the list?')}>Refresh list</Button>
          <Typography variant="body2">Editing: <strong>{bundle?.name || 'None'}</strong></Typography>
        </Stack>
        {busy && <LinearProgress />}
        {msg.text && <Alert severity={msg.error ? 'error' : 'success'} role="status">{msg.text}</Alert>}
        {!toolsReady && <Alert severity="warning" action={<Button color="inherit" size="small" onClick={() => setToolsTick((n) => n + 1)}>Try again</Button>}>Editor tools are not available. Your draft is preserved; the diagram and code editors need the bundled workflow tools.</Alert>}
        {!bundle ? (
          <Box sx={{ p: 3, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="h6">Load a research workflow</Typography>
            <Typography variant="body2">The workflow shows the agent flow, role-grouped prompt templates, and the stage and debate round limits in workflow.yaml. It shapes how analysts, bull and bear researchers, the trader, and risk debaters run on future research cycles. Loading it does not start a run.</Typography>
          </Box>
        ) : (
          <>
            <Stack direction="row" spacing={1}  useFlexGap  sx={{flexWrap: "wrap", alignItems: "center"}}>
              <Chip color={dirty ? 'warning' : 'default'} label={dirty ? 'Unsaved changes' : 'Saved workflow'} />
              <Button variant="contained" disabled={busy || !dirty} onClick={() => act('save')}>Save</Button>
              <Button disabled={busy} onClick={() => setSaveAs({ name: bundle.name, error: '' })}>Save as</Button>
              <Button disabled={busy || !dirty} onClick={() => setPending({ fn: discard })}>Discard changes</Button>
              <Button disabled={busy || dirty || cat.active === bundle.name} onClick={() => act('activate')}>Use for new research</Button>
            </Stack>

            <Accordion disableGutters>
              <AccordionSummary>Shared investment mission</AccordionSummary>
              <AccordionDetails>
                <Typography variant="body2" sx={{ mb: 1 }}>Optional. An empty mission adds no instructions. Changes are a workflow draft until Save; existing role prompts remain unchanged. Saving does not start research or select another workflow.</Typography>
                <TextField multiline minRows={5} fullWidth label="Mission" value={mission} onChange={(e) => setMission(e.target.value)} />
                <Typography variant="body2" sx={{ my: 1 }}>{mission === (saved[MISSION_FILE] || '') ? 'Matches saved mission.' : 'Mission changed in this draft.'}</Typography>
                {Object.entries(missionRoles).map(([role, path]) => (
                  <Evidence key={role} title={`${role.replaceAll('_', ' ')} · effective instruction template`} data={(mission.trim() ? 'Shared investment mission:\n' + mission.trim() + '\n\nRole instructions:\n' : '') + (files[path] || '')} />
                ))}
              </AccordionDetails>
            </Accordion>

            <Box>
              <Stack direction="row" spacing={1}  sx={{alignItems: "center",  mb: 1 }}>
                <Button size="small" variant="outlined" disabled={!toolsReady} onClick={preview}>Preview draft</Button>
                <Typography variant="body2" role="status">{previewState}{previewMsg ? ' · ' + previewMsg : ''}</Typography>
              </Stack>
              {diagram && toolsReady && <Diagram diagram={diagram} files={files} onNode={onNode} selectedNode={node} />}
              {!diagram && <Typography variant="body2" color="text.secondary">No diagram for this workflow yet. Use Preview draft.</Typography>}
              <Box aria-live="polite" sx={{ mt: 1 }}>
                {nodeInfo ? (
                  <>
                    <Typography variant="subtitle2" title={nodeInfo.caption || ''}>{nodeInfo.name}</Typography>
                    <Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap"}}>
                      {agent.length ? agent.map((i) => <Chip key={i.file} clickable color={i.file === prompt ? 'primary' : 'default'} label={promptLabel(i.file)} title={i.description} onClick={() => { setView('prompts'); setPrompt(i.file); }} />) : <Typography variant="body2">No agent-specific prompt file.</Typography>}
                    </Stack>
                    {[['Shared context and tools', nodeFiles(groups.shared)], ['Output schema fields', nodeFiles(groups.schema)]].filter(([, l]) => l.length).map(([label, l]) => (
                      <Accordion key={label} disableGutters><AccordionSummary>{label} ({l.length})</AccordionSummary><AccordionDetails><Stack direction="row" spacing={1}  useFlexGap sx={{flexWrap: "wrap"}}>{l.map((i) => <Chip key={i.file} clickable label={promptLabel(i.file)} title={i.description} onClick={() => { setView('prompts'); setPrompt(i.file); }} />)}</Stack></AccordionDetails></Accordion>
                    ))}
                  </>
                ) : <Typography variant="body2" color="text.secondary">Select an agent node in the diagram (click, or press Enter or Space) to inspect its primary prompt, shared context fragments and output schema.</Typography>}
              </Box>
            </Box>

            <Tabs value={view} onChange={(_, v) => setView(v)} aria-label="Workflow inspector">
              <Tab value="prompts" label="Prompts" />
              <Tab value="yaml" label="workflow.yaml" />
            </Tabs>
            {view === 'prompts' && (
              <Stack spacing={1}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                  <TextField size="small" label="Filter prompts" value={search} onChange={(e) => setSearch(e.target.value)} sx={{ minWidth: 220 }} />
                  <FormControl size="small" sx={{ minWidth: 320 }}>
                    <InputLabel id="wf-prompt-label">Prompt file</InputLabel>
                    <Select labelId="wf-prompt-label" label="Prompt file" value={Object.values(grouped).flat().includes(prompt) ? prompt : ''} onChange={(e) => setPrompt(e.target.value)}>
                      {Object.entries(grouped).flatMap(([g, list]) => [<MenuItem key={g} disabled dense sx={{ opacity: 1, fontWeight: 600 }}>{g}</MenuItem>, ...list.map((p) => <MenuItem key={p} value={p}>{promptLabel(p)}</MenuItem>)])}
                    </Select>
                  </FormControl>
                </Stack>
                {prompt && Object.hasOwn(files, prompt) ? (
                  <>
                    <Typography variant="caption">{prompt} — an individual file; runtime may combine it with other fragments.</Typography>
                    {toolsReady && <CodeEditor editorKey={`p:${prompt}:${epoch}`} getText={() => files[prompt] ?? ''} language="markdown" label="Prompt contents" readOnly={busy} onChange={(v) => setFiles((f) => ({ ...f, [prompt]: v }))} />}
                  </>
                ) : <Typography variant="body2">No prompt selected.</Typography>}
              </Stack>
            )}
            {view === 'yaml' && toolsReady && <CodeEditor editorKey={`y:${epoch}`} getText={() => files['workflow.yaml'] ?? ''} language="yaml" label="Workflow definition YAML" readOnly={busy} onChange={(v) => setFiles((f) => ({ ...f, 'workflow.yaml': v }))} />}
          </>
        )}
      </Stack>
    </Page>
  );
}


// Recovery-only startup surface: archive preview and deliberate restore only.
export function RecoveryView() {
  const { state, api, refresh } = useDesk();
  const [file, setFile] = useState(null);
  const [candidate, setCandidate] = useState(null);
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [finished, setFinished] = useState(false);
  const done = finished || state?.health?.restart_required === true;
  const run = async (action) => {
    if (busy || done) return;
    setBusy(true);
    try {
      if (action === 'preview') {
        setCandidate(null);
        if (!file || file.size > 64 * 1024 * 1024) throw new Error('Choose a backup ZIP no larger than 64 MiB');
        const bytes = new Uint8Array(await file.arrayBuffer());
        let bin = '';
        for (let i = 0; i < bytes.length; i += 32768) bin += String.fromCharCode(...bytes.subarray(i, i + 32768));
        setCandidate(await api('/api/recovery', { action: 'preview', archive: btoa(bin) }));
        setMessage('Archive inspected. Review the manifest and checksum before confirming.');
      } else {
        const r = await api('/api/recovery', { action: 'restore', token: candidate?.token, confirmation: confirm });
        setFinished(r.restart_required === true);
        setMessage(r.message || '');
        setConfirm('');
        if (r.promoted) window.location.reload(); else refresh({fresh: true}).catch(() => {});
      }
    } catch (e) { setMessage(errText(e)); } finally { setBusy(false); }
  };
  return (
    <Page title="Recovery" subtitle="Startup recovery: the engine, research and data operations are unavailable. Preview a backup archive and restore it deliberately.">
      <Stack spacing={2}>
        <Evidence title="Startup health" data={state?.health || {}} />
        <Stack direction="row" spacing={1}  sx={{alignItems: "center"}}>
          <Button component="label" disabled={busy || done}>Choose backup ZIP (max 64 MiB)
            <input type="file" hidden accept=".zip,application/zip" onChange={(e) => { setFile(e.target.files?.[0] || null); e.target.value = ''; setCandidate(null); setMessage(''); }} />
          </Button>
          <Typography variant="body2">{file?.name || 'No archive selected'}</Typography>
          <Button variant="outlined" disabled={busy || done || !file} onClick={() => run('preview')}>Inspect archive</Button>
        </Stack>
        {candidate && <Evidence title="Archive manifest and checksum" data={candidate} />}
        <TextField size="small" label="Type RESTORE LOCAL RECORDS to confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} disabled={busy || done} />
        <Box><Button color="error" variant="contained" disabled={busy || done || !candidate || confirm !== 'RESTORE LOCAL RECORDS'} onClick={() => run('restore')}>Restore the reviewed local records</Button></Box>
        {busy && <LinearProgress />}
        {done && <Alert severity="info">Restore finished. Restart the desk to continue.</Alert>}
        <Typography role="status" variant="body2">{message}</Typography>
      </Stack>
    </Page>
  );
}
