'use strict';

const $ = (selector, base = document) => base.querySelector(selector);
const $$ = (selector, base = document) => [...base.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const number = value => value === null || value === undefined || typeof value==='boolean' || typeof value==='string'&&!value.trim() ? null : Number.isFinite(Number(value)) ? Number(value) : null;
const money = value => number(value) === null ? '—' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:2}).format(Number(value));
const count = value => number(value) === null ? '—' : new Intl.NumberFormat('en-US', {maximumFractionDigits:6}).format(Number(value));
const percent = value => number(value) === null ? '—' : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
const color = value => number(value) === null || Number(value) === 0 ? '' : Number(value) > 0 ? 'positive' : 'negative';
const time = value => {if(!value)return '—'; const d=new Date(typeof value==='number'&&value<1e12?value*1000:value); return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});};
const date = value => {if(!value)return '—';const d=new Date(typeof value==='number'&&value<1e12?value*1000:value);return Number.isNaN(d.getTime())?'—':d.toLocaleDateString([], {month:'short',day:'numeric'});};
const barDate = value => {const match=String(value||'').match(/^(\d{4})-(\d{2})-(\d{2})/);return match?new Date(Number(match[1]),Number(match[2])-1,Number(match[3])).toLocaleDateString([], {month:'short',day:'numeric'}):date(value);};
const text = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const iconPaths = {overview:'M3 3h7v8H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 15h7v6H3z',research:'M9 3h6M10 3v6l-6 9a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-6-9V3M8 15h8',orders:'M8 3h8v4H8zM8 5H5v16h14V5h-3M8 12h8M8 16h5',settings:'M4 7h16M4 17h16M8 4v6M16 14v6',play:'m9 5 11 7-11 7z',chart:'M3 3v18h18M7 14l4-4 4 2 5-7',arrow:'M5 12h14m-6-6 6 6-6 6',stop:'M6 6h12v12H6z',check:'m5 12 4 4L19 6',link:'m9 15 6-6M8 17l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M16 7l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',download:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4'};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${iconPaths[name]||iconPaths.overview}"/></svg>`;
const companies = {META:'Meta Platforms',AAPL:'Apple',NVDA:'NVIDIA',GOOGL:'Alphabet',GOOG:'Alphabet',MSFT:'Microsoft',AMZN:'Amazon',NFLX:'Netflix',AMD:'AMD',AVGO:'Broadcom',TSLA:'Tesla',INTC:'Intel'};
const reportNames = {market_report:'Market analysis',sentiment_report:'Sentiment analysis',news_report:'News analysis',fundamentals_report:'Fundamentals',investment_plan:'Research committee decision',trader_investment_plan:'Trader proposal',final_trade_decision:'Portfolio decision',investment_debate_state:'Bull / bear debate',risk_debate_state:'Risk committee',decision:'Decision'};
let state = null;
let quoteRefreshAt = 0, quoteRefreshPaused = false;

async function refreshQuotes({manual=false}={}) {
  if(!state?.connection?.connected){if(manual)setError('Quotes unavailable while disconnected. Start the gateway, then use Refresh to reconnect.');return;}
  if(document.hidden||busy.size||stateFetch||coolingDown()||!state?.connection?.connected)return;
  if(!manual&&(quoteRefreshPaused||Date.now()<quoteRefreshAt))return;
  quoteRefreshAt=Date.now()+60000;
  busy.add('quotes');
  render();
  try {
    const fresh=await api('/api/quotes/refresh',{}, {timeoutMs:50000});
    for(const key of ['quotes','clock','quotes_updated_at'])state[key]=fresh[key];
    quoteRefreshPaused=false;
    if(manual)errorMessage='';
    render();
  } catch(e) {
    quoteRefreshPaused=true;
    setError(`Quote updates paused: ${e.message} Use Update quotes to retry.`);
  } finally {busy.delete('quotes');render();}
}

function quoteStatus(q){
  const status=DeskLists.quoteState(q,Date.now(),state.clock);
  if(status==='missing')return 'Missing price';
  const observed=`${date(q.timestamp)} ${time(q.timestamp)}`;
  if(status==='closed')return `Last trade · Market closed · ${observed}`;
  if(status==='unverified')return `Last trade · session unverified · ${observed}`;
  if(status==='unknown')return `Last trade · market status unknown · ${observed}`;
  if(status==='stale')return `Stale last trade · ${observed}`;
  return `${q.invalid_quote?'Bid/ask unavailable · ':''}Last trade ${observed}`;
}
let activePage = ['overview','research','orders','settings'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
let selectedSymbols = new Set();
let selectedSymbol = '';
let selectedRunId = '';
let busy = new Set();
const pendingCancellations = new Set();
let errorMessage = '';
let toastTimer;
let stateFetch = false;
let stateWait=null,stateDone=null;
let settingsDirty = false;
let settingsDraft = null;
function captureSettingsDraft(){const form=$('#settings-form');if(!form)return;settingsDraft=Object.fromEntries(new FormData(form));settingsDirty=true;}
let openReportNames = new Set();
const reportViews = new Map();
let reportViewKey = '';
function reportReadingAnchor(panel){
  if(!panel?.querySelectorAll||!panel.getBoundingClientRect)return null;
  const top=panel.getBoundingClientRect().top;
  for(const report of panel.querySelectorAll('.report-section[open]')){
    const nodes=[...report.querySelectorAll('p,pre,summary')];
    const index=nodes.findIndex(node=>node.getBoundingClientRect().bottom>top&&node.getBoundingClientRect().height>0);
    if(index>=0)return {report:report.dataset.report,index,offset:nodes[index].getBoundingClientRect().top-top};
  }
  return null;
}
function restoreReadingAnchor(panel,anchor){
  if(!panel||!anchor)return;
  const report=[...panel.querySelectorAll('.report-section')].find(node=>node.dataset.report===anchor.report);
  const node=report?.querySelectorAll('p,pre,summary')[anchor.index];
  if(node)panel.scrollTop+=node.getBoundingClientRect().top-panel.getBoundingClientRect().top-anchor.offset;
}
function syncReportView(){const key=`${chosenRun()?.id||selectedRunId}:${selectedSymbol}`;if(key!==reportViewKey){reportViews.set(reportViewKey,{open:openReportNames,scroll:reportViews.get(reportViewKey)?.scroll||0});reportViewKey=key;openReportNames=reportViews.get(key)?.open||new Set();}return key;}
let orderFilter = 'all';
let universeSort = {field:'default',direction:1};
let chartMode = 'stock';
let chartPeriod = 'month';

let chartSize = {width:610,height:238};
let chartResizeObserver = null;
let stateErrorMessage = '';
let rateLimitedUntil=0;
const coolingDown=()=>Date.now()<rateLimitedUntil;
function rateLimitMessage(){return coolingDown()?`Upstream rate limit (429). Try again after ${time(rateLimitedUntil)}. Your last snapshot is still shown; requests are paused.`:'The cooldown has ended. Retry the chart or refresh when ready.';}
function selectStock(symbol){if(!universe().includes(symbol))return;selectedSymbol=symbol;if(activePage==='overview'){chartMode='stock';selectedRunId=state.research?.[symbol]?.run_id||'';}syncReportView();render();}


const listViews=Object.fromEntries(['watch','research','positions','proposals','orders'].map(name=>[name,{query:'',filter:'all',page:0,size:25}]));
function listToolbar(name,filters=[]){const v=listViews[name];return `<div class="collection-toolbar"><label class="collection-search" for="${name}-search">Find ${name==='watch'?'stocks':name}<input id="${name}-search" type="search" class="form-control" data-list-query="${name}" value="${esc(v.query)}" placeholder="Search symbols" autocomplete="off"></label>${filters.length?`<label for="${name}-scope">Show<select id="${name}-scope" class="form-control" data-list-filter="${name}">${filters.map(([key,label])=>`<option value="${key}" ${v.filter===key?'selected':''}>${esc(label)}</option>`).join('')}</select></label>`:''}</div>`;}
function listPage(name,items){const v=listViews[name],p=DeskLists.page(items,v.page,v.size);v.page=p.current;return p;}
function listPager(name,p){return `<div class="collection-pager"><span>${p.first}–${p.last} of ${p.total}</span><label for="${name}-size">Rows <select class="form-control" id="${name}-size" data-list-size="${name}">${[25,50,100].map(n=>`<option ${p.size===n?'selected':''}>${n}</option>`).join('')}</select></label><div><button class="button button-small" data-action="list-page" data-list="${name}" data-direction="-1" aria-label="Previous ${name} page" ${!p.current?'disabled':''}>Previous</button><span> ${p.current+1} / ${p.pages} </span><button class="button button-small" data-action="list-page" data-list="${name}" data-direction="1" aria-label="Next ${name} page" ${p.current+1>=p.pages?'disabled':''}>Next</button></div></div>`;}
function matchesStock(symbol,query){return !query||`${symbol} ${companies[symbol]||''}`.toLowerCase().includes(query.trim().toLowerCase());}
function reviewLabel(result){if(['failed','cancelled'].includes(result?.status))return 'Research '+result.status;const social=result?.social_sentiment;return social?'Social screening '+String(social.status||'not recorded').replaceAll('_',' '):'Social screening not recorded';}
function filteredWatch(){const v=listViews.watch;return sortedUniverse().filter(symbol=>{if(!matchesStock(symbol,v.query))return false;const r=state.research?.[symbol],q=DeskLists.quoteState(state.quotes?.[symbol],Date.now(),state.clock);return v.filter==='all'||v.filter==='selected'&&selectedSymbols.has(symbol)||v.filter==='held'&&positions().some(p=>p.symbol===symbol)||v.filter==='unresearched'&&!(r?.status==='completed'&&r.trade_date===DeskLists.dateNY())||v.filter===q;});}
function emptyMatches(){return '<div class="detail-note">No matches. Change the search or filter to see more stocks. Your research selection is preserved.</div>';}

function persistView(){try{localStorage.setItem('paper-desk-view',JSON.stringify({listViews,selected:[...selectedSymbols],symbol:selectedSymbol,sort:universeSort}));}catch{}}
function restoreView(){try{const saved=JSON.parse(localStorage.getItem('paper-desk-view')||'null');if(!saved)return false;for(const [name,value]of Object.entries(saved.listViews||{})){if(!listViews[name]||!value||typeof value!=='object')continue;listViews[name]={query:typeof value.query==='string'?value.query.slice(0,100):'',filter:typeof value.filter==='string'?value.filter:'all',page:Number.isInteger(value.page)?value.page:0,size:[25,50,100].includes(value.size)?value.size:25};}selectedSymbols=new Set((Array.isArray(saved.selected)?saved.selected:[]).filter(symbol=>universe().includes(symbol)));if(universe().includes(saved.symbol))selectedSymbol=saved.symbol;if(['default','symbol','price'].includes(saved.sort?.field))universeSort={field:saved.sort.field,direction:saved.sort.direction===-1?-1:1};return true;}catch{return false;}}
let pendingResearch=null;
async function launchResearch(symbols,revision){const result=await act('run','/api/runs',{symbols,config_revision:revision},'Research started. No orders have been placed.');if(result?.id||result?.run_id)selectedRunId=result.id||result.run_id;activePage='research';location.hash='research';await readState();}
function reviewResearch(){const symbols=[...selectedSymbols],estimate=DeskLists.estimate(runs(),state.config,symbols.length);pendingResearch={symbols,revision:state.config_revision};$('#research-preview').innerHTML=`<span class="badge neutral">Research only</span><h2 id="research-dialog-title">Research ${symbols.length} stocks</h2><p>The universe remains ${universe().length} stocks. This run analyzes the selected ${symbols.length} sequentially and places no orders.</p><dl class="order-spec"><div><dt>Fast analysis</dt><dd>${esc(state.config.quick_think_llm)}</dd></div><div><dt>Deep reasoning</dt><dd>${esc(state.config.deep_think_llm)}</dd></div><div><dt>Trade date</dt><dd>${esc(DeskLists.dateNY())} · New York</dd></div><div><dt>Observed duration</dt><dd>${estimate?`About ${DeskLists.duration(estimate.seconds)}, based on ${estimate.samples} completed stocks with these models`:'No completed observations for this configuration yet'}</dd></div></dl><p>A long sweep can cross a trading day. Account usage limits may interrupt research. Completed evidence is retained; paper proposals still require current data and individual review.</p><details><summary>Selected symbols (${symbols.length})</summary><p class="selection-preview">${esc(symbols.join(', '))}</p></details><button class="button button-primary" data-action="confirm-research">Start ${symbols.length}-stock research</button><div id="research-error" class="dialog-error" role="alert"></div>`;$('#research-dialog').showModal();}

const resultDetails=new Map();
const detailLoadedFor=new Map();
const detailRequests=new Set();
const detailErrors=new Map();
const chartRequests=new Set();
const chartErrors=new Map();
const chartLoadedAt=new Map();

async function ensureResultDetail(force=false){
  const run=chosenRun();const summary=(run?.results||[]).find(r=>r.symbol===selectedSymbol);
  if(!summary||summary.reports)return;
  const key=`${run.id}:${selectedSymbol}`;
  if(detailRequests.has(key)||(!force&&detailErrors.has(key))||(!force&&resultDetails.has(key)&&(resultDetails.get(key).revision>=summary.revision||detailLoadedFor.get(key)===summary.revision)))return;
  detailRequests.add(key);detailErrors.delete(key);
  try{
    const detail=await api(`/api/runs/${encodeURIComponent(run.id)}/results/${encodeURIComponent(summary.symbol)}`);
    if(detail.symbol!==summary.symbol)throw new Error('The research response belongs to a different stock. Refresh the run.');
    resultDetails.set(key,detail);detailLoadedFor.set(key,summary.revision);
    while(resultDetails.size>16){const oldest=resultDetails.keys().next().value;resultDetails.delete(oldest);detailLoadedFor.delete(oldest);}
  }catch(error){detailErrors.set(key,error.message);}
  finally{detailRequests.delete(key);if(activePage==='research'&&chosenRun()?.id===run.id&&selectedSymbol===summary.symbol)render();}
}

async function ensureChart(force=false){
  const symbol=selectedSymbol;
  if(!symbol||!state?.account||chartRequests.size)return;
  if(!force&&(chartErrors.has(symbol)||state.bars?.[symbol]?.length||chartLoadedAt.has(symbol)))return;
  chartRequests.add(symbol);chartErrors.delete(symbol);if(activePage==='overview')render();
  try{
    const detail=await api(`/api/instruments/${encodeURIComponent(symbol)}${force?'?refresh=1':''}`);
    if(detail.symbol!==symbol||!Array.isArray(detail.bars))throw new Error('Chart history was not returned for this stock.');
    state.bars=state.bars||{};state.bars[symbol]=detail.bars;chartLoadedAt.set(symbol,Date.now());
    while(chartLoadedAt.size>32){const oldest=chartLoadedAt.keys().next().value;chartLoadedAt.delete(oldest);delete state.bars[oldest];}
  }catch(error){chartErrors.set(symbol,error.message);}
  finally{chartRequests.delete(symbol);if(activePage==='overview')render();}
}

function detailNotice(result,run){
  const key=`${run?.id}:${selectedSymbol}`;
  if(detailErrors.has(key))return `<div class="detail-note negative">${esc(detailErrors.get(key))}<button class="button button-small" data-action="retry-detail">Try loading reports again</button></div>`;
  if(result&&!result.reports)return '<div class="detail-note" role="status">Loading the selected stock’s research reports…</div>';
  if(result?._updating)return '<div class="detail-note" role="status">A newer report is pending. The previous version remains visible. <button class="link-button" data-action="retry-detail">Refresh this report</button></div>';
  return '';
}

const runs = () => Array.isArray(state?.runs) ? state.runs : [];
const proposals = () => Array.isArray(state?.proposals) ? state.proposals : [];
const positions = () => Array.isArray(state?.positions) ? state.positions : [];
const orders = () => {
  const list=Array.isArray(state?.orders)?[...state.orders]:[];
  for(const p of proposals())if(p.broker_receipt){
    const index=list.findIndex(o=>o.id===p.broker_order_id);
    const owned={...p.broker_receipt,submitted_at:p.submitted_at,localReceipt:true};
    if(index<0)list.push(owned);else list[index]={...list[index],...owned};
  }
  return list;
};
function cancellationPending(id){
  const p=proposals().find(p=>p.broker_order_id===id);
  if(['intent','requested','unknown'].includes(p?.cancellation?.status))return true;
  const terminal=p?.broker_receipt?.id===id&&['filled','canceled','expired','rejected'].includes(p?.broker_receipt?.status)&&p.status===p.broker_receipt.status;
  if(p&&!p.reconciliation_error&&(p.cancellation?.status==='resolved'||terminal))pendingCancellations.delete(id);
  return pendingCancellations.has(id);
}
function mutationUncertain(){return pendingCancellations.size>0&&[...pendingCancellations].some(cancellationPending)||proposals().some(p=>['unknown','submitting'].includes(p.status)||p.reconciliation_error||cancellationPending(p.broker_order_id));}
function cancellationLabel(o){const p=proposals().find(p=>p.broker_order_id===o.id);const status=p?.cancellation?.status;return `${o.localReceipt?'<span class="asset-name">Last verified receipt</span>':''}${p?.reconciliation_error?'<span class="asset-name">Receipt conflict · Refresh to reconcile</span>':''}${status||cancellationPending(o.id)?`<span class="asset-name">${status==='resolved'?'Cancellation resolved':status==='requested'?'Cancellation requested · Refresh to reconcile':'Cancellation outcome unknown · Refresh to reconcile'}</span>`:''}`;}
async function cancelOrder(id){
  if(cancellationPending(id)||busy.has(`cancel-${id}`))return;
  pendingCancellations.add(id);
  try{const result=await act(`cancel-${id}`,'/api/orders/cancel',{order_id:id});showToast(result?.status==='cancel_requested'?'Cancellation requested. Refresh to reconcile broker status.':'Order status checked. Review the blotter.');}
  catch(error){await readState();throw error;}
}
const universe = () => state?.config?.universe || [];
const activeRun = () => runs().find(r => ['queued','running','cancelling','cancel_requested'].includes(r.status));
const chosenRun = () => runs().find(r => r.id===selectedRunId) || runs()[0];
const paused = () => Boolean(state?.trading_paused ?? state?.config?.trading_paused ?? state?.paused);
const currentResult = (symbol, run=chosenRun()) => {
  const summary=(run?.results||[]).find(r=>r.symbol===symbol);
  if(!summary||summary.reports)return summary;
  const cached=resultDetails.get(`${run.id}:${symbol}`);
  if(cached&&cached.revision>=summary.revision)return cached;
  return cached?{...cached,...summary,reports:cached.reports,
    laya:cached.revision===summary.revision?cached.laya:summary.laya,
    social_sentiment:cached.revision===summary.revision?cached.social_sentiment:summary.social_sentiment,
    _updating:cached.revision!==summary.revision}:summary;
};
const sourceError = source => (Array.isArray(state?.errors)?state.errors:[]).find(error=>error.source===source)?.message;
function unavailablePanel(title,source){return `<section class="panel"><div class="panel-header"><h2>${esc(title)}</h2>${statusBadge('Unavailable')}</div><div class="empty-state compact"><h3>${esc(title)} could not be loaded</h3><p>${esc(sourceError(source)||'The broker data source did not return a complete response.')}</p><button class="button button-small" data-action="refresh-source">Refresh broker data</button></div></section>`;}
const statusBadge = status => {const s=String(status||'Not started'); const key=s.toLowerCase(); const cls=['completed','complete','filled','buy','overweight','accepted','verified','ready'].includes(key)?'green':['failed','error','rejected','sell','underweight'].includes(key)?'red':['running','queued','new','pending_new','partially_filled','pending','proposed'].includes(key)?'blue':['cancelled','canceled','review','blocked','hold','stopping'].includes(key)?'amber':'neutral';return `<span class="badge ${cls}">${esc(s.replaceAll('_',' '))}</span>`;};
function showToast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
function setError(message){errorMessage=message;renderNotice();}
function renderNotice(){const notice=$('#notice'); const conn=state?.connection;let message=coolingDown()?rateLimitMessage():errorMessage||stateErrorMessage;let cls='error';if(!message&&state&&(!conn?.connected||!conn?.paper_verified)){message=conn?.message || (!conn?.connected?'Gateway unavailable. Check the local MCP service, then refresh.':'Paper account has not been verified. Refresh the connection before submitting orders.');cls='';}if(!message&&paused()){message='Execution is paused. Research and account monitoring remain available.';cls='';}notice.hidden=!message;notice.className=`notice ${cls}`;notice.innerHTML=message?`${esc(message)}${errorMessage?'<button class="icon-button" data-action="dismiss-error" aria-label="Dismiss error">×</button>':''}`:'';}
async function api(path, body, {timeoutMs=path.startsWith('/api/instruments/')||['/api/refresh','/api/runs','/api/proposals'].includes(path)?550000:body===undefined?15000:120000}={}){
  if(coolingDown()&&(path==='/api/quotes/refresh'||path.startsWith('/api/instruments/')||['/api/refresh','/api/runs','/api/proposals','/api/orders','/api/orders/cancel'].includes(path)))throw new Error(rateLimitMessage());
  const controller=typeof AbortController==='function'?new AbortController():null;
  let timedOut=false;
  let timer;
  const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{
    timedOut=true;controller?.abort();reject(new Error('Request deadline exceeded.'));
  },timeoutMs);});
  try{
    const request=(async()=>{
      const response=await fetch(path,{method:body===undefined?'GET':'POST',signal:controller?.signal,
        headers:body===undefined?{'Accept':'application/json'}:{'Content-Type':'application/json','Accept':'application/json','X-CSRF-Token':state?.csrf_token||''},
        body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
      if(response.status===429){
        const retry=response.headers?.get?.('Retry-After');
        const delay=retry&&Number.isFinite(Number(retry))?Math.max(1,Number(retry))*1000:retry&&Number.isFinite(Date.parse(retry))?Math.max(1000,Date.parse(retry)-Date.now()):30000;
        rateLimitedUntil=Math.max(rateLimitedUntil,Date.now()+delay);
        const limited=new Error(rateLimitMessage());limited.status=429;
        renderNotice();throw limited;
      }
      let payload;
      try{payload=await response.json();}catch{if(timedOut)throw new Error('timeout');throw new Error(`The local service returned an unreadable response (${response.status}).`);}
      if(!response.ok)throw new Error(payload?.error||`Request failed (${response.status}).`);
      return payload;
    })();
    return await Promise.race([request,deadline]);
  }catch(error){
    if(timedOut||error.name==='AbortError'){
      const message=body===undefined?'The local service did not respond in time. Your last snapshot is still shown; try refreshing.':
        path==='/api/orders'?'The submission request timed out. Refresh broker status before taking another action; its outcome may be unknown.':
        path==='/api/orders/cancel'?'The cancellation request timed out; its outcome may be unknown. Refresh to reconcile broker status. Do not resend cancellation.':
        'The request timed out. Refresh the workspace to check its status before trying again.';
      throw new Error(message);
    }
    throw error;
  }finally{clearTimeout(timer);}
}
async function readState({force=false,timeoutMs}={}){
  if(stateFetch){await stateWait;if(!force)return;}
  stateFetch=true;stateWait=new Promise(resolve=>stateDone=resolve);
  try{
    const fresh=await api(`/api/state?compact=1${selectedRunId?`&run_id=${encodeURIComponent(selectedRunId)}`:''}`,undefined,timeoutMs?{timeoutMs}:undefined);
    const first=!state;
    fresh.bars=fresh.bars||state?.bars||{};
    state=fresh;
    stateErrorMessage='';
    if(first&&!restoreView())selectedSymbols=new Set(universe().length<=50?universe():[]);
    else selectedSymbols=new Set([...selectedSymbols].filter(s=>universe().includes(s)));
    if(!selectedSymbol||!universe().includes(selectedSymbol))selectedSymbol=universe()[0]||'';
    render({force});
  }catch(e){
    stateErrorMessage=e.message;renderNotice();
    if(!state)$('#main').innerHTML=`<div class="initial-state"><h1>The desk is not connected</h1><p>${esc(e.message)}</p><button class="button button-primary" data-action="retry">Try again</button></div>`;
  }finally{stateFetch=false;stateDone?.();stateDone=null;}

}
async function act(key,path,body,success){if(busy.has(key))return;busy.add(key);errorMessage='';render();try{const result=await api(path,body);if(success)showToast(success);await readState({force:true});return result;}catch(e){setError(e.message);throw e;}finally{busy.delete(key);render();}}
function render({force=false}={}){if(!state)return;const before=document.activeElement,caret=[before?.selectionStart,before?.selectionEnd];renderChrome();renderNotice();if(activePage==='settings'&&settingsDirty&&$('#settings-form')?.isConnected&&!force)return;const focused=before;const focusId=focused?.id;const scrollPanel=$('#research-detail-scroll');const readingAnchor=reportReadingAnchor(scrollPanel);const previousView=scrollPanel?.dataset?.view;const reportScroll=scrollPanel?.scrollTop||0;if(previousView!==undefined)reportViews.set(previousView,{open:reportViews.get(previousView)?.open||openReportNames,scroll:reportScroll});syncReportView();const nextReportScroll=previousView===reportViewKey?reportScroll:(reportViews.get(reportViewKey)?.scroll||0);const main=$('#main'),scrolls=$$('.table-scroll,.research-rows',main).map(el=>({top:el.scrollTop,left:el.scrollLeft}));main.innerHTML=activePage==='overview'?renderOverview():activePage==='research'?renderResearch():activePage==='orders'?renderOrders():renderSettings();if(activePage==='settings'&&state.readiness?.ready===false)$('.page-heading',main).insertAdjacentHTML('afterend',`<div class="error-detail">${esc(state.readiness.message)}</div>`);if(focusId){let next=document.getElementById(focusId);if(next&&focused?.dataset?.listQuery&&next.tagName===focused.tagName){next.replaceWith(focused);next=focused;}if(next&&next.tagName===focused.tagName)next.focus({preventScroll:true});if(next?.setSelectionRange&&caret[0]!==null&&caret[0]!==undefined)try{next.setSelectionRange(...caret);}catch{}}if(!focusId&&focused?.tagName==='A'&&focused.getAttribute?.('href')){const next=$$('#navigation a').find(el=>el.getAttribute('href')===focused.getAttribute('href'));next?.focus({preventScroll:true});}if(!focusId&&focused?.dataset?.action){const next=$$('[data-action]',main).find(el=>el.dataset.action===focused.dataset.action&&el.dataset.symbol===focused.dataset.symbol&&el.dataset.proposal===focused.dataset.proposal&&el.dataset.list===focused.dataset.list&&el.dataset.direction===focused.dataset.direction&&el.dataset.order===focused.dataset.order);if(next)next.focus({preventScroll:true});}if($('#research-detail-scroll')){$('#research-detail-scroll').scrollTop=nextReportScroll;if(previousView===reportViewKey)restoreReadingAnchor($('#research-detail-scroll'),readingAnchor);}$$('.table-scroll,.research-rows',main).forEach((el,i)=>{if(scrolls[i]){el.scrollTop=scrolls[i].top;el.scrollLeft=scrolls[i].left;}});persistView();observeChartSize();if(activePage==='overview'&&chartMode==='stock')ensureChart();if(activePage==='research')ensureResultDetail();}
function observeChartSize(){chartResizeObserver?.disconnect();const target=$('.chart-wrap');if(!target||typeof ResizeObserver==='undefined')return;chartResizeObserver=new ResizeObserver(entries=>{const {width,height}=entries[0].contentRect;if(width<120||height<100)return;if(Math.abs(chartSize.width-width)>.5||Math.abs(chartSize.height-height)>.5){chartSize={width,height};target.innerHTML=chartMode==='stock'?stockChart():equityChart();}});chartResizeObserver.observe(target);}
function renderChrome(){const labels={overview:'Workspace',research:'Agent research',orders:'Trade & orders',settings:'Settings'};$('#navigation').innerHTML=Object.entries(labels).map(([page,label])=>`<a class="nav-link" href="#${page}" ${page===activePage?'aria-current="page"':''} aria-label="${label}">${icon(page)}<span>${label}</span>${page==='orders'&&proposals().some(p=>['pending','proposed','ready'].includes(p.status))?`<span class="nav-count">${proposals().filter(p=>['pending','proposed','ready'].includes(p.status)).length}</span>`:''}</a>`).join('');$('#page-label').textContent=labels[activePage];$('#universe-name').textContent=state.config?.name||'Custom universe';$('#last-updated').textContent=`${({open:'Market open',closed:'Market closed',unknown:'Market status unknown'})[DeskLists.marketState(state.clock)]} · ${state.updated_at?`Snapshot ${time(state.updated_at)}`:'No account snapshot'}`;$('#gateway-status').innerHTML=`<span class="status-dot ${state.connection?.connected?'connected':'disconnected'}"></span><span>${state.connection?.connected?'Gateway connected':'Gateway disconnected'}</span>`;const pauseButton=$('#pause-trading');pauseButton.textContent=paused()?'Resume execution':'Pause execution';pauseButton.classList.toggle('is-paused',paused());pauseButton.disabled=busy.has('pause');$('#refresh').disabled=busy.has('refresh')||coolingDown();$('#refresh span').textContent=busy.has('refresh')?'Refreshing…':'Refresh';}
function researchButton(){if(!state.account||!state.connection?.paper_verified)return '<button class="button button-primary" data-action="refresh-source" '+(busy.has('refresh')?'disabled':'')+'>Connect paper account</button>';if(state.readiness?.ready===false&&state.config?.llm_provider!=='codex')return `<a class="button button-primary" href="#settings" title="${esc(state.readiness.message||'Configure the research models to continue')}">${icon('settings')}Configure research</a>`;return `<button class="button button-primary" data-action="run" ${busy.has('run')||activeRun()||!selectedSymbols.size||coolingDown()?'disabled':''}>${icon('play')}${busy.has('run')?'Starting…':activeRun()?'Research running':`Run research${selectedSymbols.size?` (${selectedSymbols.size})`:''}`}</button>`;}
function pageHeader(title,description,actions=''){return `<div class="page-heading"><div><div class="heading-line"><h1>${title}</h1>${state.connection?.paper_verified?'<span class="badge green">Paper verified</span>':'<span class="badge amber">Paper unverified</span>'}</div><p>${description}</p></div><div class="button-group">${actions}</div></div>`;}
function accountLedger(){const a=state.account;const eq=number(a?.equity??a?.portfolio_value);const prior=number(a?.last_equity);const pnl=eq!==null&&prior!==null?eq-prior:null;const pnlPct=pnl!==null&&prior!==0?pnl/prior*100:null;const invested=sourceError('positions')?null:positions().reduce((sum,p)=>sum+Math.abs(number(p.market_value)||0),0);return `<dl class="account-ledger"><div class="account-cell"><dt>Net liquidation</dt><dd>${money(eq)}</dd><p class="${color(pnl)}">${pnl!==null?`${money(pnl)} (${percent(pnlPct)}) today`:'Awaiting broker account'}</p></div><div class="account-cell"><dt>Available cash</dt><dd>${money(a?.cash)}</dd><p>Reserve target ${esc(state.config?.reserve_pct??'—')}%</p></div><div class="account-cell"><dt>Invested capital</dt><dd>${a?money(invested):'—'}</dd><p>${sourceError('positions')?'Positions unavailable':a?`${positions().length} open position${positions().length===1?'':'s'}`:'Positions not loaded'}</p></div><div class="account-cell"><dt>Buying power</dt><dd>${money(a?.buying_power)}</dd><p>Order cap ${money(state.config?.max_order_notional)}</p></div></dl>`;}
function equityChart(){const h=state.history||{};const values=(h.equity||[]).map((v,i)=>({value:number(v),timestamp:h.timestamp?.[i]})).filter(p=>p.value!==null);if(values.length<2)return `<div class="empty-chart">${icon('chart')}<h3>No equity history yet</h3><p>Refresh the paper account to load its recorded equity. Missing points are never estimated.</p></div>`;const w=chartSize.width,hgt=chartSize.height,left=8,right=86,top=17,bottom=28;let min=Math.min(...values.map(p=>p.value)),max=Math.max(...values.map(p=>p.value));const pad=Math.max((max-min)*.15,max*.0001,1);min-=pad;max+=pad;const x=i=>left+i/(values.length-1)*(w-left-right);const y=v=>top+(max-v)/(max-min)*(hgt-top-bottom);const path=values.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v.value).toFixed(2)}`).join(' ');return `<svg class="equity-chart" viewBox="0 0 ${w} ${hgt}" role="img" aria-label="Paper account equity from ${esc(date(values[0].timestamp))} to ${esc(date(values.at(-1).timestamp))}: ${esc(money(values[0].value))} to ${esc(money(values.at(-1).value))}">${[0,.5,1].map(f=>{const val=min+(max-min)*f;return `<line class="grid" x1="${left}" y1="${y(val)}" x2="${w-right}" y2="${y(val)}"/><text x="${w-right+10}" y="${y(val)+4}">${esc(money(val))}</text>`;}).join('')}<path class="series" d="${path}"/><text x="${left}" y="${hgt-5}">${esc(date(values[0].timestamp))}</text><text x="${w-right}" y="${hgt-5}" text-anchor="end">${esc(date(values.at(-1).timestamp))}</text></svg>`;}
function linkedSummary(){const result=currentResult(selectedSymbol),run=chosenRun(),q=state.quotes?.[selectedSymbol],symbols=filteredWatch(),index=symbols.indexOf(selectedSymbol);return `<section class="panel research-summary"><div class="panel-header"><div><h2>Agent research</h2><p>Linked to ${esc(selectedSymbol||'your universe')}</p></div>${statusBadge(result?.status||'Not started')}</div><div class="run-summary-body"><div class="run-summary-title"><strong>${esc(selectedSymbol||'Select a symbol')}</strong>${result?.rating?statusBadge(result.rating):'<span class="muted">No decision</span>'}</div><p>${esc(result?.error||(!run?'Select stocks and launch research to read the analysts, debate and portfolio decision.':result?'Inspect the source reports and committee decision before building orders.':'This stock has no result in the selected run.'))}</p><p>${esc(reviewLabel(result||state.research?.[selectedSymbol]))}</p><div class="symbols-inline"><button class="button button-small" data-action="linked-step" data-direction="-1" ${index<=0?'disabled':''}>Previous stock</button><button class="button button-small" data-action="linked-step" data-direction="1" ${index<0||index>=symbols.length-1?'disabled':''}>Next stock</button><button class="link-button" data-action="find-stock">Find in watchlist</button></div><p class="muted">${index>=0?`${index+1} of ${symbols.length} matching stocks`:'Stock outside the current filter'}</p></div><div class="run-summary-foot"><span>${q?.timestamp?`Quote ${time(q.timestamp)}`:'No verified quote'}</span><button class="link-button" data-action="inspect" data-symbol="${esc(selectedSymbol)}">Open evidence ${icon('arrow')}</button></div></section>`;}
function sortedUniverse(){let symbols=[...universe()];if(universeSort.field==='symbol')symbols.sort((a,b)=>a.localeCompare(b)*universeSort.direction);if(universeSort.field==='price')symbols.sort((a,b)=>((number(state.quotes?.[a]?.price)||0)-(number(state.quotes?.[b]?.price)||0))*universeSort.direction);return symbols;}
function watchlist(){const matches=filteredWatch(),p=listPage('watch',matches);return `<section class="panel watchlist-panel"><div class="panel-header"><div><h2>${esc(state.config?.name||'Watchlist')}</h2><p>${universe().length} stocks · ${selectedSymbols.size} selected for research</p><p>Quotes: ${quoteRefreshPaused?'updates paused':'checked at most once a minute while visible'} · IEX${state.quotes_updated_at?' · checked '+esc(time(state.quotes_updated_at)):''}</p></div>${!state.connection?.connected?'<p>Quotes unavailable: gateway disconnected. Start the gateway, then <button class="link-button" data-action="refresh-source">Refresh connection</button>.</p>':''}<div class="quote-actions"><button class="link-button" data-action="refresh-quotes" ${!state.connection?.connected||busy.size||coolingDown()?'disabled':''}>${busy.has('quotes')?'Updating...':'Update quotes'}</button><a class="link-button" href="#settings">Edit index</a></div></div>${listToolbar('watch',[['all','All stocks'],['selected','Selected for research'],['held','Held positions'],['unresearched','Needs research today'],['missing','Missing quotes'],['stale','Stale quotes']])}<div class="selection-actions"><button class="link-button" data-action="select-matches" ${!matches.length?'disabled':''}>Select ${matches.length} matches</button><button class="link-button" data-action="clear-selection" ${!selectedSymbols.size?'disabled':''}>Clear selection</button><span>${selectedSymbols.size} selected across all pages</span></div><div class="table-scroll"><table class="data-table watchlist-table"><thead><tr><th class="checkbox-cell"><input type="checkbox" id="select-page" aria-label="Select the ${p.items.length} stocks on this page" ${p.items.length&&p.items.every(s=>selectedSymbols.has(s))?'checked':''}></th><th class="asset-cell"><button class="table-sort" data-action="sort-symbol">Symbol</button></th><th><button class="table-sort" data-action="sort-price">Last</button></th><th>Change</th></tr></thead><tbody>${p.items.map(symbol=>{const q=state.quotes?.[symbol]||{},r=state.research?.[symbol],fresh=DeskLists.quoteState(q,Date.now(),state.clock);return `<tr data-action="select-symbol" data-symbol="${esc(symbol)}" class="${symbol===selectedSymbol?'selected-row':''}"><td class="checkbox-cell"><input type="checkbox" class="symbol-select" id="select-symbol-${esc(symbol)}" value="${esc(symbol)}" aria-label="Include ${esc(symbol)} in research" ${selectedSymbols.has(symbol)?'checked':''}></td><td class="asset-cell"><button class="ticker-button" data-action="select-symbol" data-symbol="${esc(symbol)}" aria-pressed="${symbol===selectedSymbol}">${esc(symbol)}</button><span class="asset-name">${esc(companies[symbol]||'Equity')}</span><span class="asset-name">${esc(r?.status==='completed'?r?.rating||'Completed':r?.status||'Not researched')} · ${esc(reviewLabel(r))}</span>${r?.trade_date?`<span class="asset-name">${esc(r.trade_date)}</span>`:''}</td><td>${money(q.price)}<span class="asset-name ${['current','closed'].includes(fresh)?'':'negative'}">${esc(quoteStatus(q))}</span></td><td class="${color(q.change_pct)}">${percent(q.change_pct)}</td></tr>`;}).join('')}</tbody></table></div>${!matches.length?emptyMatches():''}${listPager('watch',p)}</section>`;}
function positionsTable(){const page=boundedItems('positions',positions());if(sourceError('positions'))return unavailablePanel('Positions','positions');return `<section class="panel"><div class="panel-header"><div><h2>Positions</h2><p>Broker holdings · actual paper exposure</p></div><button class="button button-small button-quiet" data-action="export-positions" ${positions().length?'':'disabled'}>${icon('download')}CSV</button></div>${listToolbar('positions')}${!positions().length?`<div class="empty-state compact">${icon('overview')}<h3>${state.account?'No open positions':'Account not loaded'}</h3><p>${state.account?'Paper fills will appear here with cost basis and unrealized P/L.':'Refresh to retrieve holdings from the connected paper account.'}</p></div>`:`<div class="table-scroll"><table class="data-table"><thead><tr><th>Symbol</th><th>Quantity</th><th>Avg. cost</th><th>Market value</th><th>Unrealized P/L</th><th>Weight</th></tr></thead><tbody>${page.items.map(p=>{const eq=number(state.account?.equity);const weight=eq?number(p.market_value)!==null?Math.abs(Number(p.market_value))/eq*100:null:null;return `<tr><td><button class="ticker-button" data-action="inspect" data-symbol="${esc(p.symbol)}">${esc(p.symbol)}</button></td><td>${count(p.qty)}</td><td>${money(p.avg_entry_price)}</td><td>${money(p.market_value)}</td><td class="${color(p.unrealized_pl)}">${money(p.unrealized_pl)}<span class="asset-name ${color(p.unrealized_plpc)}">${number(p.unrealized_plpc)!==null?percent(Number(p.unrealized_plpc)*100):''}</span></td><td>${weight===null?'—':`${weight.toFixed(1)}%`}<span class="allocation"><span style="width:${Math.min(100,Math.max(0,weight||0))}%"></span></span></td></tr>`;}).join('')}</tbody></table></div>`}${positions().length&&!page.total?emptyMatches():''}${positions().length?listPager('positions',page):''}</section>`;}
function stockChart(){if(chartErrors.has(selectedSymbol))return `<div class="empty-chart"><h3>Price history unavailable</h3><p>${esc(chartErrors.get(selectedSymbol).includes("429")&&!coolingDown()?"Rate limit retries ended. You can try loading history again.":chartErrors.get(selectedSymbol))}</p><button class="button button-small" data-action="retry-chart" ${coolingDown()?'disabled':''}>Try loading history again</button></div>`;if(chartRequests.size&&!state.bars?.[selectedSymbol]?.length)return '<div class="empty-chart" role="status"><h3>Loading price history…</h3><p>Fetching the stock in focus. Rate limits use up to 3 retries, with waits capped at 60 seconds.</p></div>';let bars=(state.bars?.[selectedSymbol]||[]).filter(b=>['o','h','l','c'].every(k=>number(b[k])!==null));if(bars.length){const end=new Date(bars.at(-1).t);const start=new Date(end);chartPeriod==='week'?start.setUTCDate(start.getUTCDate()-7):start.setUTCMonth(start.getUTCMonth()-1);bars=bars.filter(b=>new Date(b.t)>=start);}if(bars.length<2)return `<div class="empty-chart">${icon('chart')}<h3>No price history for ${esc(selectedSymbol)}</h3><p>The broker has not returned enough daily bars for this stock.</p><button class="button button-small" data-action="retry-chart" ${coolingDown()?'disabled':''}>Load price history</button></div>`;const w=chartSize.width,h=chartSize.height,left=8,right=57,top=13,bottom=47;const low=Math.min(...bars.map(b=>+b.l)),high=Math.max(...bars.map(b=>+b.h));const pad=Math.max((high-low)*.12,1);const min=low-pad,max=high+pad;const x=i=>left+(i+.5)/bars.length*(w-left-right);const y=v=>top+(max-v)/(max-min)*(h-top-bottom);const cw=Math.max(2,Math.min(9,(w-left-right)/bars.length*.6));const vmax=Math.max(...bars.map(b=>+b.v||0),1);return `<svg class="equity-chart candle-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(selectedSymbol)} daily price candles, ${bars.length} sessions ending ${esc(barDate(bars.at(-1).t))}">${[0,.25,.5,.75,1].map(f=>{const val=min+(max-min)*f;return `<line class="grid" x1="${left}" y1="${y(val)}" x2="${w-right}" y2="${y(val)}"/><text x="${w-right+8}" y="${y(val)+4}">${val.toFixed(2)}</text>`;}).join('')}${bars.map((b,i)=>{const cls=+b.c>=+b.o?'candle-up':'candle-down';return `<g class="${cls}"><title>${esc(barDate(b.t))} · O ${esc(money(b.o))} H ${esc(money(b.h))} L ${esc(money(b.l))} C ${esc(money(b.c))} · Vol ${count(b.v)}</title><line x1="${x(i)}" y1="${y(+b.h)}" x2="${x(i)}" y2="${y(+b.l)}"/><rect x="${x(i)-cw/2}" y="${Math.min(y(+b.o),y(+b.c))}" width="${cw}" height="${Math.max(1,Math.abs(y(+b.o)-y(+b.c)))}"/><rect class="volume-bar" x="${x(i)-cw/2}" y="${h-20-(+b.v||0)/vmax*22}" width="${cw}" height="${(+b.v||0)/vmax*22}"/></g>`;}).join('')}<text x="${left}" y="${h-3}">${esc(barDate(bars[0].t))}</text><text x="${w-right}" y="${h-3}" text-anchor="end">${esc(barDate(bars.at(-1).t))}</text></svg>`;}
function chartPanel(){const q=state.quotes?.[selectedSymbol]||{};return `<section class="panel equity-panel"><div class="panel-header"><div class="chart-tabs"><button class="${chartMode==='stock'?'active':''}" data-action="chart-stock">${esc(selectedSymbol)} chart</button><button class="${chartMode==='equity'?'active':''}" data-action="chart-equity">Account equity</button></div><div class="chart-periods">${chartMode==='stock'?`<button class="${chartPeriod==='week'?'active':''}" data-action="chart-week">1W</button><button class="${chartPeriod==='month'?'active':''}" data-action="chart-month">1M</button>`:'<span class="badge neutral">Broker history</span>'}</div></div>${chartMode==='stock'?`<div class="quote-strip"><div><strong>${esc(selectedSymbol)}</strong><span>${esc(companies[selectedSymbol]||'Equity')}</span></div><div><strong>${money(q.price)}</strong><span class="${color(q.change_pct)}">${percent(q.change_pct)}</span></div><div><span>Bid / ask</span><span>${money(number(q.bid)>0?q.bid:null)} / ${money(number(q.ask)>0?q.ask:null)}</span></div></div>`:''}<div class="chart-wrap">${chartMode==='stock'?stockChart():equityChart()}</div><div class="chart-caption"><span>${chartMode==='stock'?`Daily OHLC · ${esc(q.feed||'Broker')} feed`:'Source: Alpaca paper account'}</span><span>${chartMode==='stock'&&q.timestamp?`${date(q.timestamp)} ${time(q.timestamp)}`:state.updated_at?`Updated ${time(state.updated_at)}`:'Awaiting first snapshot'}</span></div></section>`;}
function renderOverview(){return `${pageHeader('Trading workspace','Alpaca paper account · linked tools and agent research',`${activeRun()?`<button class="button button-danger" data-action="stop-run">${icon('stop')}Stop run</button>`:''}${researchButton()}`)}${accountLedger()}<div class="trading-grid">${watchlist()}${chartPanel()}${linkedSummary()}</div><div class="lower-grid">${positionsTable()}${orderBlotter(true)}</div>${renderDiagnostics()}`;}

function researchCollection(run){const v=listViews.research,items=(run.symbols||[]).filter(symbol=>matchesStock(symbol,v.query)&&(v.filter==='all'||(currentResult(symbol,run)?.status||'queued')===v.filter)),p=listPage('research',items),counts=run.counts||{},remaining=(counts.queued||0)+(counts.running||0),estimate=remaining?DeskLists.estimate(runs(),run.config,remaining):null,done=['completed','failed','cancelled'].reduce((n,k)=>n+(counts[k]||0),0);return `${listToolbar('research',[['all','All run stocks'],['completed','Completed'],['running','Running'],['queued','Queued'],['failed','Failed'],['cancelled','Cancelled']])}<div class="queue-progress"><label for="run-progress">${done} / ${run.symbols.length} finished</label><progress id="run-progress" max="${run.symbols.length||1}" value="${done}"></progress><p>${counts.completed||0} completed · ${counts.failed||0} failed · ${counts.queued||0} queued</p>${remaining?`<p>${estimate?`About ${DeskLists.duration(estimate.seconds)} remaining · based on ${estimate.samples} completed stock timings with these models`:'Observed duration will appear after a stock finishes with these models.'}</p>`:''}<button class="link-button" data-action="select-unfinished" ${activeRun()?'disabled':''}>Select failed / unfinished for a new run</button></div><div class="research-rows">${p.items.map(symbol=>{const result=currentResult(symbol,run);return `<button class="research-symbol" data-action="select-symbol" data-symbol="${esc(symbol)}" aria-pressed="${symbol===selectedSymbol}"><span><strong>${esc(symbol)}</strong><span class="asset-name">${esc(reviewLabel(result))}</span></span>${statusBadge(result?.status==='completed'?result.rating||'Completed':result?.status||'Queued')}</button>`;}).join('')}</div>${!items.length?emptyMatches():''}${listPager('research',p)}`;}
function boundedItems(name,items){const v=listViews[name];return listPage(name,items.filter(item=>matchesStock(item.symbol,v.query)&&(v.filter==='all'||item.status===v.filter)));}

function renderResearch(){const run=chosenRun();const result=currentResult(selectedSymbol,run);return `${pageHeader('Agent research','Trace every decision from analysis to portfolio review.',`${activeRun()?'<button class="button button-danger" data-action="stop-run">Stop run</button>':''}${researchButton()}`)}${!runs().length?`<section class="panel"><div class="empty-state">${icon('research')}<h2>Your first research run</h2><p>Selected symbols move through market, sentiment, news and fundamentals analysts, a bull / bear debate, a trader, and a risk committee. Read the evidence here before creating proposals.</p>${researchButton()}<p class="muted">A research run does not place orders.</p></div></section>`:`<div class="run-toolbar"><label for="run-select" class="muted">Research run</label><select id="run-select" class="form-control">${runs().map(r=>`<option value="${esc(r.id)}" ${r.id===run?.id?'selected':''}>${esc(date(r.created_at))} ${esc(time(r.created_at))} · ${(r.symbols||[]).length} symbols · ${esc(r.status)} · ${esc(r.id.slice(0,8))}</option>`).join('')}</select>${statusBadge(run?.status)}<button class="button" data-action="build-proposals" ${busy.has('proposals')||mutationUncertain()||!run||!['completed','complete','partial','failed','cancelled'].includes(run.status)?'disabled':''}>${busy.has('proposals')?'Building…':'Build paper proposals'}</button></div><div class="research-layout"><aside class="symbol-list" aria-label="Run symbols">${researchCollection(run)}</aside><section class="panel research-detail-panel"><div class="result-top"><div class="heading-line"><h2>${esc(selectedSymbol)}</h2>${statusBadge(result?.rating||result?.status||'Awaiting result')}</div><p>${esc(companies[selectedSymbol]||'Equity')} · ${esc(run.id)}</p></div><div id="research-detail-scroll" data-view="${esc(reportViewKey)}" class="research-detail-scroll" tabindex="0" role="region" aria-label="Selected stock research reports">${result?.error?`<div class="detail-note negative">${esc(result.error)}</div>`:''}${detailNotice(result,run)}${renderReports(result)}<div class="detail-note">Agent opinions are research evidence. Position sizes are calculated by the execution policy.</div></div></section></div>${renderEvents(run)}`}${renderDiagnostics()}`;}
// Reports are untrusted source text. Only these authored elements and HTTP(S) links are emitted.
function reportLink(value){
  if(!/^https?:\/\//i.test(value)||/[\s<>"'\\]/.test(value))return null;
  try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}
}
function reportInline(value,depth=0){
  const source=String(value??'');
  if(depth>5)return esc(source);
  const tokens=/`([^`\n]+)`|(!?\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\))|\*\*([^\n]+?)\*\*|(?<![\p{L}\p{N}_])__([^\n]+?)__(?![\p{L}\p{N}_])|\*([^*\n]+)\*|(?<![\p{L}\p{N}_])_([^_\n]+)_(?![\p{L}\p{N}_])/gu;
  let html='',offset=0;
  for(const match of source.matchAll(tokens)){
    html+=esc(source.slice(offset,match.index));
    if(match[1]!==undefined)html+=`<code>${esc(match[1])}</code>`;
    else if(match[2]!==undefined){
      const href=match[2].startsWith('!')?null:reportLink(match[4]);
      html+=href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(match[3])}</a>`:esc(match[2]);
    }else if(match[5]!==undefined||match[6]!==undefined)html+=`<strong>${reportInline(match[5]??match[6],depth+1)}</strong>`;
    else html+=`<em>${reportInline(match[7]??match[8],depth+1)}</em>`;
    offset=match.index+match[0].length;
  }
  return html+esc(source.slice(offset));
}
function reportTableCells(line){return line.trim().replace(/^\|/,'').replace(/\|$/,'').split(/(?<!\\)\|/).map(cell=>cell.trim().replace(/\\\|/g,'|'));}
function reportMarkdown(value,depth=0){
  if(depth>8)return `<p>${esc(value)}</p>`;
  const lines=String(value??'').replace(/\r\n?/g,'\n').split('\n');
  const html=[];
  const isTable=i=>i+1<lines.length&&lines[i].includes('|')&&reportTableCells(lines[i+1]).length>1&&reportTableCells(lines[i+1]).every(cell=>/^:?-{3,}:?$/.test(cell));
  const isBlock=i=>/^\s*$|^\s*```|^\s*#{1,6}\s|^\s*(?:[-+*]|\d+[.)])\s+|^\s*>\s?|^\s*(?:---+|\*\*\*+)\s*$/.test(lines[i])||isTable(i);
  for(let i=0;i<lines.length;){
    if(!lines[i].trim()){i++;continue;}
    if(/^\s*```/.test(lines[i])){
      const code=[];i++;
      while(i<lines.length&&!/^\s*```/.test(lines[i]))code.push(lines[i++]);
      if(i<lines.length)i++;
      html.push(`<pre><code>${esc(code.join('\n'))}</code></pre>`);continue;
    }
    const heading=lines[i].match(/^\s*(#{1,6})\s+(.+?)\s*#*$/);
    if(heading){const level=Math.min(6,heading[1].length+2);html.push(`<h${level}>${reportInline(heading[2])}</h${level}>`);i++;continue;}
    if(isTable(i)){
      const headers=reportTableCells(lines[i]);i+=2;const rows=[];
      while(i<lines.length&&lines[i].trim()&&lines[i].includes('|')){const cells=reportTableCells(lines[i++]);rows.push(`<tr>${headers.map((_,n)=>`<td>${reportInline(cells[n]??'')}</td>`).join('')}</tr>`);}
      html.push(`<div class="report-table-scroll" role="region" aria-label="Report table" tabindex="0"><table><thead><tr>${headers.map(cell=>`<th scope="col">${reportInline(cell)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`);continue;
    }
    const list=lines[i].match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);
    if(list){
      const ordered=/^\d/.test(list[1]);const start=ordered?Number.parseInt(list[1],10):1;const items=[];
      while(i<lines.length){const item=lines[i].match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);if(!item||/^\d/.test(item[1])!==ordered)break;items.push(`<li>${reportInline(item[2])}</li>`);i++;}
      const tag=ordered?'ol':'ul';html.push(`<${tag}${ordered&&start!==1?` start="${start}"`:''}>${items.join('')}</${tag}>`);continue;
    }
    if(/^\s*>/.test(lines[i])){const quote=[];while(i<lines.length&&/^\s*>/.test(lines[i]))quote.push(lines[i++].replace(/^\s*>\s?/,''));html.push(`<blockquote>${reportMarkdown(quote.join('\n'),depth+1)}</blockquote>`);continue;}
    if(/^\s*(?:---+|\*\*\*+)\s*$/.test(lines[i])){html.push('<hr>');i++;continue;}
    const paragraph=[lines[i++]];
    while(i<lines.length&&!isBlock(i))paragraph.push(lines[i++]);
    html.push(`<p>${reportInline(paragraph.join('\n')).replace(/\n/g,'<br>')}</p>`);
  }
  return html.join('');
}
function reportValue(value){
  if(typeof value==='string'&&/^[\s]*[\[{]/.test(value)){try{const parsed=JSON.parse(value);if(parsed&&typeof parsed==='object')return parsed;}catch{/* Narrative text is not JSON. */}}
  return value;
}
const reportLabel=value=>String(value??'').replaceAll('_',' ').replace(/^\w/,letter=>letter.toUpperCase());
function reportStructured(value,depth=0){
  value=reportValue(value);
  if(value===null||value===undefined||value==='')return '<p class="muted">Not provided</p>';
  if(typeof value==='boolean')return `<p>${value?'Yes':'No'}</p>`;
  if(typeof value!=='object')return reportMarkdown(value);
  if(depth>4)return `<pre>${esc(text(value))}</pre>`;
  if(Array.isArray(value))return `<ul>${value.map(item=>`<li>${reportStructured(item,depth+1)}</li>`).join('')}</ul>`;
  return `<dl class="report-fields">${Object.entries(value).map(([key,item])=>`<div><dt>${esc(reportLabel(key))}</dt><dd>${reportStructured(item,depth+1)}</dd></div>`).join('')}</dl>`;
}
function reportDebate(value,committeeDecision){
  value=reportValue(value);
  if(!value||typeof value!=='object'||Array.isArray(value))return reportStructured(value);
  const sections=[];const seen=new Set();
  const normalized=content=>content===null||content===undefined?'':text(content).replace(/\s+/g,' ').trim();
  const add=(label,content)=>{const key=normalized(content);if(!key||seen.has(key))return;seen.add(key);sections.push(`<section class="report-part"><h3>${esc(label)}</h3>${reportStructured(content)}</section>`);};
  if(value.history)add('Discussion',value.history);
  else for(const [key,content]of Object.entries(value))if(key.endsWith('_history'))add(reportLabel(key.replace(/_history$/,'')),content);
  const response=value.judge_decision??value.decision??value.current_response;const responseKey=normalized(response);
  if(responseKey&&![...seen].some(history=>history.includes(responseKey)))add(responseKey===normalized(committeeDecision)?'Committee decision':'Latest response',response);
  return sections.length?sections.join(''):reportStructured(value);
}
function reportLaya(value){
  value=reportValue(value);
  if(!value||typeof value!=='object'||Array.isArray(value))return reportStructured(value);
  const contract=value.contract||{};const grade=contract.grade??value.grade;const summary=contract.summary??value.summary;const answers=value.answers??contract.answers;
  if(!grade&&!summary&&!answers)return reportStructured(value);
  const current=value.question_contract_version==='research-choice-v1';
  let html=`<p class="report-answer-meta">Historical Laya research check — retired. This saved assessment does not approve or block proposals.${current?' Research choice contract: research-choice-v1':''}</p>`;
  html+=grade?`<dl class="report-grade"><dt>Grade</dt><dd>${esc(reportLabel(grade))}</dd></dl>`:'';
  if(summary)html+=reportMarkdown(summary);
  if(answers&&typeof answers==='object')html+=`<div class="report-answers">${Object.entries(answers).map(([key,raw])=>{
    const answer=raw&&typeof raw==='object'?raw:{value:raw};const confidence=number(answer.confidence);
    const meta=[answer.kind?reportLabel(answer.kind):'',confidence!==null?`${Math.round(confidence*100)}% confidence`:'',answer.grade?reportLabel(answer.grade):''].filter(Boolean);
    const meanings={evidence_complete:{A:'Essential evidence supports assessment',B:'Essential evidence is missing or materially contradictory'},decision_consistent:{A:'Rating follows evidence and restrictions',B:'Rating is unsupported or disregards restrictions'}};
    const meaning=current?meanings[key]?.[answer.value]:null;
    return `<section class="report-answer"><h3>${esc(answer.question||reportLabel(key))}</h3>${meta.length?`<p class="report-answer-meta">${esc(meta.join(' · '))}</p>`:''}${meaning?`<p>${esc(meaning)}</p>`:''}<div class="report-answer-value">${reportStructured(answer.value??answer.answer)}</div>${answer.reason?reportMarkdown(answer.reason):''}</section>`;
  }).join('')}</div>`;
  else if(contract.reasons||value.reasons)html+=reportStructured(contract.reasons||value.reasons);
  return html;
}
function reportLayaReview(content){
  const parameters=content?.parameters||{},input=parameters.state||{},budget=content?.token_budget;
  const structuredBudget=budget&&typeof budget==='object'&&!Array.isArray(budget);
  const metadata={model:parameters.model??(structuredBudget?budget.model:null)??'Not recorded'};
  metadata.question_contract_version=content?.question_contract_version??'Legacy assessment (unversioned)';
  if(structuredBudget){
    metadata.effective_token_cap=budget.effective_max_tokens??'Not recorded';
    if(budget.max_tokens!==undefined)metadata.model_token_cap=budget.max_tokens;
  }else metadata.recorded_token_budget=budget??'Not recorded';
  metadata.reserved_tokens=content?.reserve_tokens??'Not recorded';
  metadata.summary_attempts=content?.summary_attempts??'Not recorded';
  const counts=structuredBudget?budget.sequence_tokens:null;
  return `<h3>Review input</h3>${reportStructured(metadata)}${counts&&typeof counts==='object'?`<h4>Full input tokens per question</h4>${reportStructured(counts)}`:''}<h4>Summary supplied to Laya</h4>${input.evidence_basis?reportStructured(input.evidence_basis):''}${reportStructured(input.summary??'No summary recorded.')}<p class="muted">The full source artifact below includes the exact request, questions, source references and token audit.</p>`;
}
function reportSocial(value){
  if(!value||typeof value!=='object')return reportStructured(value);
  const historical=Object.values(value.sources||{}).some(source=>source.admission_version!=='stance-contract-v1'||(source.posts||[]).some(post=>['bullish','bearish','neutral'].includes(post.stance)&&(post.stance_grade??post.result?.answers?.stance?.grade)!=='auto_execute'));
  const labels={bullish:'Bullish',bearish:'Bearish',neutral:'Neutral',unclear:'Unclear',off_topic:'Off topic',unscreened:'Unscreened'};
  return `${historical?'<p class="error-detail">Historical screening: saved counts may include predictions the current uncertainty rules would mark unclear. Original evidence is preserved.</p>':''}<p>Laya classifies individual social posts for relevance and sentiment. It does not approve trades.</p><p>Screening: ${esc(value.status||'not recorded')} · Model: ${esc(value.model||'not recorded')}</p>${Object.entries(value.sources||{}).map(([source,evidence])=>`<section class="report-answer"><h3>${esc(reportLabel(source))}</h3><p>${esc(evidence.status||'not recorded')}${evidence.note?' · '+esc(evidence.note):''}</p><dl class="report-grade">${Object.entries(labels).map(([key,label])=>`<dt>${label}</dt><dd>${esc(evidence.counts?.[key]??'Not recorded')}</dd>`).join('')}</dl><p class="muted">Unclear means the classification was uncertain. Unscreened means no usable classification was obtained; neither means neutral.</p>${(evidence.posts||[]).map(post=>`<section class="report-answer"><h4>${esc(['unscreened','off_topic'].includes(post.status)?reportLabel(post.status):reportLabel(post.stance||post.status||'unclear'))}</h4><p>${esc(post.text||'Post text not recorded')}</p>${reportStructured({provenance:post.provenance,text_sha256:post.text_sha256,status:post.status,relevance_probability:post.about_probability,stance_probability:post.stance_probability,raw_prediction:post.raw_prediction??post.result?.answers?.stance?.value,stance_grade:post.stance_grade??post.result?.answers?.stance?.grade,model:post.model})}</section>`).join('')}</section>`).join('')}`;
}
function portfolioDisplay(value){
  if(typeof value!=='string')return value;
  // Only remove the observed redundant field prefixes, never narrative headings
  // or a conflicting rating. The original artifact remains untouched below.
  return value.replace(/^(\*\*Rating\*\*:[ \t]*([^\r\n]+)\r?\n\r?\n\*\*Executive Summary\*\*:[ \t]*)\*\*Rating\*\*\r?\n([^\r\n]+)\r?\n\r?\n\*\*Executive Summary\*\*[ \t]*\r?\n/,
    (full,prefix,rating,repeated)=>rating.trim()===repeated.trim()?prefix:full)
    .replace(/(^|\n)(\*\*(Executive Summary|Investment Thesis|Price Target|Time Horizon)\*\*:[ \t]*)\*\*\3\*\*[ \t]*\r?\n/g,'$1$2');
}
function renderReportArtifact(name,content,reports={}){
  const body=name==='social_sentiment'?reportSocial(content):name==='laya_review'?reportLayaReview(content):name==='laya'?reportLaya(content):name.endsWith('_debate_state')?reportDebate(content,name==='investment_debate_state'?reports.investment_plan:reports.final_trade_decision):reportStructured(name==='final_trade_decision'?portfolioDisplay(content):content);
  return `<div class="report-content">${body}</div><details class="report-raw" data-view="${esc(reportViewKey)}" data-report="${esc(name)}:raw" ${openReportNames.has(name+':raw')?'open':''}><summary id="report-raw-${esc(name)}">Full source artifact</summary><pre>${esc(text(content))}</pre></details>`;
}
function renderReports(result){
  if(!result)return '<div class="empty-state"><h3>Waiting for this symbol</h3><p>Its reports will appear as the research run progresses.</p></div>';
  const reports=result.reports||{};const entries=Object.entries(reports).filter(([,v])=>v!==null&&v!==undefined&&v!=='');
  if(result.laya)entries.push(['laya',result.laya]);if(result.laya_review)entries.push(['laya_review',result.laya_review]);
  if(result.social_sentiment)entries.push(['social_sentiment',result.social_sentiment]);
  if(!entries.length)return `<div class="empty-state"><h3>${result.status==='running'?'Research in progress':'No reports available'}</h3><p>${result.error?'The run did not produce a report for this symbol. Review the event log below.':'The agent pipeline has not returned report artifacts yet.'}</p></div>`;
  const order=['final_trade_decision','decision','market_report','fundamentals_report','news_report','sentiment_report','investment_plan','investment_debate_state','trader_investment_plan','risk_debate_state','laya'];
  const priority=name=>order.includes(name)?order.indexOf(name):order.length;
  entries.sort(([a],[b])=>priority(a)-priority(b)||a.localeCompare(b));
  return `<div class="report-list">${entries.map(([name,content],i)=>`<details class="report-section" data-view="${esc(reportViewKey)}" data-report="${esc(name)}" ${openReportNames.has(name)?'open':''}><summary id="report-summary-${esc(name)}">${esc(({laya:'Historical Laya research check',laya_review:'Historical Laya review input',social_sentiment:'Laya social sentiment'})[name]||reportNames[name]||reportLabel(name))}<small>Source artifact</small></summary>${renderReportArtifact(name,content,reports)}</details>`).join('')}</div>`;
}
function renderEvents(run){const events=run.events||[];return `<section class="panel events-panel"><div class="panel-header"><div><h2>Run activity</h2><p>Recorded events · latest ${events.length} of ${run.event_count??events.length}</p></div><button class="button button-small button-quiet" data-action="export-run">${icon('download')}JSON</button></div>${events.length?`<ol class="event-list">${[...events].reverse().map(event=>{const e=typeof event==='string'?{message:event}:event;return `<li><time class="event-time">${esc(time(e.time||e.timestamp||e.at||e.created_at))}</time><strong>${esc(e.symbol||e.stage||e.kind||e.type||'Run')}</strong><span class="event-message">${esc(e.message||e.detail||text(e))}</span></li>`;}).join('')}</ol>`:'<div class="detail-note">No events recorded for this run yet.</div>'}</section>`;}
function orderBlotter(compact=false){if(sourceError('orders')&&!proposals().some(p=>p.broker_receipt))return unavailablePanel('Order blotter','orders');let list=orders();if(!compact&&orderFilter!=='all')list=list.filter(o=>orderFilter==='open'?['new','accepted','partially_filled','pending_new','pending_cancel','held'].includes(o.status):o.status===orderFilter);const page=boundedItems('orders',list);if(compact)list=list.slice(0,5);else list=page.items;return `<section class="panel"><div class="panel-header"><div><h2>Order blotter</h2><p>Broker acknowledgements and fill status</p></div>${compact?'<a class="link-button" href="#orders">All orders</a>':`<select id="order-filter" class="form-control compact-select" aria-label="Filter order status">${[['all','All orders'],['open','Open'],['filled','Filled'],['canceled','Canceled'],['rejected','Rejected']].map(([v,l])=>`<option value="${v}" ${orderFilter===v?'selected':''}>${l}</option>`).join('')}</select>`}</div>${!compact?listToolbar('orders'):''}${!list.length?`<div class="empty-state compact">${icon('orders')}<h3>${orders().length?'No matching orders':'No orders to display'}</h3><p>${state.account?'Review an agent proposal to submit a paper order. Its broker status and fills appear here.':'Refresh the account to retrieve paper order activity.'}</p></div>`:`<div class="table-scroll"><table class="data-table"><thead><tr><th>Symbol</th><th>Side</th><th>Qty / filled</th><th>Limit / fill</th><th>Status</th>${!compact?'<th>Submitted</th><th></th>':''}</tr></thead><tbody>${list.map(o=>`<tr><td><strong>${esc(o.symbol)}</strong>${!compact?`<span class="asset-name">${esc(String(o.id||'').slice(0,12))}</span>`:''}</td><td class="${o.side==='buy'?'positive':'negative'}">${esc(o.side)}</td><td>${count(o.qty)} / ${count(o.filled_qty)}</td><td>${money(o.limit_price)}<span class="asset-name">${money(o.filled_avg_price)}</span></td><td>${statusBadge(o.status)}${cancellationLabel(o)}</td>${!compact?`<td>${esc(time(o.submitted_at||o.created_at))}</td><td>${['new','accepted','partially_filled','pending_new','held'].includes(o.status)&&proposals().some(p=>p.broker_order_id===o.id)?`<button class="button button-small button-danger" data-action="cancel-order" data-order="${esc(o.id)}" ${busy.has(`cancel-${o.id}`)||cancellationPending(o.id)||proposals().some(p=>p.broker_order_id===o.id&&p.reconciliation_error)?'disabled':''}>Cancel</button>`:''}</td>`:''}</tr>`).join('')}</tbody></table></div>`}${!compact?listPager('orders',page):''}</section>`;}
function renderOrders(){const page=boundedItems('proposals',proposals()),pending=page.items;return `${pageHeader('Trade & orders','Review agent proposals, inspect limits, and track paper execution.',paused()?'<button class="button button-primary" data-action="toggle-pause">Resume execution</button>':'<button class="button button-danger" data-action="toggle-pause">Pause execution</button>')}<div class="risk-strip"><div>Execution <strong>${paused()?'Paused':'Manual approval'}</strong></div><div>Max allocation <strong>${esc(state.config?.allocation_pct??'—')}%</strong></div><div>Position cap <strong>${esc(state.config?.max_position_pct??'—')}%</strong></div><div>Cash reserve <strong>${esc(state.config?.reserve_pct??'—')}%</strong></div><div>Order cap <strong>${money(state.config?.max_order_notional)}</strong></div></div><section class="panel"><div class="panel-header"><div><h2>Paper proposals</h2><p>Calculated from research decisions and portfolio limits</p></div><a class="link-button" href="#research">View research</a></div>${listToolbar('proposals',[['all','All proposals'],['ready','Ready'],['blocked','Blocked'],['submitted','Submitted']])}${!pending.length?'<div class="empty-state">'+icon('orders')+`<h3>${proposals().length?'No matching proposals':'No proposals yet'}</h3>`+(proposals().length?'<p>No proposals match your search or status filter.</p><button class="button" data-action="clear-proposal-filters">Clear filters</button></div>':'<p>Complete a research run, then build paper proposals. Each proposal shows the exact quantity, limit price, and rationale before submission.</p><a href="#research" class="button">Open research</a></div>'):`<div class="table-scroll"><table class="data-table"><thead><tr><th>Symbol / side</th><th>Quantity</th><th>Limit price</th><th>Notional</th><th>Rationale</th><th>Status</th><th></th></tr></thead><tbody>${pending.map(p=>`<tr><td><strong>${esc(p.symbol)}</strong><span class="asset-name ${p.side==='buy'?'positive':'negative'}">${esc(p.side)}</span></td><td>${count(p.qty)}</td><td>${money(p.limit_price)}</td><td>${money(p.notional)}</td><td class="proposal-reason">${esc(p.reason||'No rationale provided.')}${p.reason==='Laya has not authorized automatic execution'?'<span class="asset-name">Historical · retired Laya check</span>':''}<span class="asset-name">${esc(p.created_at?new Date(p.created_at).toLocaleString():'Creation time not recorded')}</span></td><td>${statusBadge(p.status)}</td><td>${['pending','proposed','ready'].includes(p.status)?`<button class="button button-small button-primary" data-action="preview-order" data-proposal="${esc(p.id)}" ${!state.connection?.paper_verified||paused()||mutationUncertain()?'disabled':''}>Review order</button>`:'—'}</td></tr>`).join('')}</tbody></table></div>`}${listPager('proposals',page)}</section><div class="orders-section">${orderBlotter()}</div>${renderDiagnostics()}`;}
function field(name,label,value,{type='text',help='',min='',max='',step='',unit='',placeholder=''}={}){return `<div class="field"><label for="config-${name}">${label}</label><div class="${unit?'input-unit':''}"><input class="form-control" id="config-${name}" name="${name}" type="${type}" value="${esc(value)}" ${min!==''?`min="${min}"`:''} ${max!==''?`max="${max}"`:''} ${step!==''?`step="${step}"`:''} placeholder="${esc(placeholder)}" ${name==='backend_url'?'':'required'}>${unit?`<span>${unit}</span>`:''}</div>${help?`<small>${help}</small>`:''}</div>`;}
function renderSettings(){const c=settingsDraft||state.config||{};const domains=state.connection?.domains||[];return `${pageHeader('Workspace settings','Define the universe, capital limits, and models used for the next research run.')}<div class="settings-layout"><form id="settings-form" class="settings-form"><section class="settings-section"><h2>Stock universe</h2><p>A named collection of symbols for repeatable portfolio research.</p><div class="field-grid">${field('name','Universe name',c.name??'FANGMAN')}<div class="field"><label>Preset</label><button type="button" class="button" data-action="reset-universe">Use FANGMAN · 7 stocks</button><small>Meta, Apple, NVIDIA, Alphabet, Microsoft, Amazon, Netflix.</small></div><div class="field field-full"><label for="config-universe">Stock symbols</label><textarea class="form-control" id="config-universe" name="universe" spellcheck="false" required>${esc(Array.isArray(c.universe)?c.universe.join(', '):(c.universe||''))}</textarea><small>Paste up to 1,000 symbols, separated by commas or spaces, or import a CSV with a Symbol / Ticker column.</small><div class="index-tools"><button type="button" class="button button-small" data-action="import-index">Import CSV / text</button><input id="index-file" type="file" accept=".csv,.txt,text/csv,text/plain" hidden><button type="button" class="button button-small" data-action="export-index">Export saved index</button><span id="index-feedback" role="status">${(state.config?.universe||[]).length} saved stocks</span></div></div></div></section><section class="settings-section"><h2>Portfolio limits</h2><p>These limits constrain proposal sizing. Research opinions cannot override them.</p><div class="field-grid">${field('allocation_pct','Maximum invested allocation',c.allocation_pct,{type:'number',min:0,max:100,step:1,unit:'%',help:'Total portfolio capital available to the strategy.'})}${field('max_position_pct','Maximum single position',c.max_position_pct,{type:'number',min:.1,max:100,step:.1,unit:'%',help:'Concentration limit per stock, including holdings.'})}${field('reserve_pct','Minimum cash reserve',c.reserve_pct,{type:'number',min:0,max:100,step:1,unit:'%',help:'Cash retained after proposed purchases.'})}${field('max_order_notional','Maximum order value',c.max_order_notional,{type:'number',min:1,step:.01,unit:'USD',help:'Maximum notional for each submitted paper order.'})}</div></section><section class="settings-section"><h2>Research models</h2><p>Use your Codex ChatGPT sign-in, or configure another model provider. Research uses your selected account and its limits.</p><div class="field-grid">${field('llm_provider','Provider',c.llm_provider??'codex',{placeholder:'codex',help:'codex uses your existing Codex sign-in. No API key needed.'})}${field('backend_url','Provider endpoint',c.backend_url||'',{type:'url',placeholder:'https://api.openai.com/v1',help:'Leave blank for ChatGPT. Optional for other providers.'})}${field('deep_think_llm','Deep reasoning model',c.deep_think_llm||'',{help:'Research debate, trader and portfolio decisions.'})}${field('quick_think_llm','Fast analysis model',c.quick_think_llm||'',{help:'Analyst reports and lightweight research.'})}</div></section><div class="form-actions"><p>${settingsDirty?'Unsaved draft · changes apply after saving.':'Changes apply to future runs.'}</p><button type="button" class="button" data-action="discard-settings">Discard changes</button><button class="button button-primary" type="submit" ${busy.has('config')?'disabled':''}>${busy.has('config')?'Saving…':'Save settings'}</button></div><div id="config-error" class="form-error" role="alert"></div></form><aside class="settings-note"><h3>Connected services</h3><p>Tools are discovered through your local maenifold MCP gateway.</p><div><span class="connection-endpoint">${esc(state.connection?.endpoint||'http://localhost:8080/mcp')}</span><ul class="connection-list">${['maenifold','laya','alpaca'].map(d=>{const names=Array.isArray(domains)?domains:Object.keys(domains);const found=names.some(n=>String(typeof n==='object'?n.name:n).toLowerCase().includes(d)||(d==='alpaca'&&String(n).toLowerCase().includes('alpacca')));return `<li><span class="status-dot ${found?'connected':'disconnected'}"></span><span>${d==='alpaca'?'Alpaca':d==='laya'?'Laya':'maenifold'}</span><span class="muted" style="margin-left:auto;font-size:11px">${found?'Discovered':'Not discovered'}</span></li>`;}).join('')}</ul></div><div><h3>Paper account boundary</h3><p>The service must verify its paper environment before accepting an order. Execution remains under explicit review and the pause control stays available in every workspace.</p><h3>Data freshness</h3><p>Refresh fetches broker state. Research activity updates automatically. Quotes and account values retain their snapshot timestamps.</p></div><details><summary>Connection diagnostics</summary><pre>${esc(text(state.connection))}</pre></details></aside></div>`;}
function renderDiagnostics(){const readiness=state.readiness?.ready===false?`<div class="readiness-note">${icon('settings')}<span>${esc(state.readiness.message||'Research models need configuration.')}</span><a href="#settings">Research settings</a></div>`:'';if(!state.errors||!(Array.isArray(state.errors)?state.errors.length:Object.keys(state.errors).length))return readiness;return `${readiness}<details class="diagnostics"><summary>Data source diagnostics</summary><pre>${esc(text(state.errors))}</pre></details>`;}
function previewOrder(id){const p=proposals().find(p=>p.id===id);if(!p||mutationUncertain())return;$('#order-preview').innerHTML=`<span class="badge green">Paper order</span><h2 id="order-dialog-title">${esc(p.side==='buy'?'Buy':'Sell')} ${esc(p.symbol)}</h2><p>Quantity is calculated from configured allocation policy and the current broker book. Research commentary is advisory and does not set this order size. Review the associated research and this exact limit order before manual submission to the verified Alpaca paper account.</p><dl class="order-spec"><div><dt>Quantity</dt><dd>${count(p.qty)} shares</dd></div><div><dt>Limit price</dt><dd>${money(p.limit_price)}</dd></div><div><dt>Order notional</dt><dd>${money(p.notional)}</dd></div><div><dt>Time in force</dt><dd>Day</dd></div><div><dt>Proposal</dt><dd>${esc(String(p.id).slice(0,12))}</dd></div></dl><p>${esc(p.reason||'')}</p><button class="button" data-action="inspect-proposal" data-proposal="${esc(p.id)}">Review associated research</button><button class="button button-primary order-submit" data-action="submit-order" data-proposal="${esc(p.id)}">Submit paper ${esc(p.side)} · ${count(p.qty)} ${esc(p.symbol)}</button><div id="order-error" class="dialog-error" role="alert"></div>`;$('#order-dialog').showModal();}
function download(content,filename,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportPositions(){const fields=['symbol','qty','avg_entry_price','current_price','market_value','unrealized_pl','unrealized_plpc'];const csvCell=value=>`"${String(value??'').replaceAll('"','""').replace(/^[=+@-]/,"'")}"`;download([fields.join(','),...positions().map(p=>fields.map(f=>csvCell(p[f])).join(','))].join('\r\n'),'paper-positions.csv','text/csv;charset=utf-8');}

document.addEventListener('click',async event=>{const button=event.target.closest('[data-action]');if(!button||button.disabled)return;const action=button.dataset.action;try{if(action==='discard-settings'){settingsDirty=false;settingsDraft=null;render({force:true});return;}if(action==='clear-proposal-filters'){Object.assign(listViews.proposals,{query:'',filter:'all',page:0});render();$('#proposals-search')?.focus();return;}if(action==='dismiss-error'){setError('');return;}if(action==='retry'){await readState();return;}if(action==='retry-chart'){await ensureChart(true);return;}if(action==='retry-detail'){await ensureResultDetail(true);return;}if(action==='select-symbol'){if(event.target.closest('input'))return;selectStock(button.dataset.symbol);return;}if(action==='inspect'){selectedSymbol=button.dataset.symbol;selectedRunId=state.research?.[selectedSymbol]?.run_id||selectedRunId;activePage='research';location.hash='research';render({force:true});return;}if(action==='run'){if(selectedSymbols.size>25){reviewResearch();return;}await launchResearch([...selectedSymbols],state.config_revision);return;}if(action==='stop-run'){const run=activeRun();if(run)await act('stop','/api/runs/cancel',{run_id:run.id},'Stop requested. The current agent step may finish before the run stops.');return;}if(action==='build-proposals'){await act('proposals','/api/proposals',{run_id:chosenRun()?.id},'Paper proposals updated. Review each order before submission.');activePage='orders';location.hash='orders';render({force:true});return;}if(action==='toggle-pause'){await togglePause();return;}if(action==='inspect-proposal'){const p=proposals().find(p=>p.id===button.dataset.proposal);if(p){selectedSymbol=p.symbol;selectedRunId=p.run_id;$('#order-dialog').close();activePage='research';location.hash='research';render({force:true});}return;}if(action==='preview-order'){previewOrder(button.dataset.proposal);return;}if(action==='submit-order'){button.disabled=true;button.textContent='Submitting paper order…';try{await act('submit','/api/orders',{proposal_id:button.dataset.proposal},'Paper order submitted. Check the blotter for broker status.');$('#order-dialog').close();}catch(e){$('#order-error').textContent=e.message;button.disabled=true;button.textContent='Refresh and check broker status';await readState();}return;}if(action==='cancel-order'){await cancelOrder(button.dataset.order);return;}if(action==='reset-universe'){$('#config-universe').value='META, AAPL, NVDA, GOOGL, MSFT, AMZN, NFLX';$('#config-name').value='FANGMAN';captureSettingsDraft();return;}if(action==='export-positions'){exportPositions();return;}if(action==='export-run'){const exported=await api(`/api/runs/${encodeURIComponent(chosenRun().id)}`);download(JSON.stringify(exported,null,2),`research-${chosenRun()?.id||'run'}.json`,'application/json');return;}if(action==='sort-symbol'||action==='sort-price'){listViews.watch.page=0;const field=action==='sort-symbol'?'symbol':'price';universeSort={field,direction:universeSort.field===field?-universeSort.direction:1};render();}}catch{/* The action already reports its error in the notice. */}});
document.addEventListener('change',event=>{if(event.target.id==='select-page'){for(const symbol of listPage('watch',filteredWatch()).items)event.target.checked?selectedSymbols.add(symbol):selectedSymbols.delete(symbol);render();}if(event.target.classList.contains('symbol-select')){event.target.checked?selectedSymbols.add(event.target.value):selectedSymbols.delete(event.target.value);if(event.target.checked)selectStock(event.target.value);else render();}if(event.target.id==='run-select'){selectedRunId=event.target.value;const run=chosenRun();if(!run?.symbols?.includes(selectedSymbol))selectedSymbol=run?.symbols?.[0]||selectedSymbol;syncReportView();render();readState();}if(event.target.id==='order-filter'){orderFilter=event.target.value;render();}});
document.addEventListener('click',event=>{const action=event.target.closest('[data-action]')?.dataset.action;if(action==='chart-stock'||action==='chart-equity'){chartMode=action==='chart-stock'?'stock':'equity';render();}if(action==='chart-week'||action==='chart-month'){chartPeriod=action==='chart-week'?'week':'month';render();}if(action==='refresh-source')$('#refresh').click();});
document.addEventListener('input',event=>{if(event.target.closest('#settings-form'))captureSettingsDraft();});
document.addEventListener('toggle',event=>{if(event.target.isConnected!==false&&(event.target.matches?.('.report-section')||event.target.matches?.('.report-raw'))&&(event.target.dataset.view===undefined||event.target.dataset.view===reportViewKey)){const name=event.target.dataset.report;event.target.open?openReportNames.add(name):openReportNames.delete(name);}},true);
document.addEventListener('submit',async event=>{if(event.target.id!=='settings-form')return;event.preventDefault();if(busy.has('config'))return;const submittedDraft=settingsDraft;const form=event.target;const data=new FormData(form);const c={...state.config};for(const [key,value]of data)c[key]=value;for(const key of ['allocation_pct','max_position_pct','reserve_pct','max_order_notional'])c[key]=Number(c[key]);c.backend_url=String(c.backend_url||'').trim()||null;try{c.universe=DeskLists.parseSymbols(c.universe).symbols;}catch(e){$('#config-error').textContent=e.message;return;}if(!c.universe.length){$('#config-error').textContent='Enter at least one stock symbol.';return;}if(c.allocation_pct+c.reserve_pct>100){$('#config-error').textContent='Invested allocation plus cash reserve cannot exceed 100%.';return;}if(c.max_position_pct>c.allocation_pct){$('#config-error').textContent='The single-position limit cannot exceed total invested allocation.';return;}try{await act('config','/api/config',c,'Workspace settings saved.');if(settingsDraft===submittedDraft){settingsDirty=false;settingsDraft=null;}selectedSymbols=new Set(universe().length<=50?universe():[]);render({force:true});}catch(e){if($('#config-error'))$('#config-error').textContent=e.message;}});
async function togglePause(){try{await act('pause','/api/trading/pause',{paused:!paused()},paused()?'Execution resumed. Each order still requires approval.':'Execution paused. Existing orders remain at the broker.');}catch{}}
$('#pause-trading').addEventListener('click',togglePause);
$('#refresh').addEventListener('click',async()=>{try{await act('refresh','/api/refresh',{},'Broker snapshot refreshed.');if(activePage==='overview'&&chartMode==='stock')await ensureChart(true);}catch{}});
window.addEventListener('hashchange',()=>{const next=location.hash.slice(1);if(['overview','research','orders','settings'].includes(next)){activePage=next;render({force:true});window.scrollTo(0,0);}});
document.addEventListener('keydown',event=>{if(event.altKey&&event.key.toLowerCase()==='r'&&!['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName)){event.preventDefault();$('#refresh').click();}});
readState();
setInterval(()=>{if(activePage==='overview')refreshQuotes();},60000);
document.addEventListener('click',event=>{if(event.target.closest('[data-action="refresh-quotes"]'))refreshQuotes({manual:true});});
setInterval(()=>{if(rateLimitedUntil){if(!coolingDown()){rateLimitedUntil=0;errorMessage='The cooldown has ended. Retry the chart or refresh when ready.';const chartError=$('.empty-chart p');if(chartError&&chartErrors.get(selectedSymbol)?.includes('429'))chartError.textContent='Rate limit retries ended. You can try loading history again.';}renderNotice();$('#refresh').disabled=coolingDown()||busy.has('refresh');$$('[data-action="retry-chart"]').forEach(button=>button.disabled=coolingDown());}if(!document.hidden&&!busy.size&&state?.connection?.connected&&!stateErrorMessage&&activeRun())readState();},5000);

document.addEventListener('input',event=>{const name=event.target.dataset.listQuery;if(name&&listViews[name]){listViews[name].query=event.target.value;listViews[name].page=0;render();}});
document.addEventListener('change',async event=>{const name=event.target.dataset.listFilter||event.target.dataset.listSize;if(name&&listViews[name]){if(event.target.dataset.listFilter)listViews[name].filter=event.target.value;else listViews[name].size=Number(event.target.value);listViews[name].page=0;render();}if(event.target.id==='index-file'){const file=event.target.files?.[0];if(!file)return;try{if(file.size>1048576)throw new Error('Use a file smaller than 1 MB.');let deadline;let content;try{content=await Promise.race([file.text(),new Promise((_,reject)=>deadline=setTimeout(()=>reject(new Error('File reading exceeded 15 seconds. Try a smaller file.')),15000))]);}finally{clearTimeout(deadline);}const parsed=DeskLists.parseSymbols(content,{file:true});$('#config-universe').value=parsed.symbols.join(', ');captureSettingsDraft();$('#index-feedback').textContent=`${parsed.symbols.length} stocks imported · ${parsed.duplicates} duplicates removed. Save to apply.`;$('#config-error').textContent='';}catch(e){$('#config-error').textContent=e.message;}event.target.value='';}});
document.addEventListener('click',async event=>{const button=event.target.closest('[data-action]');if(!button||button.disabled)return;const action=button.dataset.action;try{if(action==='list-page'){listViews[button.dataset.list].page+=Number(button.dataset.direction);render();}if(action==='select-matches'){for(const symbol of filteredWatch())selectedSymbols.add(symbol);render();}if(action==='clear-selection'){selectedSymbols.clear();render();}if(action==='linked-step'){const stocks=filteredWatch();selectStock(stocks[stocks.indexOf(selectedSymbol)+Number(button.dataset.direction)]||selectedSymbol);}if(action==='find-stock'){listViews.watch.query=selectedSymbol;listViews.watch.filter='all';listViews.watch.page=0;render();$('#watch-search')?.focus();}if(action==='select-unfinished'){selectedSymbols=new Set((chosenRun()?.symbols||[]).filter(symbol=>universe().includes(symbol)&&currentResult(symbol)?.status!=='completed'));activePage='overview';location.hash='overview';render();showToast(`${selectedSymbols.size} stocks selected. Review the selection before starting research.`);}if(action==='confirm-research'&&pendingResearch){button.disabled=true;try{await launchResearch(pendingResearch.symbols,pendingResearch.revision);$('#research-dialog').close();pendingResearch=null;}catch(e){$('#research-error').textContent=e.message;button.disabled=false;}}if(action==='import-index'){$('#index-file').click();}if(action==='export-index')download('Symbol\r\n'+universe().join('\r\n'),'stock-index.csv','text/csv;charset=utf-8');}catch(e){setError(e.message);}});
