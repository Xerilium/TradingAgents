import React, {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState} from 'react';

const DeskContext = createContext(null);
export const pages = {
  spy: 'SPY portfolio', overview: 'Dashboard', portfolio: 'Portfolio', markets: 'Markets',
  research: 'Research', orders: 'Orders', strategy: 'Strategy lab', journal: 'Journal',
  alerts: 'Alerts', workflows: 'Workflows', settings: 'Settings',
};
const currentPage = () => Object.hasOwn(pages, location.hash.slice(1)) ? location.hash.slice(1) : 'spy';

export function DeskProvider({children}) {
  const [snapshot, setSnapshot] = useState(null);
  const [stateError, setStateError] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(new Set());
  const [page, setPage] = useState(currentPage);
  const [navigation, setNavigation] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState(new URLSearchParams(location.search).get('symbol') || '');
  const latest = useRef(null), csrf = useRef(''), flight = useRef(null);
  const locks = useRef(new Set()), limited = useRef(new Map());

  const api = useCallback(async (path, body, {timeoutMs = body === undefined ? 30000 : 550000, signal} = {}) => {
    if (!path.startsWith('/api/') || path.includes('://')) throw new Error('Only local desk API routes are supported.');
    const scope = path.split('?')[0] + ':' + (body?.action || '');
    const retryAt = limited.current.get(scope);
    if (retryAt > Date.now()) throw new Error(`Request rate limited. Try again after ${new Date(retryAt).toLocaleTimeString()}.`);
    const controller = new AbortController();
    const abort = () => controller.abort(signal.reason);
    if (signal?.aborted) abort();
    signal?.addEventListener('abort', abort, {once: true});
    const timer = setTimeout(() => controller.abort(new Error('Request timed out.')), timeoutMs);
    try {
      const options = {
        method: body === undefined ? 'GET' : 'POST', signal: controller.signal, cache: 'no-store',
        headers: body === undefined ? {Accept: 'application/json'} :
          {'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': csrf.current},
        ...(body === undefined ? {} : {body: JSON.stringify(body)}),
      };
      let response = await fetch(path, options);
      if (response.status === 403 && body === undefined) {
        const session = await fetch('/', {cache: 'no-store', signal: controller.signal});
        if (session.ok) response = await fetch(path, options);
      }
      if (response.status === 429) {
        const retry = response.headers.get('Retry-After');
        const until = retry && Number.isFinite(Number(retry)) ? Date.now() + Math.max(1, Number(retry)) * 1000 :
          retry && Number.isFinite(Date.parse(retry)) ? Date.parse(retry) : Date.now() + 30000;
        limited.current.set(scope, until);
      }
      const result = response.headers.get('Content-Type')?.includes('application/json') ? await response.json() : await response.blob();
      if (!response.ok) {
        const failure = new Error(result?.error || `Desk request failed (${response.status}).`);
        failure.status = response.status;
        failure.spyPreviewNotQueued = result?.spy_preview_not_queued === true;
        throw failure;
      }
      return result;
    } catch (failure) {
      if (body !== undefined && !failure.status) {
        throw new Error(`${failure.message} The operation may have reached the service. Check current status before retrying; no automatic retry was made.`, {cause: failure});
      }
      throw failure;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }, []);

  const refresh = useCallback(({fresh = false} = {}) => {
    if (flight.current) {
      if (!fresh) return flight.current;
      return flight.current.then(() => refresh(), () => refresh());
    }
    flight.current = (async () => {
      try {
        const fresh = await api('/api/state?compact=1');
        const previous = latest.current;
        if (previous?.server_instance_id === fresh.server_instance_id &&
            Number.isInteger(previous?.snapshot_sequence) && fresh.snapshot_sequence <= previous.snapshot_sequence) {
          setStateError('');
          return previous;
        }
        csrf.current = fresh.csrf_token || '';
        const {csrf_token, ...data} = fresh;
        latest.current = data;
        setSnapshot(data);
        setStateError('');
        return data;
      } catch (failure) {
        setStateError(failure.message);
        throw failure;
      } finally {
        flight.current = null;
      }
    })();
    return flight.current;
  }, [api]);

  useEffect(() => {
    let active = true, timer;
    const poll = async () => {
      try { await refresh(); } catch { /* The persistent connection alert owns this failure. */ }
      if (active) timer = setTimeout(poll, 5000);
    };
    poll();
    return () => {active = false; clearTimeout(timer);};
  }, [refresh]);

  const act = useCallback(async (key, path, body) => {
    if (locks.current.has(key)) throw new Error('This action is already pending.');
    locks.current.add(key);
    setPending(new Set(locks.current));
    setError('');
    try {
      const result = await api(path, body);
      try {
        await refresh({fresh: true});
      } catch (failure) {
        setError(`The request completed, but the updated workspace could not be read: ${failure.message}. Check current status before repeating the action.`);
      }
      return result;
    } catch (failure) {
      setError(failure.message);
      throw failure;
    } finally {
      locks.current.delete(key);
      setPending(new Set(locks.current));
    }
  }, [api, refresh]);

  useEffect(() => {
    const change = () => setPage(currentPage());
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  const navigate = useCallback((next, intent = null) => {
    if (!Object.hasOwn(pages, next)) throw new Error('Unknown workspace.');
    setNavigation(intent === null ? null : {id: crypto.randomUUID(), page: next, intent});
    location.hash = next;
    setPage(next);
  }, []);
  const clearNavigation = useCallback(id => setNavigation(current => current?.id === id ? null : current), []);
  const state = useMemo(() => !snapshot || !stateError ? snapshot : {
    ...snapshot, connection: {...snapshot.connection, connected: false, account_verified: false},
    nautilus: {...snapshot.nautilus, status: 'stale'},
  }, [snapshot, stateError]);
  const value = useMemo(() => ({state, stateError, api, act, refresh, pending, error, setError, page,
    navigate, navigation, clearNavigation, selectedSymbol, setSelectedSymbol}),
  [state, stateError, api, act, refresh, pending, error, page, navigate, navigation, clearNavigation, selectedSymbol]);
  return <DeskContext.Provider value={value}>{children}</DeskContext.Provider>;
}

export function useDesk() {
  const value = useContext(DeskContext);
  if (!value) throw new Error('Desk components require DeskProvider.');
  return value;
}
