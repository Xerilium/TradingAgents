import React, {Component, useEffect, useRef, useState} from 'react';
import {Alert, Autocomplete, Box, Button, Divider, Drawer, LinearProgress, Link, List, ListItemButton,
  ListItemText, Stack, TextField, Toolbar, Typography} from '@mui/material';
import {pages, useDesk} from './DeskContext.jsx';
import {dateTime, Status} from './ui.jsx';
import {SpyView, DashboardView, PortfolioView, OrdersView} from './TradingViews.jsx';
import {MarketsView, ResearchView} from './ResearchMarkets.jsx';
import {RecoveryView, SettingsView, WorkflowsView} from './SettingsWorkflows.jsx';
import {StrategyView, JournalView, AlertsView} from './LabJournalAlerts.jsx';

const views = {spy: SpyView, overview: DashboardView, portfolio: PortfolioView, markets: MarketsView,
  research: ResearchView, orders: OrdersView, settings: SettingsView, workflows: WorkflowsView,
  strategy: StrategyView, journal: JournalView, alerts: AlertsView};

class WorkspaceBoundary extends Component {
  state = {error: null};
  static getDerivedStateFromError(error) {return {error};}
  render() {
    return this.state.error ? <Alert severity="error" action={<Button onClick={() => this.setState({error: null})}>Retry view</Button>}>
      This workspace could not render: {this.state.error.message}. Local drafts have not been submitted.
    </Alert> : this.props.children;
  }
}

export default function App() {
  const {state, stateError, error, setError, page, navigate, refresh, pending, selectedSymbol, setSelectedSymbol} = useDesk();
  const [visited, setVisited] = useState(() => new Set([page]));
  const symbolInput = useRef(null);
  useEffect(() => setVisited(previous => previous.has(page) ? previous : new Set([...previous, page])), [page]);
  useEffect(() => {
    const shortcut = event => {
      if (event.isComposing || event.altKey || document.querySelector('[role="dialog"]')) return;
      const editing = event.target.closest?.('input,textarea,select,[contenteditable="true"],.cm-editor');
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' ||
          !editing && !event.ctrlKey && !event.metaKey && event.key === '/') {
        event.preventDefault();
        symbolInput.current?.focus();
      }
    };
    document.addEventListener('keydown', shortcut);
    return () => document.removeEventListener('keydown', shortcut);
  }, []);
  const symbols = [...new Set([...(state?.config?.universe || []),
    ...(state?.positions || []).map(position => position.symbol),
    ...Object.keys(state?.investor?.instruments || {})])].filter(Boolean);
  if (state?.recovery_only === true) return <Box sx={{height: '100%', overflow: 'auto'}}>
    {stateError && <Alert severity="error">{stateError}</Alert>}
    {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
    <WorkspaceBoundary><RecoveryView/></WorkspaceBoundary>
  </Box>;
  return <Box sx={{display: 'flex', height: '100%', minWidth: 0}}>
    <Link href="#main" onClick={event => {event.preventDefault(); document.getElementById('main')?.focus();}}
      sx={{position: 'absolute', top: -80, zIndex: 1500, '&:focus': {top: 8, left: 220}, bgcolor: 'background.paper', p: 1}}>Skip to workspace</Link>
    <Drawer variant="permanent" sx={{width: 208, flexShrink: 0, '& .MuiDrawer-paper': {width: 208, boxSizing: 'border-box', bgcolor: '#101a23'}}}>
      <Toolbar><Typography variant="h2">Printer</Typography></Toolbar>
      <Divider/>
      <List component="nav" aria-label="Workspaces">
        {Object.entries(pages).map(([id, label]) => <ListItemButton component="a" href={`#${id}`} key={id} selected={page === id}
          aria-current={page === id ? 'page' : undefined} onClick={event => {event.preventDefault(); navigate(id);}}>
          <ListItemText primary={label}/>
        </ListItemButton>)}
      </List>
      <Stack spacing={1} sx={{mt: 'auto', p: 2}}>
        <Typography variant="caption">Research: TradingAgents</Typography>
        <Status value={state?.nautilus?.status || 'Connecting'}/>
        <Typography variant="caption">Account {state?.nautilus?.reconciliation?.status === 'refreshing' ? 'refreshing' :
          state?.connection?.account_verified ? 'verified' : 'unverified'}</Typography>
      </Stack>
    </Drawer>
    <Box sx={{display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1, height: '100%'}}>
      <Toolbar sx={{gap: 2, flexWrap: 'wrap', borderBottom: 1, borderColor: 'divider', py: 1}}>
        <Typography sx={{mr: 'auto'}}>{state?.config?.name || 'Trading desk'} / {pages[page]}</Typography>
        <Autocomplete size="small" sx={{width: 220}} options={symbols} value={selectedSymbol || null}
          onChange={(_, symbol) => {setSelectedSymbol(symbol || ''); if (symbol) navigate('markets', {symbol});}}
          renderInput={params => <TextField {...params} inputRef={symbolInput} label="Find symbol"
            slotProps={{...params.slotProps, htmlInput: {...params.slotProps.htmlInput, 'aria-keyshortcuts': 'Control+k Meta+k /'}}}/>}/>
        <Status value={state?.nautilus?.reconciliation?.status}/>
        <Typography variant="caption">Observed {dateTime(state?.nautilus?.account_at)}</Typography>
        <Button onClick={() => navigate('orders')}>Orders: {state?.trading_paused ? 'Paused' : state ? 'Manage' : 'Unconfirmed'}</Button>
        <Button onClick={() => navigate('alerts')}>Alerts</Button>
        <Button onClick={() => refresh().catch(failure => setError(failure.message))}>Refresh</Button>
      </Toolbar>
      {pending.size > 0 && <LinearProgress aria-label="Desk action pending"/>}
      {stateError && <Alert severity="error">Connection unconfirmed. Showing the last snapshot: {stateError}</Alert>}
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Box component="main" id="main" tabIndex={-1} sx={{flex: 1, minHeight: 0, minWidth: 0, overflow: 'hidden'}}>
        {!state ? <Stack spacing={2} sx={{p: 3}}><Typography variant="h1">Opening your trading desk</Typography>
          <LinearProgress/><Typography>Connecting to the local Printer service.</Typography></Stack> :
          Object.entries(views).filter(([id]) => visited.has(id)).map(([id, View]) =>
            <Box key={id} hidden={page !== id} sx={{height: '100%', overflow: 'auto'}}><WorkspaceBoundary><View/></WorkspaceBoundary></Box>)}
      </Box>
    </Box>
  </Box>;
}
