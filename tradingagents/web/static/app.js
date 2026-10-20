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
const marketDate = () => {const parts=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());return ['year','month','day'].map(type=>parts.find(p=>p.type===type).value).join('-');};
const text = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const iconPaths = {overview:'M3 3h7v8H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 15h7v6H3z',research:'M9 3h6M10 3v6l-6 9a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-6-9V3M8 15h8',orders:'M8 3h8v4H8zM8 5H5v16h14V5h-3M8 12h8M8 16h5',settings:'M4 7h16M4 17h16M8 4v6M16 14v6',play:'m9 5 11 7-11 7z',chart:'M3 3v18h18M7 14l4-4 4 2 5-7',arrow:'M5 12h14m-6-6 6 6-6 6',stop:'M6 6h12v12H6z',check:'m5 12 4 4L19 6',link:'m9 15 6-6M8 17l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M16 7l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',download:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4'};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${iconPaths[name]||iconPaths.overview}"/></svg>`;
const companyName = symbol => state?.company_names?.[symbol] || symbol;
const reportNames = {market_report:'Market analysis',sentiment_report:'Sentiment analysis',news_report:'News analysis',fundamentals_report:'Fundamentals',investment_plan:'Research committee decision',trader_investment_plan:'Trader proposal',final_trade_decision:'Portfolio decision',investment_debate_state:'Bull / bear debate',risk_debate_state:'Risk committee',decision:'Decision'};
let state = null;
let quoteRefreshAt = 0, quoteRefreshFailed = false;

async function refreshQuotes({manual=false}={}) {
  if(!state?.connection?.connected){if(manual)setError('Quotes unavailable while disconnected. Start the gateway, then use Refresh to reconnect.');return;}
  if(document.hidden||busy.size||stateFetch||coolingDown('/api/quotes/refresh')||!state?.connection?.connected)return;
  if(!manual&&Date.now()<quoteRefreshAt)return;
  quoteRefreshAt=Date.now()+60000;
  busy.add('quotes');
  render();
  try {
    const fresh=await api('/api/quotes/refresh',{}, {timeoutMs:50000});
    for(const key of ['quotes','clock','quotes_updated_at'])state[key]=fresh[key];
    quoteRefreshFailed=false;
    if(manual)errorMessage='';
    render();
  } catch(e) {
    quoteRefreshFailed=true;
    setError(`Quote update failed: ${e.message} Use Refresh to retry; automatic updates will also retry.`);
  } finally {busy.delete('quotes');render();}
}

function liveQuoteState(q){
  if(q?.price==null)return 'missing';
  if(q.freshness_configured!==true||number(q.max_age_seconds)===null)return 'unconfigured';
  const observed=Date.parse(q.timestamp),age=(Date.now()-observed)/1000;
  return !Number.isFinite(age)||age<0||age>Number(q.max_age_seconds)?'stale':'current';
}
function quoteFreshness(q){
  const status=liveQuoteState(q);
  return status==='missing'?'Price unavailable':status==='unconfigured'?'Freshness limit not configured':(status==='stale'?'Outside':'Within')+' configured '+q.max_age_seconds+'s age limit';
}
function quoteStatus(q){
  if(q?.price==null)return q?.error||'Latest price unavailable';
  const session=q.session||((state?.clock?.is_open===true)?'open':state?.clock?.is_open===false?'closed':'unknown');
  const age=(Date.now()-Date.parse(q.timestamp))/1000;
  return (q.feed||'Provider')+' '+(q.basis==='quote_midpoint'?'quote midpoint':'last trade')+' · market '+session+' · '+(Number.isFinite(age)&&age>=0?Math.floor(age)+'s old':'age unavailable')+' · '+quoteFreshness(q)+' · '+date(q.timestamp)+' '+time(q.timestamp);
}
let activePage = ['overview','research','orders','settings','journal'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
const linkedResearch = new URLSearchParams(location.search);
const linkedSymbol = (linkedResearch.get('symbol')||'').toUpperCase();
let selectedSymbols = new Set();
const researchSelection=()=>[...selectedSymbols].filter(symbol=>universe().includes(symbol));
let selectedSymbol = '';
let selectedRunId = linkedResearch.get('run_id')||'';
let busy = new Set();
const pendingCancellations = new Set();
let errorMessage = '';
let toastTimer;
let stateFetch = false;
let stateWait=null,stateDone=null;
let settingsDirty = false;
let settingsDraft = null;
function captureSettingsDraft(){const form=$('#settings-form');if(!form)return;settingsDraft={...state.config,...Object.fromEntries(new FormData(form))};settingsDirty=true;}
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
function syncReportView(){const key=`${chosenRun()?.id||selectedRunId}:${selectedSymbol}`;if(key!==reportViewKey){reportViews.set(reportViewKey,{open:openReportNames,scroll:reportViews.get(reportViewKey)?.scroll||0});reportViewKey=key;openReportNames=reportViews.get(key)?.open||new Set(['final_trade_decision']);}return key;}
let orderFilter = 'all';
let universeSort = {field:'default',direction:1};
let chartMode = 'stock';
let chartPeriod = 'month';
const chartEvidence=new Map();
let selectedBarDate=null;
const evidenceKey=()=>`${chosenRun()?.id}:${selectedSymbol}`;
const selectedEvidence=()=>chartEvidence.get(evidenceKey());

let chartSize = {width:610,height:238};
let chartResizeObserver = null;
let stateErrorMessage = '';
const rateLimits=new Map();
const rateLimitScope=(path,body)=>path.split('?')[0]+(body?.action?':'+body.action:'')+(body?.provider?':'+body.provider:'');
const coolingDown=(path,body)=>Date.now()<(rateLimits.get(rateLimitScope(path,body))||0);
function rateLimitMessage(path,body){return 'This request was rate limited (429). Retry after '+time(rateLimits.get(rateLimitScope(path,body)))+'. Other operations are unaffected.';}
function selectStock(symbol){
  if(!marketSymbols().includes(symbol)&&!chosenRun()?.symbols?.includes(symbol))return;
  selectedSymbol=symbol;selectedBarDate=null;
  if(activePage==='overview'){
    chartMode='stock';
    selectedRunId=(chosenRun()?.symbols?.includes(symbol)?chosenRun():runs().find(r=>r.symbols?.includes(symbol)))?.id||'';
  }
  syncReportView();render();
}


const listViews=Object.fromEntries(['watch','research','positions','proposals','orders'].map(name=>[name,{query:'',filter:'all',page:0,size:25}]));
function listToolbar(name,filters=[]){const v=listViews[name];return `<div class="collection-toolbar"><label class="collection-search" for="${name}-search">Find ${name==='watch'?'stocks':name}<input id="${name}-search" type="search" class="form-control" data-list-query="${name}" value="${esc(v.query)}" placeholder="Search symbols" autocomplete="off"></label>${filters.length?`<label for="${name}-scope">Show<select id="${name}-scope" class="form-control" data-list-filter="${name}">${filters.map(([key,label])=>`<option value="${key}" ${v.filter===key?'selected':''}>${esc(label)}</option>`).join('')}</select></label>`:''}</div>`;}
function listPage(name,items){const v=listViews[name],p=DeskLists.page(items,v.page,v.size);v.page=p.current;return p;}
function listPager(name,p){return `<div class="collection-pager"><span>${p.first}–${p.last} of ${p.total}</span><label for="${name}-size">Rows <select class="form-control" id="${name}-size" data-list-size="${name}">${[25,50,100].map(n=>`<option ${p.size===n?'selected':''}>${n}</option>`).join('')}</select></label><div><button class="button button-small" data-action="list-page" data-list="${name}" data-direction="-1" aria-label="Previous ${name} page" ${!p.current?'disabled':''}>Previous</button><span> ${p.current+1} / ${p.pages} </span><button class="button button-small" data-action="list-page" data-list="${name}" data-direction="1" aria-label="Next ${name} page" ${p.current+1>=p.pages?'disabled':''}>Next</button></div></div>`;}
function matchesStock(symbol,query){return !query||`${symbol} ${companyName(symbol)}`.toLowerCase().includes(query.trim().toLowerCase());}
function reviewLabel(result){if(['failed','cancelled'].includes(result?.status))return 'Research '+result.status;const social=result?.social_sentiment;return social?'Social screening '+String(social.status||'not recorded').replaceAll('_',' '):'Social screening not recorded';}
function filteredWatch(){const v=listViews.watch;return sortedUniverse().filter(symbol=>{if(!matchesStock(symbol,v.query))return false;const r=state.research?.[symbol],q=liveQuoteState(state.quotes?.[symbol]);return v.filter==='all'||v.filter==='selected'&&selectedSymbols.has(symbol)||v.filter==='held'&&positions().some(p=>p.symbol===symbol)||v.filter==='unresearched'&&!(r?.status==='completed'&&r.trade_date===DeskLists.dateNY())||v.filter===q;});}
function emptyMatches(){return '<div class="detail-note">No matches. Change the search or filter to see more stocks. Your research selection is preserved.</div>';}

function persistView(){try{localStorage.setItem('paper-desk-view',JSON.stringify({listViews,selected:[...selectedSymbols],symbol:selectedSymbol,sort:universeSort}));}catch{}}
function restoreView(){try{const saved=JSON.parse(localStorage.getItem('paper-desk-view')||'null');if(!saved)return false;for(const [name,value]of Object.entries(saved.listViews||{})){if(!listViews[name]||!value||typeof value!=='object')continue;listViews[name]={query:typeof value.query==='string'?value.query.slice(0,100):'',filter:typeof value.filter==='string'?value.filter:'all',page:Number.isInteger(value.page)?value.page:0,size:[25,50,100].includes(value.size)?value.size:25};}selectedSymbols=new Set((Array.isArray(saved.selected)?saved.selected:[]).filter(symbol=>universe().includes(symbol)));if(universe().includes(saved.symbol))selectedSymbol=saved.symbol;if(['default','symbol','price'].includes(saved.sort?.field))universeSort={field:saved.sort.field,direction:saved.sort.direction===-1?-1:1};return true;}catch{return false;}}
let pendingResearch=null;
async function launchResearch(symbols,revision){const result=await act('run','/api/runs',{symbols,config_revision:revision},'Research started. No orders have been placed.');if(result?.id||result?.run_id)selectedRunId=result.id||result.run_id;activePage='research';location.hash='research';await readState();}
function reviewResearch(){const symbols=researchSelection();if(!symbols.length)return;const estimate=DeskLists.estimate(runs(),state.config,symbols.length);pendingResearch={symbols,revision:state.config_revision};$('#research-preview').innerHTML=`<span class="badge neutral">Research only</span><h2 id="research-dialog-title">Research ${symbols.length} stocks</h2><p>The universe remains ${marketSymbols().length} configured stocks. This run analyzes the selected ${symbols.length} sequentially and places no orders.</p><dl class="order-spec"><div><dt>Fast analysis</dt><dd>${esc(state.config.quick_think_llm)}</dd></div><div><dt>Deep reasoning</dt><dd>${esc(state.config.deep_think_llm)}</dd></div><div><dt>Trade date</dt><dd>${esc(DeskLists.dateNY())} · New York</dd></div><div><dt>Observed duration</dt><dd>${estimate?`About ${DeskLists.duration(estimate.seconds)}, based on ${estimate.samples} completed stocks with these models`:'No completed observations for this configuration yet'}</dd></div></dl><p>A cost estimate is unavailable; actual model usage depends on the selected research. A long sweep can cross a trading day. Account usage limits may interrupt research. Completed evidence is retained; paper proposals still require current data and individual review.</p><details><summary>Selected symbols (${symbols.length})</summary><p class="selection-preview">${esc(symbols.join(', '))}</p></details><button class="button button-primary" data-action="confirm-research">Start ${symbols.length}-stock research</button><div id="research-error" class="dialog-error" role="alert"></div>`;$('#research-dialog').showModal();}

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
  finally{detailRequests.delete(key);if(['overview','research'].includes(activePage)&&chosenRun()?.id===run.id&&selectedSymbol===summary.symbol)render();}
}

async function ensureChart(force=false){
  const run=chosenRun(),key=evidenceKey(),symbol=selectedSymbol;
  if(!symbol||!run||!run.symbols?.includes(symbol)||chartRequests.size)return;
  if(!force&&(chartErrors.has(key)||chartEvidence.has(key)))return;
  chartRequests.add(key);chartErrors.delete(key);
  try{
    const detail=await api(`/api/instruments/${encodeURIComponent(symbol)}?run_id=${encodeURIComponent(run.id)}${force?'&refresh=1':''}`);
    if(detail.symbol!==symbol||detail.run_id!==run.id||!Array.isArray(detail.bars))throw new Error('Market evidence does not match the selected research.');
    chartEvidence.set(key,detail);chartLoadedAt.set(key,Date.now());
  }catch(error){chartErrors.set(key,error.message);}
  finally{chartRequests.delete(key);if(activePage==='overview')render();}
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
const universe = () => state?.config?.universe || [];
const marketSymbols=()=>universe();
const activeRun = () => runs().find(r => !r.history_source && ['queued','running','cancelling','cancel_requested'].includes(r.status));
const chosenRun = () => runs().find(r => r.id===selectedRunId) || runs().find(r=>r.symbols?.includes(selectedSymbol)) || runs()[0];
const paused = () => (state?.commands?.data?.new_orders_blocked ?? state?.health?.new_orders_blocked ?? false)!==false;
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
function renderNotice(){const notice=$('#notice'); const conn=state?.connection;let message=errorMessage||stateErrorMessage;let cls='error';if(!message&&state&&(!conn?.connected||!conn?.account_verified)){message=conn?.message || (!conn?.connected?'Account connection unavailable. Start Nautilus, then refresh.':'Account has not been verified. Refresh the configured connection before submitting orders.');cls='';}if(!message&&paused()){message=state.browse_only?'Review-only session. Local human proposals and basket drafts can be saved. New research, native Nautilus drafts, approvals, admission and broker writes are disabled.':'New orders are blocked. Account monitoring and cancellation of existing working orders remain available; use account order controls to review the block.';cls='';}notice.hidden=!message;notice.className=`notice ${cls}`;notice.innerHTML=message?`${esc(message)}${errorMessage?'<button class="icon-button" data-action="dismiss-error" aria-label="Dismiss error">×</button>':''}`:'';}
async function api(path, body, {timeoutMs=path.startsWith('/api/instruments/')||['/api/refresh','/api/runs','/api/proposals'].includes(path)?550000:body===undefined?15000:120000,signal}={}){
  if(coolingDown(path,body))throw new Error(rateLimitMessage(path,body));
  const controller=typeof AbortController==='function'?new AbortController():null;
  const abort=()=>controller?.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
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
        const scope=rateLimitScope(path,body);rateLimits.set(scope,Math.max(rateLimits.get(scope)||0,Date.now()+delay));
        const limited=new Error(rateLimitMessage(path,body));limited.status=429;
        renderNotice();throw limited;
      }
      let payload;
      try{payload=await response.json();}catch{if(timedOut)throw new Error('timeout');throw new Error(`The local service returned an unreadable response (${response.status}).`);}
      if(!response.ok){const error=new Error(payload?.error||`Request failed (${response.status}).`);error.status=response.status;throw error;}
      return payload;
    })();
    return await Promise.race([request,deadline]);
  }catch(error){
    if(signal?.aborted)throw new Error('Request canceled.');
    if(timedOut||error.name==='AbortError'){
      const message=body===undefined?'The local service did not respond in time. Your last snapshot is still shown; try refreshing.':
        path==='/api/orders'?'The submission request timed out. Refresh broker status before taking another action; its outcome may be unknown.':
        path==='/api/orders/cancel'?'The cancellation request timed out; its outcome may be unknown. Refresh to reconcile broker status. Do not resend cancellation.':
        'The request timed out. Refresh the workspace to check its status before trying again.';
      throw new Error(message);
    }
    throw error;
  }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
async function readState({force=false,timeoutMs}={}){
  if(stateFetch){await stateWait;if(!force)return;}
  stateFetch=true;stateWait=new Promise(resolve=>stateDone=resolve);
  try{
    let fresh;
    try{fresh=await api(`/api/state?compact=1${selectedRunId?`&run_id=${encodeURIComponent(selectedRunId)}`:''}`,undefined,timeoutMs?{timeoutMs}:undefined);}
    catch(error){
      if(error.status!==403)throw error;
      const session=await fetch('/',{cache:'no-store'});if(!session.ok)throw error;
      fresh=await api(`/api/state?compact=1${selectedRunId?`&run_id=${encodeURIComponent(selectedRunId)}`:''}`,undefined,timeoutMs?{timeoutMs}:undefined);
    }
    if(state?.server_instance_id===fresh.server_instance_id&&Number.isInteger(state.snapshot_sequence)&&fresh.snapshot_sequence<=state.snapshot_sequence){if(stateErrorMessage){stateErrorMessage='';render();}return;}
    if(state?.store_generation&&state.store_generation!==fresh.store_generation){UniverseReview.generationChanged();resultDetails.clear();chartEvidence.clear();journalRecord=null;journalCollections.clear();journalCollection='';}

    const first=!state;
    const linkedRun=first&&linkedSymbol?fresh.runs.find(r=>(!selectedRunId||r.id===selectedRunId)&&r.symbols?.includes(linkedSymbol)):null;
    if(first&&linkedSymbol&&!linkedRun)throw new Error('No saved research matches this stock and run.');
    fresh.bars=fresh.bars||state?.bars||{};
    state=fresh;
    stateErrorMessage='';
    if(first&&!restoreView())selectedSymbols=new Set(universe().length<=50?universe():[]);
    else for(const s of selectedSymbols)if(!universe().includes(s)&&!positions().some(p=>p.symbol===s))selectedSymbols.delete(s);
    if(linkedRun){selectedSymbol=linkedSymbol;selectedRunId=linkedRun.id;}
    if(!selectedSymbol||!marketSymbols().includes(selectedSymbol)&&!chosenRun()?.symbols?.includes(selectedSymbol))selectedSymbol=universe()[0]||chosenRun()?.symbols?.[0]||'';
    render({force});
  }catch(e){
    stateErrorMessage=e.message;if(state)render();else renderNotice();
    if(!state)$('#main').innerHTML=`<div class="initial-state"><h1>The desk is not connected</h1><p>${esc(e.message)}</p><button class="button button-primary" data-action="retry">Try again</button></div>`;
  }finally{stateFetch=false;stateDone?.();stateDone=null;}

}
async function act(key,path,body,success){if(busy.has(key))return;busy.add(key);errorMessage='';render();try{const result=await api(path,body);if(success)showToast(success);await readState({force:true});return result;}catch(e){setError(e.message);throw e;}finally{busy.delete(key);render();}}
const disclosureViews=new Map();
function render({force=false}={}){if(!state)return;const disclosureKey=activePage+':'+selectedSymbol,previousMain=document.querySelector('#main');if(previousMain?.dataset.contextKey){disclosureViews.set(previousMain.dataset.contextKey,Array.from(previousMain.querySelectorAll('details[id]')).filter(d=>d.open).map(d=>d.id));}const before=document.activeElement,caret=[before?.selectionStart,before?.selectionEnd];renderChrome();renderNotice();if(activePage==='settings'&&settingsDirty&&$('#settings-form')?.isConnected&&!force)return;const focused=before;const focusId=focused?.id;const scrollPanel=$('#research-detail-scroll');const readingAnchor=reportReadingAnchor(scrollPanel);const previousView=scrollPanel?.dataset?.view;const reportScroll=scrollPanel?.scrollTop||0;if(previousView!==undefined)reportViews.set(previousView,{open:reportViews.get(previousView)?.open||openReportNames,scroll:reportScroll});syncReportView();const nextReportScroll=previousView===reportViewKey?reportScroll:(reportViews.get(reportViewKey)?.scroll||0);const main=$('#main'),scrolls=$$('.table-scroll,.research-rows',main).map(el=>({top:el.scrollTop,left:el.scrollLeft}));main.innerHTML=activePage==='overview'?renderOverview():activePage==='research'?renderResearch():activePage==='orders'?renderOrders():activePage==='journal'?renderJournal():(renderSettings()+renderHealth());main.dataset.contextKey=disclosureKey;for(const id of disclosureViews.get(disclosureKey)||[]){const detail=document.getElementById(id);if(detail?.tagName==='DETAILS')detail.open=true;}if(activePage==='settings'&&state.readiness?.ready===false)$('.page-heading',main).insertAdjacentHTML('afterend',`<div class="error-detail">${esc(state.readiness.message)}</div>`);if(focusId){let next=document.getElementById(focusId);if(next&&(focused?.dataset?.listQuery||['watchlist-name','investor-note'].includes(focused?.id))&&next.tagName===focused.tagName){next.replaceWith(focused);next=focused;}if(next&&next.tagName===focused.tagName)next.focus({preventScroll:true});if(next?.setSelectionRange&&caret[0]!==null&&caret[0]!==undefined)try{next.setSelectionRange(...caret);}catch{}}if(!focusId&&focused?.tagName==='A'&&focused.getAttribute?.('href')){const next=$$('#navigation a').find(el=>el.getAttribute('href')===focused.getAttribute('href'));next?.focus({preventScroll:true});}if(!focusId&&focused?.dataset?.action){const next=$$('[data-action]',main).find(el=>el.dataset.action===focused.dataset.action&&el.dataset.symbol===focused.dataset.symbol&&el.dataset.proposal===focused.dataset.proposal&&el.dataset.list===focused.dataset.list&&el.dataset.direction===focused.dataset.direction&&el.dataset.order===focused.dataset.order);if(next)next.focus({preventScroll:true});}if($('#research-detail-scroll')){$('#research-detail-scroll').scrollTop=nextReportScroll;if(previousView===reportViewKey)restoreReadingAnchor($('#research-detail-scroll'),readingAnchor);}$$('.table-scroll,.research-rows',main).forEach((el,i)=>{if(scrolls[i]){el.scrollTop=scrolls[i].top;el.scrollLeft=scrolls[i].left;}});persistView();observeChartSize();if(activePage==='overview'&&chartMode==='stock'&&$('.chart-wrap'))ensureChart();if(activePage==='research')ensureResultDetail();}
function observeChartSize(){chartResizeObserver?.disconnect();const target=$('.chart-wrap');if(!target||typeof ResizeObserver==='undefined')return;chartResizeObserver=new ResizeObserver(entries=>{const {width,height}=entries[0].contentRect;if(width<120||height<100)return;if(Math.abs(chartSize.width-width)>.5||Math.abs(chartSize.height-height)>.5){chartSize={width,height};target.innerHTML=chartMode==='stock'?stockChart():equityChart();}});chartResizeObserver.observe(target);}
let navigationMarkup='';
function renderChrome(){const labels={overview:'Portfolio overview',research:'Agent research',orders:'Orders and drafts',settings:'Settings',journal:'Decision journal'};const nextNavigation=Object.entries(labels).map(([page,label])=>`<a class="nav-link" href="#${page}" ${page===activePage?'aria-current="page"':''} aria-label="${label}">${icon(page)}<span>${label}</span>${page==='orders'&&proposals().some(p=>['pending','proposed','ready'].includes(p.status))?`<span class="nav-count">${proposals().filter(p=>['pending','proposed','ready'].includes(p.status)).length}</span>`:''}</a>`).join('');if(nextNavigation!==navigationMarkup){$('#navigation').innerHTML=nextNavigation;navigationMarkup=nextNavigation;}$('#page-label').textContent=labels[activePage];$('#universe-name').textContent=state.config?.name||'Custom universe';$('#last-updated').textContent=`${({open:'Market open',closed:'Market closed',unknown:'Market status unknown'})[(state.connection?.connected&&typeof state.clock?.is_open==='boolean')?(state.clock.is_open?'open':'closed'):DeskLists.marketState(state.clock)]} · ${state.updated_at?`Snapshot ${time(state.updated_at)}`:'No account snapshot'}`;$('#gateway-status').innerHTML=`<span class="status-dot ${!stateErrorMessage&&state.connection?.connected?'connected':'disconnected'}"></span><span>${stateErrorMessage?'Connection unconfirmed · last snapshot':state.connection?.connected?'Nautilus connected':'Nautilus stopped / disconnected'}</span>`;const pauseButton=$('#pause-trading');pauseButton.textContent=paused()?'New orders paused · manage':'New orders not paused · manage';const orderStatus=orderReadiness();$('#order-status').innerHTML='<strong>'+esc(orderStatus.label)+'</strong> · '+esc(orderStatus.reasons.join('; ')||(!orderStatus.items.length?'Create or review an order to approve its exact terms.':orderStatus.ready.length?'Server checks run again at Submit.':'Review the order checks below.'))+' <a href="#orders">View orders</a>';pauseButton.classList.toggle('is-paused',paused());pauseButton.disabled=false;$('#refresh').disabled=busy.has('refresh')||coolingDown(state.connection?.connected?'/api/quotes/refresh':'/api/refresh');$('#refresh span').textContent=busy.has('refresh')?'Refreshing…':'Refresh';if(typeof renderNautilus==='function')renderNautilus(state.nautilus||{});}
function researchButton(){const count=researchSelection().length;if(state?.browse_only)return '<span class="badge neutral">Existing-record review - new research disabled</span>';if(state.readiness?.ready===false&&state.config?.llm_provider!=='chatgpt')return `<a class="button button-primary" href="#settings" title="${esc(state.readiness.message||'Configure the research models to continue')}">${icon('settings')}Configure research</a>`;return `<button class="button button-primary" data-action="run" ${busy.has('run')||activeRun()||!count||coolingDown('/api/runs')?'disabled':''}>${icon('play')}${busy.has('run')?'Starting…':activeRun()?'Research running':`Run research${count?` (${count})`:''}`}</button>`;}
function pageHeader(title,description,actions=''){return `<div class="page-heading"><div><div class="heading-line"><h1>${title}</h1>${state.browse_only?'<span class="badge neutral">'+(activePage==='overview'?'Read-only':'Saved records')+'</span>':stateErrorMessage?'<span class="badge amber">Last known account · refresh failed</span>':state.connection?.account_verified?'<span class="badge green">Account verified</span>':'<span class="badge amber">Account unverified</span>'}</div><p>${description}</p></div><div class="button-group">${actions}</div></div>`;}
function equityChart(){const h=state.history||{};const values=(h.equity||[]).map((v,i)=>({value:number(v),timestamp:h.timestamp?.[i]})).filter(p=>p.value!==null);if(values.length<2)return `<div class="empty-chart">${icon('chart')}<h3>No equity history yet</h3><p>Refresh the connected account to load its recorded equity. Missing points are never estimated.</p></div>`;const w=chartSize.width,hgt=chartSize.height,left=8,right=86,top=17,bottom=28;let min=Math.min(...values.map(p=>p.value)),max=Math.max(...values.map(p=>p.value));const pad=Math.max((max-min)*.15,max*.0001,1);min-=pad;max+=pad;const x=i=>left+i/(values.length-1)*(w-left-right);const y=v=>top+(max-v)/(max-min)*(hgt-top-bottom);const path=values.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v.value).toFixed(2)}`).join(' ');return `<svg class="equity-chart" viewBox="0 0 ${w} ${hgt}" role="img" aria-label="Account equity from ${esc(date(values[0].timestamp))} to ${esc(date(values.at(-1).timestamp))}: ${esc(money(values[0].value))} to ${esc(money(values.at(-1).value))}">${[0,.5,1].map(f=>{const val=min+(max-min)*f;return `<line class="grid" x1="${left}" y1="${y(val)}" x2="${w-right}" y2="${y(val)}"/><text x="${w-right+10}" y="${y(val)+4}">${esc(money(val))}</text>`;}).join('')}<path class="series" d="${path}"/><text x="${left}" y="${hgt-5}">${esc(date(values[0].timestamp))}</text><text x="${w-right}" y="${hgt-5}" text-anchor="end">${esc(date(values.at(-1).timestamp))}</text></svg>`;}
function sortedUniverse(){let symbols=[...marketSymbols()];if(universeSort.field==='symbol')symbols.sort((a,b)=>a.localeCompare(b)*universeSort.direction);if(universeSort.field==='price')symbols.sort((a,b)=>((number(state.quotes?.[a]?.price)||0)-(number(state.quotes?.[b]?.price)||0))*universeSort.direction);return symbols;}
function watchlist(){const matches=filteredWatch(),p=listPage('watch',matches);return `<section class="panel watchlist-panel"><div class="panel-header"><div><h2>${esc(state.config?.name||'Watchlist')}</h2><p>${marketSymbols().length} configured stocks · ${selectedSymbols.size} selected for research</p><p>Latest quotes: ${quoteRefreshFailed?'last update failed; retry scheduled':'Nautilus / Alpaca snapshot, polled every 30s'} · IEX${state.quotes_updated_at?' · checked '+esc(time(state.quotes_updated_at)):''}</p></div>${!state.connection?.connected?'<p>Latest quotes unavailable: Nautilus is disconnected. Saved research bars remain readable. <button class="link-button" data-action="refresh-source">Connect Nautilus</button>.</p>':''}<div class="quote-actions"><button class="link-button" data-action="refresh-quotes" ${!state.connection?.connected||busy.size||coolingDown('/api/quotes/refresh')?'disabled':''}>${busy.has('quotes')?'Updating...':'Update quotes'}</button><a class="link-button" href="#settings">Edit index</a></div></div>${listToolbar('watch',[['all','All stocks'],['selected','Selected for research'],['held','Held positions'],['unresearched','Needs research today'],['missing','Missing quotes'],['stale','Stale quotes']])}<div class="selection-actions"><button class="link-button" data-action="select-matches" ${!matches.length?'disabled':''}>Select ${matches.length} matches</button><button class="link-button" data-action="clear-selection" ${!selectedSymbols.size?'disabled':''}>Clear selection</button><span>${selectedSymbols.size} selected across all pages</span></div><div class="table-scroll"><table class="data-table watchlist-table"><thead><tr><th class="checkbox-cell"><input type="checkbox" id="select-page" aria-label="Select the ${p.items.length} stocks on this page" ${p.items.length&&p.items.every(s=>selectedSymbols.has(s))?'checked':''}></th><th class="asset-cell"><button class="table-sort" data-action="sort-symbol">Symbol</button></th><th><button class="table-sort" data-action="sort-price">Last</button></th><th>Change</th></tr></thead><tbody>${p.items.map(symbol=>{const q=state.quotes?.[symbol]||{},r=state.research?.[symbol],fresh=liveQuoteState(q);return `<tr data-action="select-symbol" data-symbol="${esc(symbol)}" class="${symbol===selectedSymbol?'selected-row':''}"><td class="checkbox-cell"><input type="checkbox" class="symbol-select" id="select-symbol-${esc(symbol)}" value="${esc(symbol)}" aria-label="Include ${esc(symbol)} in research" ${selectedSymbols.has(symbol)?'checked':''}></td><td class="asset-cell"><button class="ticker-button" data-action="select-symbol" data-symbol="${esc(symbol)}" aria-pressed="${symbol===selectedSymbol}">${esc(symbol)}</button><span class="asset-name">${esc(companyName(symbol))}</span><span class="asset-name">${esc(r?.status==='completed'?r?.rating||'Completed':r?.status||'Not researched')} · ${esc(reviewLabel(r))}</span>${r?.trade_date?`<span class="asset-name">${esc(r.trade_date)}</span>`:''}</td><td>${money(q.price)}<span class="asset-name ${['current','closed'].includes(fresh)?'':'negative'}">${esc(quoteStatus(q))}</span></td><td class="${color(q.change_pct)}">${percent(q.change_pct)}</td></tr>`;}).join('')}</tbody></table></div>${!matches.length?emptyMatches():''}${listPager('watch',p)}</section>`;}
function positionsTable(){const page=boundedItems('positions',positions());if(sourceError('positions'))return unavailablePanel('Positions','positions');return `<section class="panel"><div class="panel-header"><div><h2>Positions</h2><p>Broker holdings · actual account exposure</p></div><button class="button button-small button-quiet" data-action="export-positions" ${positions().length?'':'disabled'}>${icon('download')}CSV</button></div>${listToolbar('positions')}${!positions().length?`<div class="empty-state compact">${icon('overview')}<h3>${state.account?'No open positions':'Account not loaded'}</h3><p>${state.account?'Broker fills appear here with cost basis and unrealized P/L.':'Refresh to retrieve holdings from the connected account.'}</p></div>`:`<div class="table-scroll"><table class="data-table"><thead><tr><th>Symbol</th><th>Quantity</th><th>Avg. cost</th><th>Market value</th><th>Unrealized P/L</th><th>Weight</th></tr></thead><tbody>${page.items.map(p=>{const eq=number(state.account?.equity);const weight=eq?number(p.market_value)!==null?Math.abs(Number(p.market_value))/eq*100:null:null;return `<tr><td><button class="ticker-button" data-action="inspect" data-symbol="${esc(p.symbol)}">${esc(p.symbol)}</button></td><td>${count(p.qty)}</td><td>${money(p.avg_entry_price)}</td><td>${money(p.market_value)}</td><td class="${color(p.unrealized_pl)}">${money(p.unrealized_pl)}<span class="asset-name ${color(p.unrealized_plpc)}">${number(p.unrealized_plpc)!==null?percent(Number(p.unrealized_plpc)*100):''}</span></td><td>${weight===null?'—':`${weight.toFixed(1)}%`}<span class="allocation"><span style="width:${Math.min(100,Math.max(0,weight||0))}%"></span></span></td></tr>`;}).join('')}</tbody></table></div>`}${positions().length&&!page.total?emptyMatches():''}${positions().length?listPager('positions',page):''}</section>`;}
function displayedBars(){
  const bars=selectedEvidence()?.bars||[];if(!bars.length)return [];
  const start=new Date(bars.at(-1).t);
  if(chartPeriod==='week')start.setUTCDate(start.getUTCDate()-7);
  else start.setUTCMonth(start.getUTCMonth()-({month:1,quarter:3,half:6}[chartPeriod]||1));
  return bars.filter(b=>new Date(b.t)>=start);
}
function stockChart(){
  const error=chartErrors.get(evidenceKey()),bars=displayedBars();
  if(!chosenRun()?.symbols?.includes(selectedSymbol))return '<div class="empty-chart"><h3>No saved research for this stock</h3><p>Its latest engine price is shown in the watchlist. No research has been started.</p></div>';
  if(error)return `<div class="empty-chart"><h3>Market evidence unavailable</h3><p>${esc(error)}</p><button class="button" data-action="retry-chart">Retry this read-only request</button></div>`;
  if(bars.length<2)return '<div class="empty-chart"><h3>Loading recorded OHLCV</h3><p>Only saved raw prices or an explicit market-data response will be plotted.</p></div>';
  const w=chartSize.width,h=chartSize.height,left=8,right=65,top=14,bottom=42;
  const low=Math.min(...bars.map(b=>b.l)),high=Math.max(...bars.map(b=>b.h)),pad=Math.max((high-low)*.1,.5);
  const min=low-pad,max=high+pad,x=i=>left+(i+.5)/bars.length*(w-left-right),y=v=>top+(max-v)/(max-min)*(h-top-bottom);
  const cw=Math.max(2,Math.min(9,(w-left-right)/bars.length*.6)),vmax=Math.max(...bars.map(b=>b.v),1);
  const overlays=(selectedEvidence()?.indicators||[]).filter(i=>/sma|ema/.test(i.name)).slice(0,3).map((series,n)=>{
    const points=new Map(series.points.map(p=>[p.t,p.value]));
    const path=bars.map((b,i)=>points.has(b.t)?`${i&&points.has(bars[i-1].t)?'L':'M'}${x(i)},${y(points.get(b.t))}`:'').join(' ');
    return `<path d="${path}" fill="none" stroke="${['#e6c17d','#86d6ab','#a5b3c0'][n]}" stroke-width="1.4"><title>${esc(series.name)} · saved dated values</title></path>`;
  }).join('');
  return `<svg class="equity-chart candle-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(selectedSymbol)} recorded daily OHLC candles from ${bars[0].t} to ${bars.at(-1).t}">
    ${[0,.5,1].map(f=>{const v=min+(max-min)*f;return `<line class="grid" x1="${left}" y1="${y(v)}" x2="${w-right}" y2="${y(v)}"/><text x="${w-right+7}" y="${y(v)+4}">${v.toFixed(2)}</text>`;}).join('')}
    ${bars.map((b,i)=>`<g class="${b.c>=b.o?'candle-up':'candle-down'}"><title>${b.t} · Open ${b.o} High ${b.h} Low ${b.l} Close ${b.c} Volume ${b.v}</title><line x1="${x(i)}" y1="${y(b.h)}" x2="${x(i)}" y2="${y(b.l)}"/><rect x="${x(i)-cw/2}" y="${Math.min(y(b.o),y(b.c))}" width="${cw}" height="${Math.max(1,Math.abs(y(b.o)-y(b.c)))}"/><rect class="volume-bar" x="${x(i)-cw/2}" y="${h-20-b.v/vmax*20}" width="${cw}" height="${b.v/vmax*20}"/></g>`).join('')}
    ${overlays}<text x="${left}" y="${h-3}">${bars[0].t}</text><text x="${w-right}" y="${h-3}" text-anchor="end">${bars.at(-1).t}</text></svg>`;
}
function savedDraftCard(d){
  const order=d.order||{},source=d.source||{};
  return `<article class="panel" id="saved-draft-${esc(order.client_order_id)}">
    <div class="panel-header"><div><h2>Saved Nautilus draft: ${esc(order.side)} ${esc(d.symbol)}</h2>
    <p>${esc(d.status)} / ${esc(String(d.approval||'Approval not recorded').replaceAll('_',' '))}</p></div>
    <span class="badge amber">${esc(order.status||d.native_status||'State not recorded')}</span></div>
    <div class="run-summary-body"><dl class="order-spec">
    <div><dt>Quantity</dt><dd>${esc(order.quantity)} whole share(s)</dd></div>
    <div><dt>Order type</dt><dd>${esc(order.type)}</dd></div>
    <div><dt>Time in force</dt><dd>${esc(order.time_in_force)}</dd></div>
    <div><dt>Price</dt><dd>${order.type==='MARKET'?'Market - no fixed price':money(order.price)}</dd></div>
    <div><dt>Broker submission</dt><dd>${d.broker_submitted===false?'Not submitted':d.broker_submitted===true?'Submission recorded':'Not recorded'}</dd></div>
    <div><dt>Risk approval</dt><dd>${d.risk_approved===false?'Not approved':d.risk_approved===true?'Recorded':'Not recorded'}</dd></div>
    <div><dt>Saved at</dt><dd>${esc(date(d.created_at))} ${esc(time(d.created_at))}</dd></div>
    <div><dt>Order ID</dt><dd>${esc(order.client_order_id)}</dd></div>
    </dl>
    <p>${d.demonstration_input?'Quantity was supplied as a demonstration input, not a sizing recommendation.':'Quantity was entered by the human.'}
    This is a saved initialized order. It does not establish ownership by the current node or a broker order.</p>
    <p>Source account: ${esc(source.account_id||'Not recorded')}</p>
    <p style="overflow-wrap:anywhere">Research result SHA256: <code>${esc(source.result_sha256||'Not recorded')}</code></p>
    <button class="button button-small" data-action="open-saved-result" data-run="${esc(source.run_id)}" data-symbol="${esc(d.symbol)}">Open saved source result</button>
    <span class="asset-name">Research run ${esc(source.run_id)}</span>
    <p class="asset-name">Historical initialized draft. Create and review an exact human proposal to obtain current order authority.</p>
    </div></article>`;
}
function workflowPanel(){
  const run=chosenRun(),result=currentResult(selectedSymbol,run);
  const related=(state.drafts||[]).filter(d=>d.source?.run_id===run?.id&&d.symbol===selectedSymbol);
  return `<section class="panel"><div class="panel-header"><div><h2>TradingAgents research → Nautilus draft → human review</h2>
    <p>Browse completed work below. Saved records remain available while the engine is stopped.</p></div></div>
    <div class="risk-strip"><div>1. TradingAgents <strong>${esc(result?.rating||result?.status||'Select a saved result')}</strong><span class="asset-name">${esc(run?.status||'No run selected')} · ${esc(selectedSymbol)}</span></div>
    <div>2. Nautilus <strong>${related.length?'Saved INITIALIZED draft':'No related draft saved'}</strong><span class="asset-name">Current engine: ${esc(stateErrorMessage?'Unconfirmed · last snapshot':state.nautilus?.status||'Unavailable')}</span></div>
    <div>3. Human review <strong>${related.length?'Awaiting approval':'No draft to approve'}</strong><span class="asset-name">Review and approve the exact revision, then explicitly Submit; resources are reserved during submission</span></div></div></section>
    ${related.map(savedDraftCard).join('')}`;
}
function renderOverview(){return UniverseReview.render(state);}
function researchCollection(run){const v=listViews.research,items=(run.symbols||[]).filter(symbol=>matchesStock(symbol,v.query)&&(v.filter==='all'||(currentResult(symbol,run)?.status||'queued')===v.filter)),p=listPage('research',items),counts=run.counts||{},remaining=(counts.queued||0)+(counts.running||0),estimate=remaining?DeskLists.estimate(runs(),run.config,remaining):null,done=['completed','failed','cancelled'].reduce((n,k)=>n+(counts[k]||0),0);return `${listToolbar('research',[['all','All run stocks'],['completed','Completed'],['running','Running'],['queued','Queued'],['failed','Failed'],['cancelled','Cancelled']])}<div class="queue-progress"><label for="run-progress">${done} / ${run.symbols.length} finished</label><progress id="run-progress" max="${run.symbols.length||1}" value="${done}"></progress><p>${counts.completed||0} completed · ${counts.failed||0} failed · ${counts.queued||0} queued</p>${remaining?`<p>${estimate?`About ${DeskLists.duration(estimate.seconds)} remaining · based on ${estimate.samples} completed stock timings with these models`:'Observed duration will appear after a stock finishes with these models.'}</p>`:''}<button class="link-button" data-action="select-unfinished" ${state.browse_only||activeRun()?'disabled':''}>Select failed / unfinished for a new run</button></div><div class="research-rows">${p.items.map(symbol=>{const result=currentResult(symbol,run);return `<button class="research-symbol" data-action="select-symbol" data-symbol="${esc(symbol)}" aria-pressed="${symbol===selectedSymbol}"><span><strong>${esc(symbol)}</strong><span class="asset-name">${esc(reviewLabel(result))}</span></span>${statusBadge(result?.status==='completed'?result.rating||'Completed':result?.status||'Queued')}</button>`;}).join('')}</div>${!items.length?emptyMatches():''}${listPager('research',p)}`;}
function boundedItems(name,items){const v=listViews[name];return listPage(name,items.filter(item=>matchesStock(item.symbol,v.query)&&(v.filter==='all'||item.status===v.filter)));}

function renderResearch(){const run=chosenRun();const result=currentResult(selectedSymbol,run);return `${pageHeader('Saved research','Select a run and symbol, then read the actual reports, debate and final recommendation.',`${activeRun()?'<button class="button button-danger" data-action="stop-run">Stop run</button>':''}${researchButton()}`)}${!runs().length?`<section class="panel"><div class="empty-state">${icon('research')}<h2>Your first research run</h2><p>Selected symbols move through market, sentiment, news and fundamentals analysts, a bull / bear debate, a trader, and a risk committee. Read the evidence here before creating proposals.</p>${researchButton()}<p class="muted">A research run does not place orders.</p></div></section>`:`<div class="run-toolbar"><label for="run-select" class="muted">Research run</label><select id="run-select" class="form-control">${runs().map(r=>`<option value="${esc(r.id)}" ${r.id===run?.id?'selected':''}>${esc(date(r.created_at))} ${esc(time(r.created_at))} · ${(r.symbols||[]).length} symbols · ${esc(r.status)} · ${esc(r.id.slice(0,8))}</option>`).join('')}</select>${statusBadge(run?.status)}<button class="button" data-action="human-proposal" ${!selectedSymbol?'disabled':''}>Create BUY / SELL proposal</button><a class="button" href="#orders">View saved Nautilus drafts</a></div><div class="research-layout"><aside class="symbol-list" aria-label="Run symbols">${researchCollection(run)}</aside><section class="panel research-detail-panel"><div class="result-top"><div class="heading-line"><h2>${esc(selectedSymbol)}</h2>${statusBadge(result?.rating||result?.status||'Awaiting result')}</div><p>${esc(companyName(selectedSymbol))} · ${esc(run.id)} · ${esc(run.history_source||'Saved app run')}</p></div><div id="research-detail-scroll" data-view="${esc(reportViewKey)}" class="research-detail-scroll" tabindex="0" role="region" aria-label="Selected stock research reports">${result?.error?`<div class="detail-note negative">${esc(result.error)}</div>`:''}${detailNotice(result,run)}${renderReports(result)}<div class="detail-note">Agent opinions are research evidence. Draft quantity is entered by the human; submission requires exact approval, admission and an explicit command action.</div></div></section></div>${renderEvents(run)}`}${renderDiagnostics()}`;}
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
  if(!result){const run=chosenRun(),pending=run?.symbols?.includes(selectedSymbol)&&['queued','running','cancelling'].includes(run.status);return pending?'<div class="empty-state"><h3>Waiting for this symbol</h3><p>This symbol is in the active run.</p></div>':'<div class="empty-state"><h3>No saved report for this stock in this run</h3><p>Select a run containing this symbol. No research job is running for this selection.</p></div>';}
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
function remainingOrderQuantity(qty,filled){
  if(!/^\d+(?:\.\d+)?$/.test(String(qty??''))||!/^\d+(?:\.\d+)?$/.test(String(filled??'')))return null;
  const parts=[String(qty).split('.'),String(filled).split('.')],scale=Math.max(...parts.map(p=>(p[1]||'').length));
  const [total,done]=parts.map(p=>BigInt(p[0]+(p[1]||'').padEnd(scale,'0'))),remaining=total-done;
  if(remaining<0n)return null;
  const digits=remaining.toString().padStart(scale+1,'0');
  return scale?digits.slice(0,-scale)+'.'+digits.slice(-scale):digits;
}
function brokerOrderTable(){
  const observation=state.broker_observation||{},connected=state.connection?.connected===true,error=sourceError('orders'),list=[];
  const collect=(rows,parent)=>{for(const order of rows){list.push({...order,parent_order_id:parent});if(Array.isArray(order.legs))collect(order.legs,order.id);}};
  collect(Array.isArray(state.orders)?state.orders:[],null);
  const page=boundedItems('orders',list);
  return '<section class="panel"><h2>Open orders at Alpaca</h2><p>'+esc(observation.source||'Alpaca order data unavailable')+' · Last update: '+esc(observation.observed_at||'Unavailable')+' · '+(connected&&observation.orders_complete===true?'Current open-order list':connected?'The current order list is incomplete':'Account disconnected; any orders shown are older saved data')+'. Older order records are listed separately in saved order history. Review and approve the exact order, then choose Submit to send it to Alpaca.</p>'+(error?'<p class="negative">'+esc((error.message||error)==='Start Nautilus to load engine state.'?'Connect your account to see current orders.':error.message||error)+'</p>':'')+listToolbar('orders')+(page.items.length?'<div class="table-scroll"><table class="data-table"><thead><tr><th>Symbol / broker identity</th><th>Side / type</th><th>Quantity</th><th>Cumulative filled</th><th>Remaining · calculated</th><th>Limit / average fill price</th><th>Status / reason</th><th>Related broker holding</th><th>Order updated</th></tr></thead><tbody>'+page.items.map(o=>{
    const holding=positions().find(p=>p.symbol===o.symbol),remaining=remainingOrderQuantity(o.qty,o.filled_qty);
    return '<tr><td><strong>'+esc(o.symbol)+'</strong><span class="asset-name">'+esc(o.id||'Broker ID unavailable')+'</span><span class="asset-name">Client '+esc(o.client_order_id||'Unavailable')+(o.parent_order_id?' · parent '+esc(o.parent_order_id):'')+'</span></td><td>'+esc(o.side)+' / '+esc(o.type||o.order_type)+'<span class="asset-name">'+esc(o.time_in_force||'TIF unavailable')+'</span></td><td>'+esc(o.qty??'Unavailable')+'</td><td>'+esc(o.filled_qty??'Unavailable')+'</td><td>'+esc(remaining??'Unavailable')+'</td><td>'+esc(o.limit_price??'No limit')+' / '+esc(o.filled_avg_price??'Unavailable')+'</td><td>'+esc(o.status||'Unavailable')+'<span class="asset-name">'+esc(o.reject_reason||o.rejection_reason||o.cancel_reason||o.status_reason||'No reason supplied')+'</span></td><td>'+esc(observation.positions_complete===true?(holding?holding.qty+' shares':'No position reported'):'Position observation incomplete')+'</td><td>'+esc(o.updated_at||o.submitted_at||o.created_at||'Unavailable')+'</td></tr>';
  }).join('')+'</tbody></table></div>':'<p>'+(!list.length&&connected&&observation.orders_complete===true?'No open broker orders reported.':list.length?'No matching broker orders.':'Current orders are unavailable.')+'</p>')+listPager('orders',page)+'</section>';
}
function renderOrders(){
  const drafts=state.drafts||[];
  return pageHeader('Orders','Review an order, approve its exact terms, then Submit. Approval alone never sends an order.')+commandActivity()+brokerOrderTable()+(drafts.length?'<details class="panel" id="saved-order-drafts"><summary>Older saved drafts · '+drafts.length+'</summary>'+drafts.map(savedDraftCard).join('')+'</details>':'');
}
function field(name,label,value,{type='text',help='',min='',max='',step='',unit='',placeholder=''}={}){return `<div class="field"><label for="config-${name}">${label}</label><div class="${unit?'input-unit':''}"><input class="form-control" id="config-${name}" name="${name}" type="${type}" value="${esc(value)}" ${min!==''?`min="${min}"`:''} ${max!==''?`max="${max}"`:''} ${step!==''?`step="${step}"`:''} placeholder="${esc(placeholder)}" ${name==='backend_url'?'':'required'}>${unit?`<span>${unit}</span>`:''}</div>${help?`<small>${help}</small>`:''}</div>`;}
let indexImportPreview=null,indexImportPage=0;
function indexImportMarkup(){
 if(!indexImportPreview)return '';
 const preview=indexImportPreview,part=DeskLists.page(preview.rows,indexImportPage,100);
 return '<section class="panel"><h3>Universe import preview</h3><p>'+preview.symbols.length+' accepted · '+preview.rejected+' rejected · '+preview.duplicates+' duplicate rows. The current universe is unchanged.</p><table><thead><tr><th>Row</th><th>Original</th><th>Symbol</th><th>Disposition / reason</th></tr></thead><tbody>'+part.items.map(row=>'<tr><td>'+row.row+'</td><td>'+esc(row.value)+'</td><td>'+esc(row.symbol)+'</td><td>'+esc(row.status+' · '+row.reason)+'</td></tr>').join('')+'</tbody></table><p>Rows '+part.first+'–'+part.last+' of '+part.total+'</p><button type="button" data-action="import-preview-prev" '+(!part.current?'disabled':'')+'>Previous rows</button><button type="button" data-action="import-preview-next" '+(part.current+1>=part.pages?'disabled':'')+'>Next rows</button><p>Only accepted rows will be applied to the editable draft. Rejected rows remain in this review; save settings separately to commit.</p><button type="button" data-action="import-merge" '+(!preview.symbols.length?'disabled':'')+'>Merge accepted rows with draft universe</button><button type="button" data-action="import-replace" '+(!preview.symbols.length?'disabled':'')+'>Replace draft universe with accepted rows</button><button type="button" data-action="import-dismiss">Discard import preview</button></section>';
}
function renderSettings(){const c=settingsDraft||state.config||{};return `${pageHeader('Workspace settings','Define the universe, capital limits, and models used for the next research run.')}<div class="settings-layout"><form id="settings-form" class="settings-form"><section class="settings-section"><h2>Stock universe</h2><p>A named collection of symbols for repeatable portfolio research.</p><div class="field-grid">${field('name','Universe name',c.name??'FANGMAN')}<div class="field"><label>Preset</label><button type="button" class="button" data-action="reset-universe">Use FANGMAN · 7 stocks</button><small>Meta, Apple, NVIDIA, Alphabet, Microsoft, Amazon, Netflix.</small></div><div class="field field-full"><label for="config-universe">Stock symbols</label><textarea class="form-control" id="config-universe" name="universe" spellcheck="false" required>${esc(Array.isArray(c.universe)?c.universe.join(', '):(c.universe||''))}</textarea><small>Paste up to 1,000 symbols, separated by commas or spaces, or import a CSV with a Symbol / Ticker column.</small><div class="index-tools"><button type="button" class="button button-small" data-action="import-index">Import CSV / text</button><input id="index-file" type="file" accept=".csv,.txt,text/csv,text/plain" hidden><button type="button" class="button button-small" data-action="export-index">Export saved index</button><span id="index-feedback" role="status">${(state.config?.universe||[]).length} saved stocks</span></div>${indexImportMarkup()}</div></div></section><section class="settings-section"><fieldset ${state.browse_only?'disabled':''}><h2>Research models</h2><p>Use your Codex ChatGPT sign-in, or configure another model provider. Research uses your selected account and its limits.</p><div class="field-grid">${field('llm_provider','Provider',c.llm_provider??'chatgpt',{placeholder:'chatgpt',help:'chatgpt uses your existing Codex sign-in. No API key needed.'})}${field('backend_url','Provider endpoint',c.backend_url||'',{type:'url',placeholder:'https://api.openai.com/v1',help:'Leave blank for ChatGPT. Optional for other providers.'})}${field('deep_think_llm','Deep reasoning model',c.deep_think_llm||'',{help:'Research debate, trader and portfolio decisions.'})}${field('quick_think_llm','Fast analysis model',c.quick_think_llm||'',{help:'Analyst reports and lightweight research.'})}</div></fieldset></section><div class="form-actions"><p>${settingsDirty?'Unsaved draft · changes apply after saving.':'Changes apply to future runs.'}</p><button type="button" class="button" data-action="discard-settings">Discard changes</button><button class="button button-primary" type="submit" ${busy.has('config')?'disabled':''}>${busy.has('config')?'Saving…':'Save settings'}</button></div><div id="config-error" class="form-error" role="alert"></div></form><aside class="settings-note"><h3>Connected services</h3><p>The configured account and IEX prices are observed through the native NautilusTrader integration. Account reconciliation and quote freshness are reported separately below.</p><div><span class="connection-endpoint">${esc(state.connection?.endpoint||'Configured endpoint unavailable')}</span><ul class="connection-list"><li><span class="status-dot ${!stateErrorMessage&&state.nautilus?.status==='connected'?'connected':'disconnected'}"></span><span>NautilusTrader / Alpaca</span><span class="muted" style="margin-left:auto;font-size:11px">${esc(stateErrorMessage?'Unconfirmed · last snapshot':state.nautilus?.status||'Unavailable')} · ${stateErrorMessage?'transport unconfirmed':state.health?.execution_enabled?'command transport available':'command transport unavailable'}</span></li><li>Market feed: ${esc(state.health?.feed||'Unknown')} · account import: ${esc(state.health?.reconciliation?.status||'unknown')}</li></ul></div><div><h3>Configured account and order authority</h3><p>The service verifies the configured account and current exact order authority before submission. Account order controls remain available in every workspace.</p><h3>Data freshness</h3><p>Refresh fetches broker state. Research activity updates automatically. Quotes and account values retain their snapshot timestamps.</p></div><details><summary>Connection diagnostics</summary><pre>${esc(text(state.connection))}</pre></details></aside></div>`;}
function renderDiagnostics(){const readiness=state.readiness?.ready===false?`<div class="readiness-note">${icon('settings')}<span>${esc(state.readiness.message||'Research models need configuration.')}</span><a href="#settings">Research settings</a></div>`:'';if(!state.errors||!(Array.isArray(state.errors)?state.errors.length:Object.keys(state.errors).length))return readiness;return `${readiness}<details class="diagnostics"><summary>Data source diagnostics</summary><pre>${esc(text(state.errors))}</pre></details>`;}
function previewOrder(id){
 const p=proposals().find(p=>p.id===id);if(!p)return;
 $('#order-preview').innerHTML='<h2 id="order-dialog-title">Historical proposal record</h2><p>This legacy record is not a currently approved command. Create a human proposal, review its exact saved revision, approve and admit it before using explicit command submission.</p><pre>'+esc(JSON.stringify(p,null,2))+'</pre><button class="button" data-action="inspect-proposal" data-proposal="'+esc(p.id)+'">Review associated research</button>';
 $('#order-dialog').showModal();
}
iconPaths.journal=iconPaths.research;
let benchmarkAsOf='',activityExportSymbols='';
let journalRecord=null,journalLoading=false,journalError='',journalConflict=false,journalSelected='',journalQuery='',journalStart='',journalEnd='',journalCollection='',reportingSettingsDraft=null;
const journalExports=new Set(),journalDrafts=new Map(),journalCollections=new Map(),journalCollectionErrors=new Map(),journalCollectionLoading=new Set();
async function loadJournal(discard=false){
 if(journalLoading)return;journalLoading=true;
 try{const record=await api('/api/reporting');journalRecord=record;journalError='';journalConflict=false;if(discard){journalDrafts.clear();reportingSettingsDraft=null;}}
 catch(error){journalError=error.message;}
 finally{journalLoading=false;if(activePage==='journal')render();}
}
async function loadJournalCollection(id){
 journalCollection=id;if(!id||journalCollections.has(id)){render();return;}
 if(journalCollectionLoading.has(id))return;
 journalCollectionErrors.delete(id);journalCollectionLoading.add(id);render();
 try{const data=await api('/api/reporting/collections/'+encodeURIComponent(id));if(data.id!==id)throw new Error('History collection identity differs');journalCollections.set(id,data);}
 catch(error){journalCollectionErrors.set(id,error.message);}
 finally{journalCollectionLoading.delete(id);if(activePage==='journal'&&journalCollection===id)render();}
}
async function journalAction(request){
 if(journalLoading||journalConflict)return;journalLoading=true;journalError='';render();
 try{
  const result=await api('/api/reporting',{...request,expected_revision:journalRecord.revision},{timeoutMs:request.action==='collect'?600000:120000});
  if(request.action==='export')download(JSON.stringify(result.export,null,2),'tradingagents-selected-decisions.json','application/json');
  else if(request.action==='export_csv')download(result.csv,result.filename,'text/csv;charset=utf-8');
  else{journalRecord=result;if(request.action==='refresh_methods'){journalCollections.delete(request.collection_id);await loadJournalCollection(request.collection_id);}if(request.action==='settings')reportingSettingsDraft=null;if(request.action==='note')journalDrafts.delete(request.id);if(request.action==='collect'){const item=result.data.collections[0];await loadJournalCollection(item.id);}}
 }catch(error){journalError=error.message;journalConflict=error.status===409;}
 finally{journalLoading=false;render();}
}
function journalNote(item){
 if(!journalDrafts.has(item.id)){const saved=journalRecord.data.entries[item.id]||{};journalDrafts.set(item.id,{assumptions:saved.assumptions||'',review_date:saved.review_date||'',outcome_notes:saved.outcome_notes||''});}
 const draft=journalDrafts.get(item.id),saved=journalRecord.data.entries[item.id];
 return '<section class="panel">'+decisionOutcomeMarkup(item)+'<h2>'+esc(item.symbol||item.kind)+' · '+esc(item.status||'Status not recorded')+'</h2><p>'+esc(item.kind)+' · source revision '+esc(item.revision??'Not recorded')+' · saved '+esc(item.saved_at||'Not recorded')+'</p><p>'+esc(item.rationale||'No human rationale recorded in this source')+'</p><p>Policy revision '+esc(item.policy_revision??'Not recorded')+' · broker order '+esc(item.broker_order_id||'None recorded')+' · fills '+esc(item.fill_ids?.join(', ')||'None recorded')+'</p><p>Approval record: '+esc(item.approval_recorded==null?'None recorded':JSON.stringify(item.approval_recorded))+'. This saved decision does not submit an order.</p><details><summary>Exact decision, source research and revision history</summary><pre>'+esc(JSON.stringify(item,null,2))+'</pre></details><label for="decision-assumptions">Investor assumptions<textarea id="decision-assumptions" rows="4" maxlength="20000">'+esc(draft.assumptions)+'</textarea></label><label for="decision-review-date">Investor review date<input id="decision-review-date" type="date" value="'+esc(draft.review_date)+'"></label><label for="decision-outcome">Later outcome notes<textarea id="decision-outcome" rows="4" maxlength="20000">'+esc(draft.outcome_notes)+'</textarea></label><button class="button" id="save-decision-note" '+(journalLoading?'disabled':'')+'>Save journal note</button><p>'+esc(saved?'Note revision '+saved.revision+' · saved '+saved.saved_at:'No saved follow-up note')+'</p><details><summary>Follow-up note history</summary><pre>'+esc(JSON.stringify(saved?.history||[],null,2))+'</pre></details></section>';
}
function performanceMetric(label,metric,key){
 const value=metric?.calculable?metric[key]:'Unavailable';
 return '<p><strong>'+esc(label)+'</strong> · '+esc(metric?.available?'Calculated from covered inputs':metric?.calculable?'Unsupported source method':'Not calculable')+' · '+esc(value??'Unavailable')+' · method '+esc(metric?.method||'Not recorded')+'</p><p>'+esc((metric?.readiness_reasons||[metric?.reason].filter(Boolean)).join('; '))+'</p>';
}
function performanceAcceptanceMarkup(data){
 const review=data.technical_method_assessment;
 return '<p><strong>'+esc(review?.accepted?'Supported performance method':'Unsupported or missing performance method')+'</strong></p><p>'+esc((review?.reasons||['No current method assessment recorded']).join('; '))+'</p><p>Assessment '+esc(review?.version||'Missing')+' · input method '+esc(review?.binding?.methods?.inputs||'Missing')+' · binding SHA-256 '+esc(review?.binding_sha256||'Missing')+'</p><details id="performance-technical-method"><summary>Named methods, daily-close convention and source semantics</summary><pre>'+esc(JSON.stringify(review||{accepted:false,reason:'Legacy records have no named method assessment'},null,2))+'</pre></details>';
}
function accountHistoryView(){
 const data=journalCollections.get(journalCollection),error=journalCollectionErrors.get(journalCollection);
 if(error)return '<p class="negative">'+esc(error)+'</p><button class="button" id="retry-history-source">Retry saved source</button>';
 if(!data)return journalCollection?'<p role="status">Loading the selected saved account-history collection… No new broker history is fetched.</p>':'<p>No saved account-history collection selected. Choose an interval to open its saved performance and activities. Loading saved records never fetches new broker history.</p>';
 const points=data.points||[];
 let chart='<p>Broker equity series unavailable.</p>';
 if(points.length>1){const values=points.map(p=>Number(p.equity)),low=Math.min(...values),high=Math.max(...values),span=high-low||1;
 chart='<svg viewBox="0 0 700 180" role="img" aria-label="Broker-reported equity over the saved interval" class="history-equity"><path fill="none" stroke="currentColor" stroke-width="2" d="'+values.map((v,i)=>(i?'L':'M')+(10+i/(values.length-1)*680)+','+(10+(high-v)/span*150)).join(' ')+'"/></svg>';}
 const allocation=data.allocation_observation||{},positions=allocation.positions||[];
 return '<section class="panel"><h3>Broker-reported equity and P&amp;L</h3><p>Account '+esc(data.account_id)+' · '+esc(data.currency||'Currency unknown')+' · '+esc(data.requested_start)+' to '+esc(data.requested_end)+' · captured '+esc(data.collected_at)+'</p><p>'+esc(data.source)+' · 1D · cashflow_types=ALL · '+esc(data.broker_rounding)+'</p><p>'+esc(data.raw_broker_percent_method)+'</p>'+chart+'<div class="report-table-scroll"><table><thead><tr><th>Provider timestamp / window label</th><th>Equity / USD</th><th>Broker P&amp;L / USD</th><th>Broker P&amp;L fraction</th></tr></thead><tbody>'+points.map(p=>'<tr><td>'+esc(new Date(p.timestamp*1000).toISOString())+'</td><td>'+esc(p.equity)+'</td><td>'+esc(p.broker_profit_loss)+'</td><td>'+esc(p.broker_profit_loss_pct)+'</td></tr>').join('')+'</tbody></table></div><h3>Adjusted performance and coverage</h3>'+performanceAcceptanceMarkup(data)+performanceMetric('Linked time-weighted return',data.time_weighted,'return')+'<details><summary>Benchmark comparison and method inputs</summary><pre>'+esc(JSON.stringify({comparison:data.benchmark_comparison,time_weighted:data.time_weighted,methodology:data.methodology_inputs},null,2))+'</pre></details><button class="button" id="refresh-performance-methods">Save method report from existing records</button><label for="benchmark-asof">Benchmark symbol mapping as-of date<input id="benchmark-asof" type="date" value="'+esc(benchmarkAsOf)+'"></label><button class="button" id="request-benchmark-history">Queue selected benchmark history for this interval</button><p>Activity pagination '+(data.pagination_complete?'completed for its creation-time query':'incomplete')+' · covered interval '+(data.interval_complete?'complete':'not established')+' · calculation coverage '+(data.calculation_coverage_complete?'matched under the declared method':'incomplete')+'</p>'+performanceMetric('Modified Dietz estimate',data.dietz,'estimate')+performanceMetric('Drawdown',data.drawdown,'value')+performanceMetric('Benchmark excess price-return comparison',data.benchmark_comparison,'excess_return')+'<ul>'+data.issues.map(issue=>'<li>'+esc(issue)+'</li>').join('')+'</ul><details><summary>Calculation inputs and broker cash-flow series</summary><pre>'+esc(JSON.stringify({dietz:data.dietz,base_value:data.broker_base_value,base_value_asof:data.broker_base_value_asof,cashflow:data.broker_cashflow_series},null,2))+'</pre></details><h3>Activities by source identity</h3><p>Deposits/withdrawals are external capital. Dividends remain investment income. Fees and unknown activity types are explicit; no zero-fee assumption is applied.</p><div class="report-table-scroll"><table><thead><tr><th>ID / type</th><th>Classification</th><th>Recorded amount</th><th>Time / date</th><th>Limitation</th></tr></thead><tbody>'+data.activities.map(a=>'<tr><td>'+esc(a.id)+'<br>'+esc(a.activity_type)+'</td><td>'+esc(a.category)+'</td><td>'+esc(a.amount??'Not recorded')+'</td><td>'+esc(a.time||a.date||'Not recorded')+'</td><td>'+esc(a.issues.join('; '))+'</td></tr>').join('')+'</tbody></table></div><h3>Allocation observation captured beside this report</h3><p>This is the existing Nautilus/broker observation at '+esc(allocation.account_at||'an unavailable time')+'. It does not reconstruct holdings for past dates. Reconciliation: '+esc(allocation.reconciliation?.status||'unknown')+'</p><div class="report-table-scroll"><table><thead><tr><th>Symbol</th><th>Observed quantity</th><th>Source market value / USD</th><th>Source unrealized P&amp;L / USD</th><th>Import</th></tr></thead><tbody>'+positions.map(p=>'<tr><td>'+esc(p.symbol)+'</td><td>'+esc(p.qty??'Unavailable')+'</td><td>'+esc(p.market_value??'Unavailable')+'</td><td>'+esc(p.unrealized_pl??'Unavailable')+'</td><td>'+esc(p.reconciliation_status||'unknown')+'</td></tr>').join('')+'</tbody></table></div><details><summary>Original source receipts</summary>'+data.receipts.map((r,i)=>'<p><a href="/api/reporting/collections/'+esc(data.id)+'/receipts/'+i+'" target="_blank" rel="noopener">Open receipt '+(i+1)+'</a> · '+esc(r.path)+' · captured '+esc(r.received_at)+' · source date '+esc(r.source_date||'Unavailable')+'<br>SHA-256 '+esc(r.artifact.sha256)+'</p>').join('')+'</details></section>';
}
function renderJournal(){
 if(!journalRecord){if(!journalLoading&&!journalError)queueMicrotask(()=>loadJournal());return pageHeader('Decision journal','Saved decisions and sourced account reporting.')+'<p>'+esc(journalError||'Loading saved local records…')+'</p><button class="button" id="reload-journal">Reload journal</button>';}
 const items=journalRecord.decisions.filter(d=>!journalQuery||JSON.stringify([d.symbol,d.status,d.kind]).toLowerCase().includes(journalQuery.toLowerCase()));
 const item=journalRecord.decisions.find(d=>d.id===journalSelected),settings=reportingSettingsDraft||{benchmark:journalRecord.data.benchmark?.symbol||'',currency:journalRecord.data.benchmark?.currency||'',treatment:journalRecord.data.benchmark?.treatment||'',horizon:journalRecord.data.horizon_days??'',reason:''};
 return pageHeader('Decision journal','Saved proposals, baskets, research identities and investor follow-up. No executions or outcomes are inferred.')+'<section class="panel journal-workspace"><p role="status">'+esc(journalError||(journalLoading?'Working…':'Saved reporting revision '+journalRecord.revision))+'</p><button class="button" id="reload-journal">Reload saved journal (discard unsaved notes/settings)</button><label for="decision-search">Find decisions<input id="decision-search" value="'+esc(journalQuery)+'" type="search"></label><button class="button" id="export-decisions">Export selected records ('+journalExports.size+')</button><div class="report-table-scroll"><table><thead><tr><th>Select</th><th>Decision</th><th>Saved status</th><th>Revision / date</th></tr></thead><tbody>'+items.map(d=>'<tr><td><input type="checkbox" data-export-decision="'+esc(d.id)+'" '+(journalExports.has(d.id)?'checked':'')+' aria-label="Export '+esc(d.symbol)+'"></td><td><button class="link-button" data-journal-decision="'+esc(d.id)+'">'+esc(d.symbol||d.kind)+'</button><br>'+esc(d.kind)+'</td><td>'+esc(d.status||'Not recorded')+'</td><td>'+esc(d.revision??'Not recorded')+'<br>'+esc(d.saved_at||'Not recorded')+'</td></tr>').join('')+'</tbody></table></div>'+(!items.length?'<p>No matching saved decisions. No research or trades are created to populate this journal.</p>':'')+'</section>'+(item?journalNote(item):'')+'<section class="panel journal-workspace"><h2>Account-history reporting</h2><div class="row"><button class="button" data-export-report="holdings">Export full-account holdings CSV</button><button class="button" data-export-report="activity">Export selected interval activity CSV</button><label>Optional activity export symbols · blank = full account<input id="activity-export-symbols" value="'+esc(activityExportSymbols)+'" placeholder="AAPL, MSFT"></label><button class="button" data-export-report="performance">Export full-account selected-period performance CSV</button></div><label for="report-start">Start date<input id="report-start" type="date" value="'+esc(journalStart)+'"></label><label for="report-end">End date<input id="report-end" type="date" value="'+esc(journalEnd)+'"></label><button class="button" id="collect-account-history" '+(journalLoading?'disabled':'')+'>Collect read-only broker history for this interval</button><p>Explicit retrieval only · up to 366 days and 2,000 activities per collection. Pagination budgets and missing coverage remain visible. This does not place orders or run agents.</p><label for="history-collection">Saved history collection<select id="history-collection"><option value="">Choose a saved interval</option>'+journalRecord.data.collections.map(c=>'<option value="'+esc(c.id)+'" '+(journalCollection===c.id?'selected':'')+'>'+esc(c.requested_start+' to '+c.requested_end+' · '+c.collected_at)+' · '+'saved interval · inspect current method status'+'</option>').join('')+'</select></label><button class="button" id="open-history-collection" '+(!journalCollection||journalCollectionLoading.has(journalCollection)?'disabled':'')+'>Open selected saved interval</button>'+accountHistoryView()+'</section><section class="panel journal-workspace"><h2>Your reporting choices</h2><p>A benchmark is the symbol you want to compare with your account over the same dates. Leave it blank to keep viewing account observations without a comparison. These choices can wait; saving does not fetch data, place orders or schedule work.</p><label>Comparison symbol (optional)<input id="report-benchmark" value="'+esc(settings.benchmark)+'"></label><label>Comparison currency (USD required for comparison)<input id="report-currency" value="'+esc(settings.currency)+'" placeholder="Unset"></label><label>What the comparison includes<select id="report-treatment"><option value="">Decide later</option><option value="price" '+(settings.treatment==='price'?'selected':'')+'>Price change only (dividends excluded)</option><option value="total_return" '+(settings.treatment==='total_return'?'selected':'')+'>Price change plus reinvested dividends (not supported)</option></select></label><p>Price comparison requires matching USD, split-adjusted daily history and excludes dividends and trading costs. Reinvested-dividend comparison is unavailable; selecting it keeps that comparison unavailable.</p><label>Planned review horizon (whole calendar days, optional)<input id="report-horizon" inputmode="numeric" value="'+esc(settings.horizon)+'"></label><p>The horizon records your reporting plan; it does not change the collection dates above or schedule a review.</p><label>Optional note about these reporting choices<textarea id="report-settings-reason" rows="2">'+esc(settings.reason)+'</textarea></label><button class="button" id="save-reporting-settings">Save reporting choices</button></section>';
}
document.addEventListener('input',event=>{
 if(event.target.id==='benchmark-asof')benchmarkAsOf=event.target.value;if(event.target.id==='activity-export-symbols')activityExportSymbols=event.target.value;
 const id=event.target.id,notes={'decision-assumptions':'assumptions','decision-review-date':'review_date','decision-outcome':'outcome_notes'};
 if(notes[id]&&journalDrafts.has(journalSelected))journalDrafts.get(journalSelected)[notes[id]]=event.target.value;
 if(id==='decision-search'){journalQuery=event.target.value;render();}
 if(id==='report-start')journalStart=event.target.value;if(id==='report-end')journalEnd=event.target.value;
 const fields={'report-benchmark':'benchmark','report-currency':'currency','report-treatment':'treatment','report-horizon':'horizon','report-settings-reason':'reason'};
 if(fields[id]){if(!reportingSettingsDraft)reportingSettingsDraft={benchmark:journalRecord.data.benchmark?.symbol||'',currency:journalRecord.data.benchmark?.currency||'',treatment:journalRecord.data.benchmark?.treatment||'',horizon:journalRecord.data.horizon_days??'',reason:''};reportingSettingsDraft[fields[id]]=event.target.value;}
});
document.addEventListener('change',event=>{
 if(event.target.dataset.exportDecision){const id=event.target.dataset.exportDecision;event.target.checked?journalExports.add(id):journalExports.delete(id);render();}
 if(event.target.id==='history-collection')loadJournalCollection(event.target.value);
});
document.addEventListener('click',event=>{
 const csv=event.target.closest('[data-export-report]');if(csv){journalAction({action:'export_csv',kind:csv.dataset.exportReport,collection_id:journalCollection,...(csv.dataset.exportReport==='activity'&&activityExportSymbols.trim()?{symbols:activityExportSymbols.toUpperCase().split(/[\s,]+/).filter(Boolean)}:{})});return;}
 if(event.target.id==='refresh-performance-methods')journalAction({action:'refresh_methods',collection_id:journalCollection});
 if(event.target.id==='request-benchmark-history')journalAction({action:'benchmark_history',collection_id:journalCollection,asof:benchmarkAsOf});
 const button=event.target.closest('[data-journal-decision]');if(button){journalSelected=button.dataset.journalDecision;render();return;}
 const id=event.target.id;
 if(id==='reload-journal')loadJournal(true);
 if(id==='save-decision-note')journalAction({action:'note',id:journalSelected,...journalDrafts.get(journalSelected)});
 if(id==='export-decisions')journalAction({action:'export',ids:[...journalExports]});
 if(id==='collect-account-history')journalAction({action:'collect',start:journalStart,end:journalEnd});
 if(id==='retry-history-source'||id==='open-history-collection')loadJournalCollection(document.getElementById('history-collection')?.value||journalCollection);
 if(id==='save-reporting-settings'){const d=reportingSettingsDraft||{benchmark:journalRecord.data.benchmark?.symbol||'',currency:journalRecord.data.benchmark?.currency||'',treatment:journalRecord.data.benchmark?.treatment||'',horizon:journalRecord.data.horizon_days??'',reason:''};journalAction({action:'settings',benchmark:d.benchmark?{symbol:d.benchmark,currency:d.currency,treatment:d.treatment}:null,horizon_days:d.horizon===''?null:Number(d.horizon),reason:d.reason});}
});
function commandActivity(){
 const data=state.commands?.data||{},commands=Object.values(data.commands||{}),labels={admitted_not_dispatched:'Approved · resources reserved · not sent',not_sent:'Not sent',dispatch_intent:'Submission requested',submitting:'Submitting',outcome_unknown:'Order outcome unknown',accepted:'Accepted',partially_filled:'Partly filled',cancel_pending:'Cancellation pending',replace_pending:'Replacement pending',filled:'Filled',canceled:'Canceled',rejected:'Rejected',expired:'Expired'};
 return '<section class="panel command-activity" id="command-activity"><h2>Place an order</h2>'+orderReadinessMarkup()+commandControls()+(commands.length?'<details><summary>Saved order history · '+commands.length+'</summary>'+commands.map(c=>'<article><h3>'+esc(c.side+' '+c.terms.quantity+' '+c.symbol)+' · '+esc(labels[c.state]||c.state)+'</h3><p>Reserved cash / USD '+esc(c.cash_commitment)+' · remaining shares '+esc(c.remaining_quantity)+' · '+esc(c.cash_commitment_basis||'Saved reservation; actual costs may differ')+'</p><details><summary>Order identifiers, events and source records</summary><pre>'+esc(JSON.stringify(c,null,2))+'</pre></details></article>').join('')+'</details>':'')+'</section>';
}
document.addEventListener('click',async event=>{if(event.target.closest('[data-action="reconcile-commands"]')){try{await api('/api/commands/reconcile',{});await readState({force:true});}catch(error){setError(error.message);}}});
let recoveryPreview=null,recoveryConfirmation='',recoveryMessage='',recoveryBusy=false,recoveryFile=null,recoveryBackup=null;
function nativeCacheMarkup(){
 return '<h3>Native cache</h3><p>Official Nautilus uses an in-memory cache. SQLite application records, research, proposals and command history remain saved. No persisted native execution proof is claimed. Broker observations and native comparison gaps are shown separately. Fresh reconciliation, valid exact approval and the saved account order block govern order actions; restarting never replays commands.</p>';
}
function renderHealth(){
 const h=state.health||{},store=h.store||{};
 return '<section class="panel health-panel"><h2>Health and recovery</h2><p><strong>'+((h.new_orders_blocked??false)===false?'New orders unblocked':'New orders blocked')+' · '+(stateErrorMessage?'transport unconfirmed':h.execution_enabled?'command transport available':'command transport unavailable in this session')+'</strong></p><dl>'+[['Account mode',h.account_mode],['Local service',stateErrorMessage?'Unconfirmed · refresh failed':h.service],['Engine',stateErrorMessage?'Unconfirmed · last snapshot':h.engine],['Engine version',h.engine_version],['Provider / feed',(h.provider||'Unknown')+' / '+(h.feed||'Unknown')],['Account observation',h.account_observed_at],['Prices checked',h.prices_checked_at],['Engine heartbeat',h.runtime_heartbeat_at],['Account import',h.reconciliation?.status||'unknown'],['Local store',store.status||'unknown'],['Database schema',store.schema],['Journal revision',store.journal_revision]].map(([label,value])=>'<dt>'+esc(label)+'</dt><dd>'+esc(value??'Unknown')+'</dd>').join('')+'</dl><p>Use Start / Stop Nautilus in the persistent account controls to reconnect. Stale observations are not current balances.</p><ul>'+(h.reconciliation?.gaps||[]).map(g=>'<li>'+esc(g)+'</li>').join('')+'</ul><details><summary>Configured capabilities</summary><pre>'+esc(JSON.stringify(h.capabilities||{},null,2))+'</pre></details><button class="button" id="download-diagnostics">Download diagnostics</button>'+nativeCacheMarkup()+'<h3>Application backup</h3><p>Includes the application database and referenced immutable research evidence, plus configured saved history. Credentials, environment contents and unrelated files are excluded. Active research writers must finish before backup or restore.</p><button class="button" id="create-backup" '+(recoveryBusy?'disabled':'')+'>Create consistent backup</button>'+(recoveryBackup?'<a class="button" href="/api/backups/'+esc(recoveryBackup.id)+'" download>Download saved backup</a><p>SHA-256 '+esc(recoveryBackup.sha256)+'</p>':'')+'<h3>Restore local records</h3><p>Broker history is unchanged. Current records are retained before cutover. Restored approvals are invalidated, the engine stops, and fresh reconciliation and new exact approvals are required; your saved pause choice is preserved (unpaused if no choice was saved).</p><label for="restore-archive">Application backup ZIP · maximum 64 MiB<input id="restore-archive" type="file" accept=".zip,application/zip"></label><p>'+esc(recoveryFile?.name||'No archive selected')+'</p><button class="button" id="preview-restore" '+(!recoveryFile||recoveryBusy?'disabled':'')+'>Inspect restore archive</button>'+(recoveryPreview?'<div class="restore-preview"><h3>Restore preview</h3><p>Backup date '+esc(recoveryPreview.manifest.created_at)+' · format '+recoveryPreview.manifest.version+' · database '+recoveryPreview.manifest.database_version+'</p><p>Records: '+esc(recoveryPreview.manifest.records.join(', '))+' · '+Object.keys(recoveryPreview.manifest.files).length+' files · saved history '+esc(recoveryPreview.manifest.history_included?'included':'not included')+'</p><p>Archive SHA-256 '+esc(recoveryPreview.archive_sha256)+'</p><p>'+esc(recoveryPreview.warning)+'</p><label for="restore-confirmation">Type RESTORE LOCAL RECORDS<textarea id="restore-confirmation" rows="1">'+esc(recoveryConfirmation)+'</textarea></label><button class="button button-danger" id="confirm-restore" '+(recoveryBusy?'disabled':'')+'>Restore the reviewed local records</button></div>':'')+'<p role="status">'+esc(recoveryMessage)+'</p><details><summary>Launch and restart</summary><p>Open Start-TradingDesk.cmd in this project. It uses tradingdesk.launch.json, the existing Python environments and the migrated SQLite store. It verifies the product and configured application identity before reusing its port. Missing paths produce an actionable message. It never migrates, installs dependencies or changes PowerShell policy. Use browser controls for native start/stop and application-only SQLite backup/restore. The native cache runs in memory.</p></details></section>';
}
document.addEventListener('change',event=>{if(event.target.id==='restore-archive'){recoveryFile=event.target.files?.[0]||null;recoveryPreview=null;recoveryConfirmation='';recoveryMessage='';render({force:true});}});
document.addEventListener('input',event=>{if(event.target.id==='restore-confirmation')recoveryConfirmation=event.target.value;});
document.addEventListener('click',async event=>{
 const action=event.target.id;if(action==='download-diagnostics'){download(JSON.stringify(state.health||{},null,2),'tradingagents-diagnostics.json','application/json');return;}
 if(!['create-backup','preview-restore','confirm-restore'].includes(action)||recoveryBusy)return;
  recoveryBusy=true;recoveryMessage=action==='preview-restore'?'Inspecting archive; current records are unchanged…':action==='create-backup'?'Creating application backup…':'Restoring application records…';render({force:true});
 try{
  if(action==='create-backup'){recoveryBackup=await api('/api/recovery',{action:'backup'});recoveryMessage='Consistent application backup saved. Download it above.';}
  if(action==='preview-restore'){
   if(!recoveryFile||recoveryFile.size>64*1024*1024)throw new Error('Choose an application ZIP no larger than 64 MiB.');
   const bytes=new Uint8Array(await recoveryFile.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
   recoveryPreview=await api('/api/recovery',{action:'preview',archive:btoa(binary)});recoveryMessage='Archive staged for review; current records are unchanged.';
  }
  if(action==='confirm-restore'){
   const result=await api('/api/recovery',{action:'restore',token:recoveryPreview?.token,confirmation:recoveryConfirmation});recoveryMessage=result.message;recoveryPreview=null;recoveryConfirmation='';recoveryFile=null;
   UniverseReview.resetAfterRestore();journalRecord=null;journalDrafts.clear();journalCollections.clear();journalCollection='';reportingSettingsDraft=null;resultDetails.clear();chartEvidence.clear();selectedRunId='';await readState({force:true});
  }
 }catch(error){recoveryMessage=(action==='preview-restore'?'Archive inspection: ':action==='create-backup'?'Backup: ':'Restore: ')+error.message;}
 finally{recoveryBusy=false;render({force:true});}
});
function download(content,filename,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportPositions(){const fields=['symbol','qty','avg_entry_price','current_price','market_value','unrealized_pl','unrealized_plpc'];const csvCell=value=>`"${String(value??'').replaceAll('"','""').replace(/^[=+@-]/,"'")}"`;download([fields.join(','),...positions().map(p=>fields.map(f=>csvCell(p[f])).join(','))].join('\r\n'),'paper-positions.csv','text/csv;charset=utf-8');}

document.addEventListener('click',async event=>{const button=event.target.closest('[data-action]');if(!button||button.disabled)return;const action=button.dataset.action;try{if(action==='discard-settings'){settingsDirty=false;settingsDraft=null;render({force:true});return;}if(action==='clear-proposal-filters'){Object.assign(listViews.proposals,{query:'',filter:'all',page:0});render();$('#proposals-search')?.focus();return;}if(action==='dismiss-error'){setError('');return;}if(action==='retry'){await readState();return;}if(action==='retry-chart'){await ensureChart(true);return;}if(action==='retry-detail'){await ensureResultDetail(true);return;}if(action==='select-symbol'){if(event.target.closest('input'))return;selectStock(button.dataset.symbol);return;}if(action==='inspect'){selectedSymbol=button.dataset.symbol;selectedRunId=state.research?.[selectedSymbol]?.run_id||selectedRunId;activePage='research';location.hash='research';render({force:true});return;}if(action==='run'){reviewResearch();return;}if(action==='stop-run'){const run=activeRun();if(run)await act('stop','/api/runs/cancel',{run_id:run.id},'Stop requested. The current agent step may finish before the run stops.');return;}if(action==='human-proposal'){const chosen=selectedSymbol,run=chosenRun(),observed=currentResult(chosen,run),result=observed?._updating?resultDetails.get(run.id+':'+chosen):observed,report=reportReadingAnchor($('#research-detail-scroll'))?.report||[...openReportNames].find(k=>result?.reports?.[k])||'final_trade_decision',context=result?{...result,symbol:chosen,run_id:run.id,report_key:report}:null;activePage='overview';location.hash='overview';render({force:true});requestAnimationFrame(()=>UniverseReview.openProposal(chosen,button,context));return;}if(action==='toggle-pause'){await togglePause();return;}if(action==='inspect-proposal'){const p=proposals().find(p=>p.id===button.dataset.proposal);if(p){selectedSymbol=p.symbol;selectedRunId=p.run_id;$('#order-dialog').close();activePage='research';location.hash='research';render({force:true});}return;}if(action==='preview-order'){previewOrder(button.dataset.proposal);return;}if(action==='reset-universe'){$('#config-universe').value='META, AAPL, NVDA, GOOGL, MSFT, AMZN, NFLX';$('#config-name').value='FANGMAN';captureSettingsDraft();return;}if(action==='export-positions'){exportPositions();return;}if(action==='export-run'){const exported=await api(`/api/runs/${encodeURIComponent(chosenRun().id)}`);download(JSON.stringify(exported,null,2),`research-${chosenRun()?.id||'run'}.json`,'application/json');return;}if(action==='sort-symbol'||action==='sort-price'){listViews.watch.page=0;const field=action==='sort-symbol'?'symbol':'price';universeSort={field,direction:universeSort.field===field?-universeSort.direction:1};render();}}catch{/* The action already reports its error in the notice. */}});
document.addEventListener('change',event=>{if(event.target.id==='select-page'){for(const symbol of listPage('watch',filteredWatch()).items)event.target.checked?selectedSymbols.add(symbol):selectedSymbols.delete(symbol);render();}if(event.target.classList.contains('symbol-select')){event.target.checked?selectedSymbols.add(event.target.value):selectedSymbols.delete(event.target.value);if(event.target.checked)selectStock(event.target.value);else render();}if(event.target.id==='run-select'){selectedRunId=event.target.value;const run=chosenRun();if(!run?.symbols?.includes(selectedSymbol))selectedSymbol=run?.symbols?.[0]||selectedSymbol;syncReportView();render();readState();}if(event.target.id==='order-filter'){orderFilter=event.target.value;render();}});
document.addEventListener('click',event=>{const action=event.target.closest('[data-action]')?.dataset.action;if(action==='evidence-period'){chartPeriod=event.target.closest('[data-action]').dataset.period;selectedBarDate=null;render();}if(action==='chart-stock'||action==='chart-equity'){chartMode=action==='chart-stock'?'stock':'equity';render();}if(action==='chart-week'||action==='chart-month'){chartPeriod=action==='chart-week'?'week':'month';render();}if(action==='refresh-source')$('#refresh').click();});
document.addEventListener('input',event=>{if(event.target.closest('#settings-form'))captureSettingsDraft();});
document.addEventListener('toggle',event=>{if(event.target.isConnected!==false&&(event.target.matches?.('.report-section')||event.target.matches?.('.report-raw'))&&(event.target.dataset.view===undefined||event.target.dataset.view===reportViewKey)){const name=event.target.dataset.report;event.target.open?openReportNames.add(name):openReportNames.delete(name);}},true);
document.addEventListener('submit',async event=>{if(event.target.id!=='settings-form')return;event.preventDefault();if(busy.has('config'))return;const submittedDraft=settingsDraft;const form=event.target;const data=new FormData(form);const c={...state.config};for(const [key,value]of data)c[key]=value;for(const key of ['allocation_pct','max_position_pct','reserve_pct','max_order_notional'])c[key]=Number(c[key]);c.backend_url=String(c.backend_url||'').trim()||null;try{c.universe=DeskLists.parseSymbols(c.universe).symbols;}catch(e){$('#config-error').textContent=e.message;return;}if(!c.universe.length){$('#config-error').textContent='Enter at least one stock symbol.';return;}if(c.allocation_pct+c.reserve_pct>100){$('#config-error').textContent='Invested allocation plus cash reserve cannot exceed 100%.';return;}if(c.max_position_pct>c.allocation_pct){$('#config-error').textContent='The single-position limit cannot exceed total invested allocation.';return;}try{await act('config','/api/config',state.browse_only?{name:c.name,universe:c.universe}:c,'Workspace settings saved.');if(settingsDraft===submittedDraft){settingsDirty=false;settingsDraft=null;}selectedSymbols=new Set([...selectedSymbols].filter(s=>universe().includes(s)));render({force:true});}catch(e){if($('#config-error'))$('#config-error').textContent=e.message;}});
async function togglePause(){activePage='orders';location.hash='orders';render({force:true});document.getElementById('account-order-controls')?.focus();}
$('#pause-trading').addEventListener('click',togglePause);
$('#refresh').addEventListener('click',async()=>{try{if(state?.connection?.connected){await refreshQuotes({manual:true});await readState();}else await act('refresh','/api/refresh',{},'Broker snapshot refreshed.');}catch{}});
window.addEventListener('hashchange',()=>{const next=location.hash.slice(1);if(['overview','research','orders','settings','journal'].includes(next)){activePage=next;render({force:true});window.scrollTo(0,0);}});
document.addEventListener('keydown',event=>{if(event.altKey&&event.key.toLowerCase()==='r'&&!['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName)){event.preventDefault();$('#refresh').click();}});
readState();
setInterval(()=>{if(activePage==='overview')refreshQuotes();},60000);
document.addEventListener('click',event=>{if(event.target.closest('[data-action="refresh-quotes"]'))refreshQuotes({manual:true});});
setInterval(()=>{for(const [scope,until]of rateLimits)if(Date.now()>=until)rateLimits.delete(scope);if(!document.hidden)readState();},5000);

document.addEventListener('input',event=>{const name=event.target.dataset.listQuery;if(name&&listViews[name]){listViews[name].query=event.target.value;listViews[name].page=0;render();}});
document.addEventListener('change',async event=>{const name=event.target.dataset.listFilter||event.target.dataset.listSize;if(name&&listViews[name]){if(event.target.dataset.listFilter)listViews[name].filter=event.target.value;else listViews[name].size=Number(event.target.value);listViews[name].page=0;render();}if(event.target.id==='index-file'){const file=event.target.files?.[0];if(!file)return;try{if(file.size>1048576)throw new Error('Use a file smaller than 1 MB.');let deadline;let content;try{content=await Promise.race([file.text(),new Promise((_,reject)=>deadline=setTimeout(()=>reject(new Error('File reading exceeded 15 seconds. Try a smaller file.')),15000))]);}finally{clearTimeout(deadline);}indexImportPreview=DeskLists.parseSymbols(content,{file:true,preview:true});indexImportPage=0;captureSettingsDraft();render({force:true});}catch(e){$('#config-error').textContent=e.message;}event.target.value='';}});
document.addEventListener('click',async event=>{const button=event.target.closest('[data-action]');if(!button||button.disabled)return;const action=button.dataset.action;try{if(action==='list-page'){listViews[button.dataset.list].page+=Number(button.dataset.direction);render();}if(action==='select-matches'){for(const symbol of filteredWatch())selectedSymbols.add(symbol);render();}if(action==='clear-selection'){selectedSymbols.clear();render();}if(action==='linked-step'){const stocks=filteredWatch();selectStock(stocks[stocks.indexOf(selectedSymbol)+Number(button.dataset.direction)]||selectedSymbol);}if(action==='find-stock'){listViews.watch.query=selectedSymbol;listViews.watch.filter='all';listViews.watch.page=0;render();$('#watch-search')?.focus();}if(action==='select-unfinished'){selectedSymbols=new Set((chosenRun()?.symbols||[]).filter(symbol=>universe().includes(symbol)&&currentResult(symbol)?.status!=='completed'));activePage='overview';location.hash='overview';render();showToast(`${selectedSymbols.size} stocks selected. Review the selection before starting research.`);}if(action==='confirm-research'&&pendingResearch){button.disabled=true;try{await launchResearch(pendingResearch.symbols,pendingResearch.revision);$('#research-dialog').close();pendingResearch=null;}catch(e){$('#research-error').textContent=e.message;button.disabled=false;}}if(action==='import-index'){captureSettingsDraft();$('#index-file').click();}if(action==='export-index')download('Symbol\r\n'+universe().join('\r\n'),'stock-index.csv','text/csv;charset=utf-8');}catch(e){setError(e.message);}});

document.addEventListener('click',event=>{
 const action=event.target.closest('[data-action]')?.dataset.action;
 if(!action?.startsWith('import-')||!indexImportPreview)return;
 if(action==='import-preview-prev')indexImportPage--;
 else if(action==='import-preview-next')indexImportPage++;
 else if(action==='import-dismiss')indexImportPreview=null;
 else if(action==='import-merge'||action==='import-replace'){
  try{
   const current=action==='import-merge'?DeskLists.parseSymbols($('#config-universe').value).symbols:[];
   const symbols=[...new Set([...current,...indexImportPreview.symbols])];
   if(symbols.length>1000)throw new Error('The combined draft exceeds 1,000 symbols. Adjust the draft or import before applying.');
   $('#config-universe').value=symbols.join(', ');captureSettingsDraft();indexImportPreview=null;
  }catch(error){$('#config-error').textContent=error.message;return;}
 }else return;
 render({force:true});
});

document.addEventListener('change',event=>{if(event.target.id==='bar-date'){selectedBarDate=event.target.value;render();}});

// Live configured-universe review; browser shortlist is independent of research selection.
const UniverseReview=(()=>{


const $=id=>document.getElementById(id), esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=value=>value===null||value===undefined||value===''||!Number.isFinite(Number(value))?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(value));
const time=value=>value?new Date(value).toLocaleString('en-US',{timeZone:'America/Los_Angeles',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'}):'Unavailable';
const fullTime=value=>value?'<time datetime="'+esc(value)+'" title="'+esc(value)+'">'+esc(time(value))+'</time>':'Unavailable';
function stock(){return DATA.stocks.find(s=>s.symbol===symbol)||DATA.held_stocks?.find(s=>s.symbol===symbol)||{symbol,company:symbol,quote:{}};}
function asText(value){return typeof value==='string'?value:JSON.stringify(value,null,2);}
const supplementaryForms=new Map(),supplementaryCache=new Map(),supplementaryVersions=new Map(),supplementaryPending=new Set(),supplementaryErrors=new Map();
function supplementForm(s){if(!supplementaryForms.has(s))supplementaryForms.set(s,{provider:'',scopes:new Set(),start:'',end:'',earnings_horizon:''});return supplementaryForms.get(s);}
async function loadStockEvidence(s){
 if(supplementaryPending.has(s)||supplementaryVersions.get(s)===state.stock_evidence?.revision)return;
 supplementaryPending.add(s);
 try{const result=await api('/api/stock-evidence?symbol='+encodeURIComponent(s));if(result.symbol!==s)throw new Error('Stock-evidence response identity differs');supplementaryCache.set(s,result);supplementaryVersions.set(s,state.stock_evidence?.revision);supplementaryErrors.delete(s);}
 catch(error){supplementaryErrors.set(s,error.message);}
 finally{supplementaryPending.delete(s);if(activePage==='overview'&&symbol===s)render();}
}
function sourceLink(url,label='Original source'){const safe=reportLink(url||'');return safe?'<a href="'+esc(safe)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+'</a>':'Source link not recorded';}
function supplementaryEvidence(s){
 const form=supplementForm(s),data=supplementaryCache.get(s),providers={alpaca:['news','corporate_actions'],sec_edgar:['fundamentals','classification'],alpha_vantage:['fundamentals','classification','earnings']};
 const observations=Object.entries(data?.observations||{});
 return '<section class="supplementary-evidence"><h3>News, business facts and dated events</h3><p>Current source observations are separate from immutable research. No provider access or paid subscription is inferred from a quote entitlement.</p><details id="supplementary-request"><summary>Request supplementary data from an existing provider</summary><div class="proposal-fields"><label>Provider<select id="supplement-provider"><option value="">Choose a provider</option>'+Object.keys(providers).map(v=>'<option '+(form.provider===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><p>'+esc(state.stock_evidence?.configuration?.[form.provider]||'Select a provider to see its configuration requirements')+'</p>'+((providers[form.provider]||[]).map(scope=>'<label><input type="checkbox" data-supplement-scope="'+scope+'" '+(form.scopes.has(scope)?'checked':'')+'> '+scope+'</label>').join(''))+'<label>Interval start<input id="supplement-start" type="date" value="'+esc(form.start)+'"></label><label>Interval end / SEC filed-as-of boundary<input id="supplement-end" type="date" value="'+esc(form.end)+'"></label><label>Earnings calendar horizon<select id="supplement-horizon"><option value="">Choose if requesting earnings</option>'+['3month','6month','12month'].map(v=>'<option '+(form.earnings_horizon===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><button id="request-supplementary">Queue selected evidence for this stock</button></div><p>'+esc(supplementaryErrors.get(s)||'No research agents are invoked. Data-job progress appears with current-market history.')+'</p></details>'+(!observations.length?'<p>No supplementary evidence saved for this stock. News, events, valuation and sector/industry coverage remain unavailable.</p>':'')+observations.map(([scope,observation])=>'<details><summary>'+esc(scope)+' · '+esc(observation.provider)+' · '+esc(observation.latest_attempt.status)+'</summary><p>Retrieved '+fullTime(observation.captured_at)+' · pagination '+(observation.complete?'completed':'incomplete')+'</p>'+(observation.retained_older_data?'<p class="negative">Older usable observations retained after a failed/incomplete latest request. Their original dates remain shown.</p>':'')+'<ul>'+observation.latest_attempt.gaps.map(g=>'<li>'+esc(g)+'</li>').join('')+'</ul>'+observation.records.map(record=>'<article><h4>'+esc(record.title||record.name||record.kind)+'</h4>'+((record.value!==undefined)?'<p>Reported value '+esc(record.value??'Unavailable')+' · '+esc(record.units||'units not reported')+' · '+esc(record.currency||'currency not reported')+'</p>':'')+(record.summary?'<p>'+esc(record.summary)+'</p>':'')+'<p>Published '+esc(record.published_at||'not reported')+' · effective '+esc(record.effective_at||'not reported')+' · period '+esc(record.period_start||'not reported')+' to '+esc(record.period_end||'not reported')+'</p><p>'+esc(record.date_status||record.date_basis||record.provenance||'Provider reported')+'</p><p>'+esc(record.limitation||'')+'</p>'+sourceLink(record.source_url)+(record.comparison_requires_review?'<p class="negative">Corporate-action comparison requires review. Saved report inputs have not been rewritten.</p>':'')+'<details><summary>Exact source fields</summary><pre>'+esc(JSON.stringify(record,null,2))+'</pre></details></article>').join('')+'<details><summary>Source receipts and hashes</summary><pre>'+esc(JSON.stringify(observation.receipts,null,2))+'</pre></details></details>').join('')+'</section>';
}
function bindSupplementary(){
 $('supplement-provider')?.addEventListener('change',e=>{const form=supplementForm(symbol);form.provider=e.target.value;form.scopes.clear();render();});
 const fields={'supplement-start':'start','supplement-end':'end','supplement-horizon':'earnings_horizon'};
 for(const [id,key]of Object.entries(fields))$(id)?.addEventListener('input',e=>supplementForm(symbol)[key]=e.target.value);
 document.querySelectorAll('[data-supplement-scope]').forEach(input=>input.addEventListener('change',e=>{const form=supplementForm(symbol);e.target.checked?form.scopes.add(input.dataset.supplementScope):form.scopes.delete(input.dataset.supplementScope);}));
 $('request-supplementary')?.addEventListener('click',async()=>{const s=symbol,form=supplementForm(s);try{const result=await api('/api/market-history',{action:'evidence',symbols:[s],...form,scopes:[...form.scopes]});state.market_history=result;supplementaryErrors.delete(s);await readState();}catch(error){supplementaryErrors.set(s,error.message);render();}});
}
const marketModes=new Map(),marketForms=new Map(),currentHistory=new Map(),currentHistoryVersions=new Map(),marketErrors=new Map();
let marketController=null,marketLoading='';
function marketForm(s){if(!marketForms.has(s))marketForms.set(s,{start:'',end:'',asof:marketDate(),adjustment:'',key:''});return marketForms.get(s);}
async function loadCurrentHistory(s,key=''){
 const signature=s+':'+key,version=state.market_history?.revision;if(marketLoading===signature||currentHistoryVersions.get(signature)===version)return;
 marketController?.abort();marketController=new AbortController();const controller=marketController;marketLoading=signature;
 try{
  const result=await api('/api/market-history?symbol='+encodeURIComponent(s)+(key?'&key='+encodeURIComponent(key):''),undefined,{signal:controller.signal});
  if(result.symbol!==s||result.context!=='current'||result.run_id)throw new Error('Current-market response does not match its selected symbol/context.');
  if(key&&result.key!==key)throw new Error('Current-market cache identity differs from the selection.');
  if(controller.signal.aborted)return;
  currentHistory.set(s,result);currentHistoryVersions.set(signature,version);marketErrors.delete(s);
  const form=marketForm(s);if(!form.start&&result.start)Object.assign(form,{start:result.start,end:result.end,asof:result.asof,adjustment:result.adjustment,key:result.key});
 }catch(error){if(!controller.signal.aborted)marketErrors.set(s,error.message);}
 finally{if(marketLoading===signature)marketLoading='';if(activePage==='overview'&&symbol===s&&!controller.signal.aborted)render();}
}
async function requestCurrentHistory(symbols,action='start',id){
 const s=symbol,form=marketForm(s);
 try{const result=await api('/api/market-history',['start','baseline'].includes(action)?{action,symbols,start:form.start,end:form.end,asof:form.asof,adjustment:form.adjustment}:{action,id});state.market_history=result;marketErrors.delete(s);await readState();}
 catch(error){marketErrors.set(s,error.message);render();}
}
function marketEvidence(s){
 const mode=marketModes.get(s)||(DATA.research[s]?'saved':'current');marketModes.set(s,mode);
 const form=marketForm(s),cached=currentHistory.get(s),jobs=Object.values(state.market_history?.data.jobs||{}),entries=Object.values(state.market_history?.data.entries||{}).filter(v=>v.symbol===s);
 const controls='<label for="market-context">Chart evidence context<select id="market-context"><option value="saved" '+(mode==='saved'?'selected':'')+'>Immutable saved research inputs</option><option value="current" '+(mode==='current'?'selected':'')+'>Current-market context · IEX cache</option></select></label>';
 if(mode==='saved')return controls+savedChart(s);
 const provenance=cached?.required_coverage?.provenance,listing=provenance?.listing;
 const listingContext=listing?' · first regular-way session '+esc(listing.first_trading_session)+' · '+esc((provenance.pre_regular_way_dates||[]).length)+' retained pre-regular-way dates (mapped context; not original regular-way trades). '+sourceLink(listing.source_url,'Listing source'):'';
 return controls+'<section class="current-market"><h3>Current-market daily history</h3><p>Independent of agent research. Feed IEX only · USD · regular daily sessions in America/New_York. Default symbol as-of and required-baseline dates use the current New York calendar date; completed-session coverage is assessed separately. Cached data remains dated; a completed request does not establish independent evidence readiness.</p><div class="proposal-fields"><label>Start date<input id="market-history-start" type="date" value="'+esc(form.start)+'"></label><label>End date<input id="market-history-end" type="date" value="'+esc(form.end)+'"></label><label>Symbol mapping as-of date · America/New_York<input id="market-history-asof" type="date" value="'+esc(form.asof)+'"></label><label>Adjustment basis<select id="market-history-adjustment"><option value="">Choose</option>'+['raw','split','dividend','all'].map(v=>'<option '+(form.adjustment===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><button id="request-current-history">Request this stock’s chart range</button><button id="request-required-baseline">Request required 252-session baseline</button><button id="request-selected-history" '+(!selectedSymbols.size?'disabled':'')+'>Request selected list ('+selectedSymbols.size+') with these dates</button><label>Saved current-market cache<select id="market-cache-key"><option value="">Latest saved context</option>'+entries.map(v=>'<option value="'+esc(v.key)+'" '+(form.key===v.key?'selected':'')+'>'+esc(v.start+' to '+v.end+' · '+v.adjustment+' · '+v.captured_at)+'</option>').join('')+'</select></label></div><p role="status">'+esc(marketErrors.get(s)||(marketLoading.startsWith(s+':')?'Loading existing cache…':cached?.latest_attempt?.error||cached?.error||''))+'</p>'+(cached?.retained_older_data?'<p class="negative">The latest attempt failed or is incomplete. Older usable data is retained with its original capture time.</p>':'')+(cached?.key?'<p>Captured '+fullTime(cached.captured_at)+' · pages '+esc(cached.pages??'Unavailable')+' · pagination '+(cached.pagination_complete?'completed':'incomplete')+' · required baseline '+(cached.required_coverage?.sufficient?'sufficient as captured':'insufficient')+' · adjustment '+esc(cached.adjustment||'Unknown')+listingContext+'</p>'+savedChart(s,cached,'current:'+s+':'+cached.key):'<p>No saved current-market history cache for this stock. Choose dates and request it explicitly. Missing history does not start research.</p>')+'<h3>Data jobs</h3><p>'+esc(state.market_history?.local_request_budget||'Data scheduler unavailable')+'</p>'+jobs.map(j=>'<details><summary>'+esc(j.status)+' · '+Object.values(j.symbols).filter(v=>v.status==='completed').length+' / '+Object.keys(j.symbols).length+' stocks · '+esc(j.id.slice(0,8))+'</summary><pre>'+esc(JSON.stringify(j.symbols,null,2))+'</pre>'+(['queued','running','canceling'].includes(j.status)?'<button data-cancel-data-job="'+esc(j.id)+'">Stop future requests</button>':'')+(['interrupted','canceled','failed','completed_with_gaps'].includes(j.status)?'<button data-resume-data-job="'+esc(j.id)+'">Resume unfinished symbols</button>':'')+'</details>').join('')+'</section>';
}
function bindMarketEvidence(){
 $('market-context')?.addEventListener('change',e=>{marketModes.set(symbol,e.target.value);if(e.target.value==='current')loadCurrentHistory(symbol,marketForm(symbol).key);render();});
 const fields={'market-history-start':'start','market-history-end':'end','market-history-asof':'asof','market-history-adjustment':'adjustment'};
 for(const [id,key]of Object.entries(fields))$(id)?.addEventListener('input',e=>marketForm(symbol)[key]=e.target.value);
 $('market-cache-key')?.addEventListener('change',e=>{marketForm(symbol).key=e.target.value;currentHistoryVersions.delete(symbol+':'+e.target.value);loadCurrentHistory(symbol,e.target.value);});
 $('request-current-history')?.addEventListener('click',()=>requestCurrentHistory([symbol]));
 $('request-required-baseline')?.addEventListener('click',()=>requestCurrentHistory([symbol],'baseline'));
 $('request-selected-history')?.addEventListener('click',()=>requestCurrentHistory([...selectedSymbols]));
 document.querySelectorAll('[data-cancel-data-job]').forEach(b=>b.addEventListener('click',()=>requestCurrentHistory([],'cancel',b.dataset.cancelDataJob)));
 document.querySelectorAll('[data-resume-data-job]').forEach(b=>b.addEventListener('click',()=>requestCurrentHistory([],'resume',b.dataset.resumeDataJob)));
}
const evidenceViews=new Map();
function savedChart(selected,h=DATA.history?.[selected],key=cacheKey(selected)){
 if(pending.has(key))return '<p class="muted">Loading existing saved evidence…</p>';
 if(!h||h.context==='current'&&!h.key)return '<p class="muted">No saved historical evidence for this stock. No research job is running.</p>';
 const all=h.bars||[],v=evidenceViews.get(key)||{range:'all',date:all.at(-1)?.t};evidenceViews.set(key,v);
 const cutoff=all.length?new Date(all.at(-1).t):null;if(cutoff&&v.range!=='all')cutoff.setUTCDate(cutoff.getUTCDate()-Number(v.range));
 const bars=all.filter(b=>!cutoff||v.range==='all'||b.t>=cutoff.toISOString().slice(0,10));
 if(!bars.some(b=>b.t===v.date))v.date=bars.at(-1)?.t;
 const bar=bars.find(b=>b.t===v.date),prior=all[all.findIndex(b=>b.t===v.date)-1],raw=(b,k)=>esc(b?.raw?.[k]??b?.[k]??'Not recorded');
 const close=number(bar?.raw?.c??bar?.c),priorClose=number(prior?.raw?.c??prior?.c);
 const movement=close!==null&&priorClose!==null&&priorClose>0?(close/priorClose-1)*100:null;
 let chart='<p>No saved OHLCV sessions. Missing evidence is not fetched.</p>';
 if(bars.length){
  const low=Math.min(...bars.map(b=>b.l)),high=Math.max(...bars.map(b=>b.h)),span=high-low||1,step=580/bars.length,y=n=>12+(high-n)/span*156;
  chart='<svg viewBox="0 0 600 180" width="100%" height="180" role="img" aria-label="'+esc(selected+' saved daily OHLC chart')+'">'+bars.map((b,i)=>{const x=10+(i+.5)*step;return '<g data-session="'+esc(b.t)+'" tabindex="0" role="button" aria-label="'+esc(b.t+' close '+(b.raw?.c??b.c))+'"><title>'+esc(b.t+' Open '+(b.raw?.o??b.o)+' High '+(b.raw?.h??b.h)+' Low '+(b.raw?.l??b.l)+' Close '+(b.raw?.c??b.c)+' Volume '+(b.raw?.v??b.v))+'</title><rect x="'+(x-step/2)+'" y="0" width="'+step+'" height="180" fill="'+(v.date===b.t?'var(--line)':'transparent')+'"/><path d="M'+x+','+y(b.h)+'V'+y(b.l)+'M'+(x-2)+','+y(b.o)+'H'+x+'M'+x+','+y(b.c)+'H'+(x+2)+'" stroke="'+(b.c>=b.o?'var(--accent)':'var(--fg)')+'" fill="none"/></g>';}).join('')+'</svg>';
 }
 const source=h.source||{},provenance=src=>'<p>'+esc(src.vendor||'Source not recorded')+' · captured '+fullTime(src.captured_at)+'</p><p>'+esc(src.path||src.note||'No source artifact recorded')+'</p><p class="artifact-hash">SHA-256 '+esc(src.sha256||'Not recorded')+'</p>';
 return '<figure class="saved-evidence" data-evidence-key="'+esc(key)+'"><h3>'+esc(h.context==='current'?'Current-market context':'Saved research inputs')+'</h3><p>'+esc(h.context==='current'?'Current data cache '+h.key:'Run '+h.run_id+' · research date '+h.research_date)+' · '+esc(h.price_basis||'Adjustment basis unknown')+'</p><label>Range <select id="saved-range">'+[['7','1W'],['30','1M'],['90','3M'],['180','6M'],['all','All saved']].map(([value,label])=>'<option value="'+value+'" '+(v.range===value?'selected':'')+'>'+label+'</option>').join('')+'</select></label>'+chart+'<label>Recorded session <select id="saved-session">'+bars.map(b=>'<option '+(b.t===v.date?'selected':'')+'>'+esc(b.t)+'</option>').join('')+'</select></label><dl>'+[['Open','o'],['High','h'],['Low','l'],['Close','c'],['Volume','v']].map(([label,k])=>'<dt>'+label+'</dt><dd>'+raw(bar,k)+'</dd>').join('')+'<dt>Prior saved close</dt><dd>'+raw(prior,'c')+' · '+esc(prior?.t||'No prior session recorded')+'</dd><dt>Recorded close-to-close movement</dt><dd>'+(movement===null||!Number.isFinite(movement)?'Unavailable':percent(movement))+'</dd></dl><p>Movement basis: (selected recorded close / previous available recorded close − 1) × 100. Reference recorded bar '+esc(prior?.t||'Unavailable')+' · '+esc(h.price_basis||'Adjustment basis unknown')+'. This compares recorded bar closes, not the current last trade or bid/ask midpoint.</p><p>Latest Nautilus price above is separate. OHLC ticks show saved sessions at equal spacing; adjustment basis remains unknown unless recorded.</p><details><summary>OHLCV source artifact</summary>'+provenance(source)+'</details><h3>Recorded indicators · '+esc(v.date||'No selected date')+'</h3>'+((h.indicators||[]).map(i=>{const point=i.points.find(p=>p.t===v.date);return '<details><summary>'+esc(i.name)+' · '+esc(point?.raw??point?.value??'Not recorded for this date')+'</summary><p>Recorded window '+esc(i.window_start)+' through '+esc(i.window_end)+'</p>'+provenance(i.source||{})+'</details>';}).join('')||'<p>No recorded indicators. Missing values are not zero.</p>')+'<h3>Claims attributed to the saved market report</h3><p>Support, resistance, entry and stop statements remain dated agent claims. Read the original market report alongside these inputs.</p>'+((h.claims||[]).map(c=>'<blockquote>'+esc(c.text??c)+'</blockquote><details><summary>Claim attribution and unresolved numeric mapping</summary><pre>'+esc(typeof c==='string'?'Legacy claim attribution has no numeric source mapping':JSON.stringify(c,null,2))+'</pre></details>').join('')||'<p>No extracted claims. Open the saved source report.</p>')+(h.problems||[]).map(p=>'<p class="negative">'+esc(p)+'</p>').join('')+'</figure>';
}
function bindEvidence(){
 bindMarketEvidence();bindSupplementary();
 const replace=()=>{const panel=$('detail-content')?.querySelector('.evidence');if(!panel)return;const scroll=panel.scrollTop;panel.outerHTML=evidence();$('detail-content').querySelector('.evidence').scrollTop=scroll;bindEvidence();};
 const changeView=(target,field,value)=>{
  const view=evidenceViews.get(target.closest('[data-evidence-key]')?.dataset.evidenceKey);
  if(!view)return;view[field]=value;replace();
 };
 $('saved-range')?.addEventListener('change',e=>changeView(e.target,'range',e.target.value));
 $('saved-session')?.addEventListener('change',e=>changeView(e.target,'date',e.target.value));
 document.querySelectorAll('#detail-content [data-session]').forEach(el=>{
  const select=()=>changeView(el,'date',el.dataset.session);
  el.addEventListener('click',select);el.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select();}});
 });
}
function evidence(){const s=stock(),q=s.quote;return `<section class="panel evidence"><div class="row"><h2>${esc(s.symbol)} evidence</h2><span class="tag">${esc(quoteFreshness(q))}</span></div><p>${esc(s.company)}</p><div class="amount">${money(q.price)}</div><dl><dt>Price basis</dt><dd>${esc(q.basis?.replaceAll('_',' ')||'Unavailable')}</dd><dt>Provider</dt><dd>${esc(q.feed||'Unavailable')}</dd><dt>Session / observation age / price event</dt><dd>${esc(quoteStatus(q))}</dd><dt>Snapshot checked</dt><dd>${fullTime(q.checked_at)}</dd><dt>Cached bid / ask</dt><dd>${money(s.bid)} / ${money(s.ask)}</dd><dt>Quote event</dt><dd>${s.quote_event_ns?fullTime(new Date(Number(s.quote_event_ns)/1e6).toISOString()):'Unavailable'}</dd></dl>${q.error?`<p>${esc(q.error)}</p>`:''}${marketEvidence(s.symbol)}${supplementaryEvidence(s.symbol)}</section>`;}
function savedResearch(){const r=researchFor(symbol);if(!r)return `<section class="panel research"><h2>${esc(symbol)} saved research</h2><p>No saved report for this stock.</p><p class="muted">${DATA.stocks.filter(s=>!DATA.research[s.symbol]).length} stocks in this configured universe have no saved research. Use the existing research controls to request a new run when this session permits it.</p></section>`;const reports=r.reports||{},keys=Object.keys(reports);if(!keys.includes(reportKey))reportKey=keys.includes('final_trade_decision')?'final_trade_decision':keys[0];return `<section class="panel research"><div class="row"><h2>${esc(symbol)} saved research</h2><span class="tag">${esc(r.rating||'Unrated')}</span></div><p class="muted">Research date ${esc(r.trade_date)} · revision ${esc(r.revision)} · ${esc(r.status)}</p><p class="muted">Saved agent analysis; dated statements below are not a current market assessment or an approved order.</p><label>Saved report<select id="report-select">${keys.map(k=>`<option value="${esc(k)}" ${k===reportKey?'selected':''}>${esc(k.replaceAll('_',' '))}</option>`).join('')}</select></label><div class="report-text" tabindex="0" aria-label="Saved report text">${reports[reportKey]?reportMarkup(reports[reportKey]):'No saved text available.'}</div><details class="report-source"><summary>Saved report provenance</summary><p>Run ${esc(r.run_id)}</p><p>${esc(r.source)}</p><p>Copied from the existing saved result. Exact saved source text:</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere;font:inherit">${esc(reports[reportKey]?asText(reports[reportKey]):'No saved text available.')}</pre></details></section>`;}

let DATA, researchOrigin=null, symbol='', reportKey='final_trade_decision', view='all', search='', sortKey='symbol', descending=false, returnFocus=null;
const shortlist=new Set(), STORAGE_KEY='tradingagents-live-universe-shortlist-v1';
const WATCHLISTS_KEY='tradingagents-universe-watchlists-v1', watchlists=[{id:'shortlist',name:'Shortlist',symbols:shortlist}];
let activeListId='', targetListId='shortlist', minMove=0, watchlistName='';
const activeList=()=>watchlists.find(list=>list.id===activeListId);
const targetList=()=>watchlists.find(list=>list.id===targetListId)||watchlists[0];
function matchesScope(s){const value=change(s);return (!activeList()||activeList().symbols.has(s.symbol))&&(minMove===0||value!==null&&Math.abs(value)>=minMove);}
const COLUMN_OPTIONS = [
 {key:'price',label:'Latest price',sort:'price'},
 {key:'change',label:'Change %',sort:'change'},
 {key:'age',label:'Price age',sort:'age'},
 {key:'research',label:'Saved research',sort:'date'},
 {key:'bid',label:'Latest bid'}, {key:'ask',label:'Latest ask'},
 {key:'savedOpen',label:'Saved session open'}, {key:'savedHigh',label:'Saved session high'},
 {key:'savedLow',label:'Saved session low'}, {key:'savedClose',label:'Saved session close'},
 {key:'savedVolume',label:'Saved session volume'}
];
const COLUMNS_KEY='tradingagents-universe-columns-v1';
let columnOrder=COLUMN_OPTIONS.map(c=>c.key), visibleColumns=new Set(['price','change','age','research']);
let portfolioView='universe', columnsOpen=false, columnsWarning='', returnWindowScroll=0;
const columns=()=>columnOrder.filter(key=>visibleColumns.has(key)).map(key=>COLUMN_OPTIONS.find(c=>c.key===key));
function restoreColumns(){
}
function persistColumns(){
 persistPreferences();
}
function renderColumns(){
 $('column-picker').open=columnsOpen;
 $('column-options').innerHTML=columnOrder.map((key,index)=>{
  const column=COLUMN_OPTIONS.find(c=>c.key===key);
  return '<div class="column-option"><label><input id="column-'+key+'" type="checkbox" data-column="'+key+'" '+(visibleColumns.has(key)?'checked':'')+'> '+column.label+'</label><div><button type="button" data-column-move="'+key+'" data-step="-1" aria-label="Move '+column.label+' up" '+(!index?'disabled':'')+'>↑</button><button type="button" data-column-move="'+key+'" data-step="1" aria-label="Move '+column.label+' down" '+(index===columnOrder.length-1?'disabled':'')+'>↓</button></div></div>';
 }).join('');
 $('column-note').textContent=columnsWarning||'Symbol and company stay visible. Saved session values load only when you open a stock with existing research.';
}
function columnCell(column,s){
 const r=DATA.research[s.symbol], value=change(s);
 if(column.key==='price')return money(s.quote.price);
 if(column.key==='change')return value===null?'Unavailable':(value>0?'+':'')+value.toFixed(2)+'%';
 if(column.key==='age')return '<span title="'+esc(s.quote.timestamp||'No provider timestamp')+'">'+ageLabel(s)+'<br><small>'+esc(quoteFreshness(s.quote))+' · '+esc(s.quote.session||'session unknown')+'</small></span>';
 if(column.key==='research')return r?esc(r.rating||'Unrated')+'<br><small>'+esc(r.trade_date)+'</small>':'<span class="muted">No saved research</span>';
 if(column.key==='bid'||column.key==='ask'){
  const event=s.quote_event_ns?new Date(Number(s.quote_event_ns)/1e6).toISOString():null;
  return money(s[column.key])+(s[column.key]!=null?'<br><small title="'+esc(event)+'">'+esc(time(event))+'</small>':'');
 }
 const saved=DATA.history[s.symbol], bar=saved?.bars?.at(-1);
 if(!bar)return r&&!history.has(cacheKey(s.symbol))?'<small>Not loaded · open stock</small>':'Unavailable';
 const field={savedOpen:'o',savedHigh:'h',savedLow:'l',savedClose:'c',savedVolume:'v'}[column.key];
 return (column.key==='savedVolume'?new Intl.NumberFormat('en-US').format(bar[field]):money(bar[field]))+'<br><small>Saved '+esc(bar.t)+'</small>';
}
let holdingsQuery='',holdingsSort='symbol',holdingsFilter='all',holdingsDescending=false;
function exactParts(value){
 if(value===null||value===undefined||typeof value==='boolean')return null;
 const match=String(value).match(/^([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/);if(!match)return null;
 const scale=(match[3]||'').length-Number(match[4]||0);if(Math.abs(scale)>100)return null;
 return {value:BigInt((match[1]==='-'?'-':'')+match[2]+(match[3]||''))*(scale<0?10n**BigInt(-scale):1n),scale:Math.max(0,scale)};
}
function exactText(part){if(!part)return 'Unavailable';const sign=part.value<0n?'-':'',digits=(part.value<0n?-part.value:part.value).toString().padStart(part.scale+1,'0');return sign+(part.scale?digits.slice(0,-part.scale)+'.'+digits.slice(-part.scale):digits);}
function exactSum(values){const parts=values.map(exactParts);if(parts.some(part=>!part))return null;const scale=Math.max(0,...parts.map(part=>part.scale));return {value:parts.reduce((sum,part)=>sum+part.value*10n**BigInt(scale-part.scale),0n),scale};}
function exactCompare(a,b){const left=exactParts(a),right=exactParts(b);if(!left||!right)return left?-1:right?1:0;const scale=Math.max(left.scale,right.scale),difference=left.value*10n**BigInt(scale-left.scale)-right.value*10n**BigInt(scale-right.scale);return difference<0n?-1:difference>0n?1:0;}
function pendingHoldings(){
 const terminal=new Set(['filled','canceled','cancelled','expired','rejected','replaced','done_for_day','not_sent']);
 const orders=DATA.orders.filter(order=>!terminal.has(String(order.status).toLowerCase()));
 const brokerClients=new Set(orders.map(order=>order.client_order_id));
 const broker=orders.map(order=>{const left=exactSum([order.qty,exactParts(order.filled_qty)?'-'+String(order.filled_qty):null]);return {symbol:order.symbol,side:String(order.side).toUpperCase(),quantity:left&&left.value>=0n?exactText(left):null,price:order.limit_price??null,source:'Broker working order '+(order.id||'identity unavailable')};});
 const local=Object.values(state.commands?.data.commands||{}).filter(command=>!terminal.has(command.state)&&!brokerClients.has(command.client_order_id)).map(command=>({symbol:command.symbol,side:command.side,quantity:command.remaining_quantity??null,price:command.price_cap??null,source:'Durable command '+command.id+' · '+command.state}));
 return [...broker,...local];
}
function pendingMarkup(rows){
 if(!rows.length)return 'None observed';
 return rows.map(row=>esc(row.side+' '+(row.quantity??'quantity unknown')+' shares · '+(row.price==null?'principal unpriced':row.price+' USD price ceiling')+' · '+row.source)).join('<br>');
}
function holdingsTable(){
 const warning=DATA.reconciliation.status==='reconciled'?'':'<div class="panel"><h2>Native comparison '+esc(DATA.reconciliation.status||'pending')+'</h2><p>'+esc((DATA.reconciliation.gaps||[]).join('; ')||'Waiting for source observations and native reconciliation.')+'</p><p>The rows below preserve broker-reported holdings. Native comparison is separate from source availability. Unresolved reconciliation can block new orders without hiding broker observations.</p></div>';
 if(!DATA.holdings_available&&!DATA.holdings.length)return warning+'<div class="panel"><h2>Holdings unavailable</h2><p>'+esc(DATA.connection_message||'Connect Nautilus to read current account positions.')+'</p><p>Unavailable or incomplete imports are distinct from zero holdings.</p></div>';
 const pending=pendingHoldings(),numeric=['qty','market_value','unrealized_pl'].includes(holdingsSort);
 const rows=DATA.holdings.filter(p=>(p.symbol+' '+(p.reconciliation_status||'')).toLowerCase().includes(holdingsQuery.toLowerCase())&&(holdingsFilter==='all'||holdingsFilter==='outside'&&!DATA.stocks.some(s=>s.symbol===p.symbol)||holdingsFilter==='pending'&&pending.some(order=>order.symbol===p.symbol)||holdingsFilter==='gaps'&&Boolean(p.import_error)));
 rows.sort((a,b)=>{const missing=numeric&&(exactParts(a[holdingsSort])===null||exactParts(b[holdingsSort])===null);const compared=numeric?exactCompare(a[holdingsSort],b[holdingsSort]):a.symbol.localeCompare(b.symbol);return (missing?compared:compared*(holdingsDescending?-1:1))||a.symbol.localeCompare(b.symbol);});
 const totals=(positions,label)=>'<p>'+esc(label)+' · '+positions.length+' holdings · market value / USD '+esc(exactText(exactSum(positions.map(p=>p.market_value))))+' · unrealized P/L / USD '+esc(exactText(exactSum(positions.map(p=>p.unrealized_pl))))+'</p>';
 return warning+'<div class="filters"><label>Filter held symbols / import status<input id="holdings-query" type="search" value="'+esc(holdingsQuery)+'"></label><label>Holding scope<select id="holdings-filter">'+[['all','All observed holdings'],['outside','Outside configured universe'],['pending','With pending exposure'],['gaps','With import gaps']].map(([value,label])=>'<option value="'+value+'" '+(holdingsFilter===value?'selected':'')+'>'+label+'</option>').join('')+'</select></label><label>Holdings sort<select id="holdings-sort">'+[['symbol','Symbol'],['qty','Exact quantity'],['market_value','Broker market value'],['unrealized_pl','Broker unrealized P/L']].map(([value,label])=>'<option value="'+value+'" '+(holdingsSort===value?'selected':'')+'>'+label+'</option>').join('')+'</select></label><button id="holdings-direction">'+(holdingsDescending?'Descending':'Ascending')+'</button></div>'+totals(rows,'Filtered subset')+totals(DATA.holdings,'All observed account holdings')+'<p>Full account equity / USD '+esc(DATA.account.equity??'Unavailable')+' · cash / USD '+esc(DATA.account.cash??'Unavailable')+' · observed '+fullTime(DATA.account_observed_at)+'. Holdings totals exclude cash and do not substitute for account equity. A missing component makes the total unavailable.</p>'+(!DATA.holdings.length?'<p>No open holdings reported in this observation. Pending orders can still exist.</p>':!rows.length?'<p>No holdings match these filters. Full account totals remain above.</p>':'')+'<div class="table-scroll holdings-table"><table><thead><tr><th>Holding / import</th><th>Exact quantity</th><th>Broker average cost / USD</th><th>Observed price / USD</th><th>Broker market value / USD</th><th>Broker unrealized P/L / USD</th><th>Account weight (derived)</th><th>Pending exposure</th></tr></thead><tbody>'+rows.map(p=>{
 const q=[...DATA.stocks,...(DATA.held_stocks||[])].find(s=>s.symbol===p.symbol)?.quote,value=number(p.market_value),equity=number(DATA.account.equity),price=p.current_price??q?.price,weight=value!==null&&equity>0?value/equity*100:null;
 return '<tr><td><button class="stock-button" data-stock="'+esc(p.symbol)+'">'+esc(p.symbol)+'</button><br><small>'+esc(p.reconciliation_status||'Import pending')+(DATA.stocks.some(s=>s.symbol===p.symbol)?'':' · outside configured universe')+'</small>'+(p.import_error?'<br><small>'+esc(p.import_error)+'</small>':'')+'</td><td>'+esc(p.qty??'Unavailable')+'</td><td>'+esc(p.avg_entry_price??'Unavailable')+'</td><td>'+esc(price??'Unavailable')+'<br><small>'+(p.current_price!=null?'Broker mark observed ':'Price event ')+esc(time(p.current_price!=null?DATA.account_observed_at:q?.timestamp))+'</small></td><td>'+esc(p.market_value??'Unavailable')+'</td><td>'+esc(p.unrealized_pl??'Unavailable')+'</td><td>'+(weight===null?'Unavailable':weight.toFixed(2)+'%')+'</td><td>'+pendingMarkup(pending.filter(order=>order.symbol===p.symbol))+'</td></tr>';
 }).join('')+'</tbody></table></div><details id="holdings-pending"><summary>All account pending exposure · '+pending.length+' observations / local commands</summary><p>Orders are not holdings. Remaining shares are derived from exact reported quantities; market-order principal, missing quantities and fees remain unknown. No sale proceeds are treated as cash.</p>'+pending.map(order=>'<p>'+esc(order.symbol)+' · '+pendingMarkup([order])+'</p>').join('')+'</details><p class="muted">Source numeric text is preserved. Account weights use supplied position market value divided by supplied equity and are rounded for display. Unknown values remain unavailable.</p>';
}
function showPortfolio(){
 $('holdings-view').hidden=portfolioView!=='holdings';$('universe-view').hidden=portfolioView!=='universe';
 $('show-holdings').setAttribute('aria-pressed',String(portfolioView==='holdings'));
 $('show-universe').setAttribute('aria-pressed',String(portfolioView==='universe'));
 $('show-holdings').textContent='Holdings ('+(DATA.holdings_available?DATA.holdings.length:'unavailable')+')';
 $('show-universe').textContent='Stock universe ('+DATA.stocks.length+')';
 $('holdings-body').innerHTML=holdingsTable()+'<details><summary>Read-only import observations and precision</summary><p>'+esc(DATA.reconciliation.fill_window||'Fill observation window pending')+'</p><p>Broker cost basis and market value retain source authority; a matching native valuation is not established. Missing fees remain unavailable.</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+esc(JSON.stringify({observed_at:DATA.reconciliation.observed_at,gaps:DATA.reconciliation.gaps,positions:DATA.holdings,orders:DATA.orders,fills:DATA.fills},null,2))+'</pre></details>';
}
function reportMarkup(value){return esc(asText(value)).replace(/^#{1,6}\s+(.+)$/gm,'<h3>$1</h3>').replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/^[-*]\s+/gm,'• ');}
function matchesSearch(s){return !search||(s.symbol+' '+s.company).toLowerCase().includes(search);}
function change(s){const v=s.quote.change_pct;return typeof v==='number'&&Number.isFinite(v)?v:null;}
function matchesView(s,key){const r=DATA.research[s.symbol],review=reviewDisposition(s.symbol);return key==='all'||key==='owned'&&DATA.holdings.some(p=>p.symbol===s.symbol)||key==='review'&&r&&review?.disposition!=='reviewed'||key==='priority'&&review?.prioritize||key==='missing'&&s.quote.price==null||key==='stale'&&liveQuoteState(s.quote)==='stale'||key==='research'&&Boolean(r)||key==='unresearched'&&!r||key==='shortlist'&&shortlist.has(s.symbol)||key==='gainers'&&change(s)>0||key==='decliners'&&change(s)<0;}
function age(s){return s.quote.timestamp?Math.max(0,new Date(DATA.captured_at)-new Date(s.quote.timestamp)):null;}
function ageLabel(s){const ms=age(s);if(ms===null||!Number.isFinite(ms))return 'Unavailable';const m=Math.floor(ms/60000);return (m>=1440?Math.floor(m/1440)+'d ':m>=60?Math.floor(m/60)+'h ':'')+(m>=1440?Math.floor(m%1440/60)+'h':m%60+'m')+' old';}
function sortValue(s){const r=DATA.research[s.symbol];return sortKey==='price'?s.quote.price:sortKey==='change'?change(s):sortKey==='magnitude'?(change(s)===null?null:Math.abs(change(s))):sortKey==='age'?age(s):sortKey==='date'?r?.trade_date??null:sortKey==='rating'?r?.rating??null:s[sortKey];}
function filteredRows(){
 return (view==='owned'?ownedRows():DATA.stocks).filter(s=>matchesSearch(s)&&matchesScope(s)&&matchesView(s,view)).sort((a,b)=>{
  const av=sortValue(a),bv=sortValue(b);if(av==null&&bv==null)return a.symbol.localeCompare(b.symbol);if(av==null)return 1;if(bv==null)return -1;
  const cmp=typeof av==='number'?av-bv:String(av).localeCompare(String(bv));return (descending?-cmp:cmp)||a.symbol.localeCompare(b.symbol);
 });
}
function renderViews(){
 const labels={all:'All',owned:'Owned · includes outside universe',research:'Has saved research',unresearched:'No saved research',review:'Research needs human review',priority:'Future research priorities',missing:'Price missing',stale:'Price stale',gainers:'Gainers',decliners:'Decliners'};
 $('universe-views').innerHTML=Object.entries(labels).map(([key,label])=>'<button data-view="'+key+'" aria-pressed="'+(view===key)+'">'+label+' <span class="count">'+(key==='owned'?ownedRows():DATA.stocks).filter(s=>matchesSearch(s)&&matchesScope(s)&&matchesView(s,key)).length+'</span></button>').join('');
}
function renderSelection(rows){
 persistView();
 const visible=rows.filter(s=>selectedSymbols.has(s.symbol)).length;
 $('selection-count').textContent=selectedSymbols.size+' selected'+(selectedSymbols.size?' · '+visible+' in view':'');
 const list=targetList();if($('export-selected-holdings'))$('export-selected-holdings').disabled=!selectedSymbols.size;$('clear-selection').disabled=!selectedSymbols.size;$('add-shortlist').disabled=!Array.from(selectedSymbols).some(s=>!list.symbols.has(s));$('remove-shortlist').disabled=!Array.from(selectedSymbols).some(s=>list.symbols.has(s));$('select-filtered').disabled=!rows.length;
 $('add-shortlist').textContent='Add to '+list.name;$('remove-shortlist').textContent='Remove from '+list.name;$('create-watchlist').disabled=!selectedSymbols.size||!watchlistName.trim();
 $('select-all').checked=rows.length>0&&visible===rows.length;$('select-all').indeterminate=visible>0&&visible<rows.length;$('select-all').disabled=!rows.length;
}
function renderTable(resetScroll=false){
 const box=$('table-scroll'),scrollTop=resetScroll?0:box.scrollTop,scrollLeft=box.scrollLeft,rows=filteredRows(),shown=columns();
 $('universe-head').innerHTML='<th class="select-cell"><input type="checkbox" id="select-all" aria-label="Select all filtered stocks"></th><th class="fixed-stock" id="head-symbol"><button data-sort="symbol">Stock / company</button></th>'+shown.map(c=>'<th id="head-'+(c.sort||c.key)+'" class="'+(['age','research'].includes(c.key)?'':'num')+'">'+(c.sort?'<button data-sort="'+c.sort+'">'+c.label+'</button>':c.label)+'</th>').join('');
 renderViews();renderSelection(rows);
 $('watchlist-select').innerHTML='<option value="">All configured stocks</option>'+watchlists.map(list=>'<option value="'+esc(list.id)+'">'+esc(list.name)+' ('+DATA.stocks.filter(s=>list.symbols.has(s.symbol)).length+')</option>').join('');
 $('watchlist-select').value=activeListId;$('min-move').value=String(minMove);
 $('watchlist-target').innerHTML=watchlists.map(list=>'<option value="'+esc(list.id)+'">'+esc(list.name)+'</option>').join('');$('watchlist-target').value=targetList().id;
 $('result-count').textContent=rows.length+' matching stocks · '+DATA.stocks.length+' in universe · '+(activeList()?activeList().name:'All configured stocks')+(minMove?' · |change| ≥ '+minMove+'%':'');
 $('stock-rows').innerHTML=rows.length?rows.map(s=>{
  const active=detailOpen&&symbol===s.symbol;
  return '<tr'+(active?' class="row-active"':'')+' data-row="'+esc(s.symbol)+'"><td class="select-cell"><input type="checkbox" data-select="'+esc(s.symbol)+'" aria-label="Select '+esc(s.symbol)+'" '+(selectedSymbols.has(s.symbol)?'checked':'')+'></td><td class="fixed-stock"><button class="stock-button" data-stock="'+esc(s.symbol)+'" aria-pressed="'+active+'">'+esc(s.symbol)+'</button>'+(shortlist.has(s.symbol)?'<span class="shortlist-mark">Shortlisted</span>':'')+'<span class="company">'+esc(s.company)+'</span><details><summary>Why in this view / source time</summary>'+esc(reviewReason(s))+'</details></td>'+shown.map(c=>'<td class="'+(['age','research'].includes(c.key)?'':'num')+'">'+columnCell(c,s)+'</td>').join('')+'</tr>';
 }).join(''):'<tr><td colspan="'+(shown.length+2)+'" class="no-results">No stocks match this view and search. Clear filters to return to all configured stocks.</td></tr>';
 $('universe-head').querySelectorAll('th[id]').forEach(th=>th.removeAttribute('aria-sort'));
 const head=$('head-'+sortKey);if(head)head.setAttribute('aria-sort',descending?'descending':'ascending');
 $('sort-by').value=sortKey;$('sort-direction').textContent=descending?'Descending ↓':'Ascending ↑';$('sort-direction').setAttribute('aria-label',descending?'Sort ascending':'Sort descending');
 box.scrollTop=scrollTop;box.scrollLeft=scrollLeft;persistPreferences();
}
function persistShortlist(){
 queueWorkspace({watchlists:watchlists.map(list=>({...list,symbols:[...list.symbols]}))});persistPreferences();
}
function bulkShortlist(add){
 const list=targetList();let changed=0;for(const s of selectedSymbols){if(add&&!list.symbols.has(s)){list.symbols.add(s);changed++;}else if(!add&&list.symbols.delete(s)){changed++;}}
 persistShortlist();selectedSymbols.clear();renderTable();$('feedback').textContent=(add?'Added ':'Removed ')+changed+' stock'+(changed===1?'':'s')+(add?' to ':' from ')+list.name+'.';
}
function createWatchlist(){
 const name=watchlistName.trim();if(!name||!selectedSymbols.size)return;
 if(watchlists.some(list=>list.name.toLowerCase()===name.toLowerCase())){$('feedback').textContent='A watchlist with that name already exists. Choose another name.';return;}
 const list={id:crypto.randomUUID(),name,symbols:new Set(selectedSymbols)};watchlists.push(list);activeListId=list.id;targetListId=list.id;selectedSymbols.clear();view='all';search='';minMove=0;watchlistName='';$('stock-search').value='';$('watchlist-name').value='';
 persistShortlist();renderTable(true);$('feedback').textContent='Created '+name+' with '+list.symbols.size+' stocks. Saving to the app.';
}
let workspaceRecord={revision:0,data:{notes:{},preferences:{}}},workspaceChanges={},workspaceBusy=false,workspaceError='',workspaceConflict=false,saveTimer,lastPreferences='',browserImport=null;
const noteDrafts=new Map();
function currentPreferences(){return {columns:{order:columnOrder,visible:[...visibleColumns]},search,view,sortKey,descending,minMove,activeListId,targetListId,portfolioView,holdingsQuery,holdingsSort,holdingsFilter,holdingsDescending,symbol,reportKey,runId:researchFor(symbol)?.run_id||''};}
function persistPreferences(){const value=currentPreferences(),encoded=JSON.stringify(value);if(encoded===lastPreferences)return;lastPreferences=encoded;queueWorkspace({preferences:value});}
function queueWorkspace(patch){
 workspaceChanges={...workspaceChanges,...patch,...(patch.notes?{notes:{...workspaceChanges.notes,...patch.notes}}:{})};
 clearTimeout(saveTimer);saveTimer=setTimeout(saveWorkspace,450);workspaceStatus();
}
function workspaceStatus(){
 const box=$('workspace-save-status');if(!box)return;
 box.innerHTML='<span>'+esc(workspaceError||(workspaceBusy?'Saving workspace…':Object.keys(workspaceChanges).length?'Unsaved workspace changes':'Workspace saved in the app · revision '+workspaceRecord.revision))+'</span> '+(workspaceError?'<button id="reload-workspace">Reload saved workspace (discard unsaved edits)</button> '+(!workspaceConflict?'<button id="retry-workspace">Retry save</button>':''):'')+(browserImport?'<button id="import-browser">Import this browser’s saved lists/preferences</button>':'');
 $('reload-workspace')?.addEventListener('click',async()=>{try{const record=await api('/api/workspace');workspaceChanges={};noteDrafts.clear();workspaceError='';workspaceConflict=false;adoptWorkspace(record,true);render();}catch(e){workspaceError=e.message;workspaceStatus();}});
 $('retry-workspace')?.addEventListener('click',saveWorkspace);
 $('import-browser')?.addEventListener('click',()=>{queueWorkspace({browser_import:browserImport});saveWorkspace();});
}
async function saveWorkspace(){
 if(workspaceBusy||workspaceConflict||!Object.keys(workspaceChanges).length)return;
 clearTimeout(saveTimer);workspaceBusy=true;workspaceError='';const submitted=workspaceChanges;workspaceChanges={};workspaceStatus();
 try{
  const record=await api('/api/workspace',{expected_revision:workspaceRecord.revision,changes:submitted});
  workspaceRecord=record;
  if(submitted.browser_import){browserImport=null;const skipped=record.data.last_import?.skipped_preferences||[];workspaceError=skipped.length?'Imported lists. Existing app preferences retained: '+skipped.join(', '):'';}
  if(!Object.keys(workspaceChanges).length)adoptWorkspace(record,true);
 }catch(e){workspaceChanges={...submitted,...workspaceChanges,...(submitted.notes?{notes:{...submitted.notes,...workspaceChanges.notes}}:{})};workspaceError=e.message;workspaceConflict=e.status===409;}
 finally{workspaceBusy=false;workspaceStatus();if(!workspaceError&&Object.keys(workspaceChanges).length)saveWorkspace();}
}
function adoptWorkspace(record,force=false){
 if(!record||!force&&(workspaceBusy||Object.keys(workspaceChanges).length||record.revision<=workspaceRecord.revision&&restored))return;
 workspaceRecord=record;const value=record.data,p=value.preferences||{};
 watchlists.splice(0,watchlists.length,...value.watchlists.map(list=>({...list,symbols:list.id==='shortlist'?shortlist:new Set(list.symbols)})));
 shortlist.clear();(value.watchlists.find(list=>list.id==='shortlist')?.symbols||[]).forEach(s=>shortlist.add(s));
 const keys=COLUMN_OPTIONS.map(c=>c.key);if(p.columns){columnOrder=[...new Set([...p.columns.order.filter(k=>keys.includes(k)),...keys])];visibleColumns=new Set(p.columns.visible.filter(k=>keys.includes(k)));}
 search=p.search??search;view=p.view??view;sortKey=p.sortKey??sortKey;descending=p.descending??descending;minMove=p.minMove??minMove;
 activeListId=watchlists.some(l=>l.id===p.activeListId)?p.activeListId:'';targetListId=watchlists.some(l=>l.id===p.targetListId)?p.targetListId:watchlists[0].id;
 portfolioView=['holdings','universe'].includes(p.portfolioView)?p.portfolioView:portfolioView;
 holdingsQuery=typeof p.holdingsQuery==='string'?p.holdingsQuery:holdingsQuery;holdingsSort=['symbol','qty','market_value','unrealized_pl'].includes(p.holdingsSort)?p.holdingsSort:holdingsSort;holdingsFilter=['all','outside','pending','gaps'].includes(p.holdingsFilter)?p.holdingsFilter:holdingsFilter;holdingsDescending=typeof p.holdingsDescending==='boolean'?p.holdingsDescending:holdingsDescending;
 symbol=p.symbol??symbol;reportKey=p.reportKey??reportKey;bridgeContext();lastPreferences=JSON.stringify(currentPreferences());
}
function restoreWatchlists(){
 try{const saved=JSON.parse(localStorage.getItem(WATCHLISTS_KEY)||'null'),legacy=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]'),columns=JSON.parse(localStorage.getItem(COLUMNS_KEY)||'null');
 const lists=saved?.lists?.length?saved.lists:legacy.length?[{id:'shortlist',name:'Shortlist',symbols:legacy}]:[];
 if(lists.length||columns)browserImport={id:crypto.randomUUID(),watchlists:lists.length?lists:[{id:'shortlist',name:'Imported shortlist',symbols:[]}],preferences:columns?{columns}:{}};
 }catch{workspaceError='Browser records could not be read. App records are retained.';}
}
function researchFor(s){return researchOrigin?.symbol===s?{...researchOrigin,...results.get(researchOrigin.run_id+':'+s+':'+(researchOrigin.revision||0))}:DATA.research[s];}
function bridgeContext(){selectedSymbol=symbol||selectedSymbol;selectedRunId=researchFor(symbol)?.run_id||'';}
let policyOpen=false,proposalListOpen=false;
let investorRecord=null,investorDirty=false,investorBusy=false,investorError='',investorConflict=false,policyDraft=null,policyReason='',proposalReason='';
const proposalForms=new Map(),proposalPreviews=new Map();
function proposalInput(){if(!proposalForms.has(symbol))proposalForms.set(symbol,{symbol,side:'',quantity:'',order_type:'',limit_price:'',rationale:'',research:null,decision_evidence_scopes:[]});return proposalForms.get(symbol);}
function clearProposalPreview(){proposalPreviews.delete(symbol);const box=$('proposal-impact');if(box)box.innerHTML=impactMarkup(null);investorDirty=true;}
function impactMarkup(proposal){
 if(!proposal)return '<p>Preview exact terms to inspect the available portfolio impact.</p>';
 const impact=proposal.impact,terms=proposal.terms,reviewedFees=proposal.review_constraints?.max_fees??proposal.risk_evaluation?.bindings?.constraints?.max_fees;
 return '<h3>Exact terms · '+esc(terms.side)+' '+esc(terms.quantity)+' '+esc(terms.symbol)+'</h3><p>'+esc(terms.order_type)+' '+esc(terms.limit_price||'No fixed market price')+' · DAY · regular session · account '+esc(terms.account_id||'Unavailable')+'</p>'+(terms.replacement?'<p>Replace broker order '+esc(terms.replacement.order_id)+' · total quantity includes '+esc(terms.replacement.filled_quantity)+' already filled shares · exact predecessor version '+esc(terms.replacement.order_version)+'</p>':'')+'<p>'+esc(terms.rationale||'No human rationale entered')+'</p><p>'+esc(terms.research?'Linked '+terms.research.report_key+' · run '+terms.research.run_id+' · revision '+terms.research.revision+' · SHA-256 '+terms.research.result_sha256:'Human proposal · no linked research')+'</p><dl>'+[['Existing quantity','existing_quantity'],['Proposed resulting quantity','resulting_quantity'],['Estimated principal / USD','estimated_principal'],['Cash change before fees / USD','estimated_cash_change_before_fees'],['Cash after known commitments before fees / USD','estimated_cash_after_commitments_before_fees'],['Current equity / USD','equity'],['Estimated position value / USD','position_value_estimate'],['Source long market value / USD','account_long_market_value'],['Fees / USD','fees']].map(([label,key])=>'<dt>'+label+'</dt><dd>'+esc(impact[key]??'Unavailable')+'</dd>').join('')+'</dl><p>'+esc(impact.fee_disclosure||'Actual fees are not sourced; a reviewed fee ceiling is a bound, not an actual fee.')+'</p><p>Estimate basis: '+esc(impact.price_basis)+' · account observed '+fullTime(impact.account_at)+' · market event ns '+esc(impact.price_event_ns||'Unavailable')+'</p><details><summary>Known working-order commitments</summary><pre>'+esc(JSON.stringify(impact.open_order_commitments,null,2))+'</pre></details><h3>Source limitations and review conditions</h3><ul>'+impact.conditions.map(c=>'<li>'+esc(c==='Fees are not sourced; after-fee cash impact is unknown'&&number(reviewedFees)!==null&&number(reviewedFees)>=0?'Actual fees remain unknown; review uses the explicit USD '+reviewedFees+' fee ceiling, not an assumed actual fee.':c)+'</li>').join('')+'</ul><details id="proposal-policy-scenarios"><summary>Current / pending / proposed policy calculations</summary><pre>'+esc(JSON.stringify(proposal.risk_evaluation?.policy_scenarios||{unavailable:'No server policy assessment recorded'},null,2))+'</pre></details><p>These are observation-based estimates. Exact saved-revision approval review appears separately.</p><a href="#orders">Review orders and submission status</a>';
}
function investorStatus(){
 return '<div class="feedback" role="status">'+esc(investorError||(investorBusy?'Saving investor record…':'Investor records · revision '+(investorRecord?.revision??0)))+(investorError?'<button id="reload-investor">Reload saved investor records (discard policy/proposal edits)</button>':'')+'</div>';
}
const approvalForms=new Map();
function approvalForm(id){
 const proposal=investorRecord?.data.proposals.find(p=>p.id===id),rules=investorRecord?.data.policy.rules||{},policyRevision=investorRecord?.data.policy.revision;
 const identity=JSON.stringify([state?.store_generation,id,proposal?.revision,proposal?.terms_sha256,policyRevision]);
 if(approvalForms.get(id)?.identity!==identity){
  const freshness=rules.session_freshness,policy={};
  if(freshness?.state==='enabled'&&typeof state.clock?.is_open==='boolean')policy.quote_max_age_seconds=state.clock.is_open?freshness.value:freshness.closed_max_age_seconds;
  const saved=Object.values(state.commands?.data.approvals||{}).filter(a=>a.proposal_id===id&&a.proposal_revision===proposal?.revision&&a.terms_sha256===proposal?.terms_sha256&&a.policy_revision===policyRevision).sort((a,b)=>String(b.approved_at).localeCompare(String(a.approved_at)))[0];
  const bound=proposal?.risk_evaluation?.bindings,review=bound?.proposal_revision===proposal?.revision&&bound?.terms_sha256===proposal?.terms_sha256&&bound?.policy_revision===policyRevision?proposal.review_constraints||bound.constraints:{};
  const seed={...policy,...saved?.constraints,...review,...(proposal?.terms.order_type==='LIMIT'?{max_execution_price:proposal.terms.limit_price}:{})},entry={identity,note:'',working_order_fee_caps:{...seed.working_order_fee_caps}};
  for(const key of ['account_max_age_seconds','quote_max_age_seconds','evidence_max_age_seconds','approval_max_age_seconds','max_execution_price','max_fees'])entry[key]=seed[key]??'';
  approvalForms.set(id,entry);
 }
 return approvalForms.get(id);
}
const policyRuleCopy={
 cash_reserve_pct:['Cash reserve','Minimum cash left (% of account equity)','Cash after reserving pending and proposed buys and fees; sale proceeds are not credited before they arrive.'],
 max_position_pct:['Single-stock exposure','Maximum for one stock (% of account equity)','Includes current exposure plus pending and proposed buys, without assuming sales fill.'],
 max_gross_exposure_pct:['Total stock exposure','Maximum total exposure (% of account equity)','Adds current stock exposure and pending/proposed buys; planned sales do not reduce this check.'],
 loss_limit_pct:['Current unrealized loss','Maximum unrealized loss (% of reported cost)','Uses aggregate broker-reported unrealized loss divided by reported cost basis. This is not a daily stop-loss or future-loss guarantee.'],
 scenario_loss_pct:['Price-fall scenario','Maximum estimated loss (% of account equity)','Models your chosen price fall across long stocks, including pending/proposed buys and fees, without assuming sales fill. This estimate is not a guaranteed loss cap.'],
 max_sector_pct:['Sector exposure','Maximum per sector (% of account equity)','Groups current exposure and pending/proposed buys by provider-reported sector. Missing or outdated sector data blocks this check.'],
 max_correlation_pct:['Stock-return correlation','Maximum absolute correlation (0–100)','Compares matching daily stock returns using the selected history and adjustment. A value of 100 means an absolute correlation of 1; the estimate does not guarantee diversification.'],
 max_spread_bps:['Bid/ask spread','Maximum spread (basis points)','Ask minus bid divided by their midpoint, using the same IEX quote. One basis point is 0.01%; this is not a consolidated-market liquidity measure.'],
 min_quote_size:['Displayed quote size','Minimum displayed quantity (shares)','Uses IEX ask shares for a buy or bid shares for a sale. Displayed size does not guarantee a fill or include hidden liquidity.'],
 session_freshness:['Quote freshness','Maximum quote age while open (seconds)','Choose the closed-market age limit and review permission separately. Closed-market review does not enable after-hours orders.']
};
const policyChoiceCopy={unset:'Decide later',enabled:'Apply this rule',disabled:'Do not apply',parallel_long_equity_price_shock:'Same percentage fall across long stock positions',pearson_daily_close_returns:'Pearson correlation of daily closing-price returns',provider_sector:'Sectors reported by the data provider',split:'Adjust for stock splits only',all:'All corporate-action adjustments supplied by the provider',regular_session_required:'Require the regular market session to be open',allow_closed_session_review:'Allow review while the regular market is closed'};
const policyParameterCopy={shock_pct:'Price fall to model (%)',classification:'Sector grouping',max_classification_age_seconds:'Oldest sector data allowed (seconds)',window_sessions:'Return window (trading sessions)',max_history_age_seconds:'Oldest correlation history allowed (seconds)',minimum_pairs:'Minimum matching daily return dates',adjustment:'Historical price adjustment',max_quote_age_seconds:'Oldest quote allowed (seconds)',closed_max_age_seconds:'Oldest closed-market quote allowed (seconds)',session:'When review is allowed'};
function policyParameterMarkup(key,rule){
 return Object.entries(investorRecord.rule_parameters?.[key]||{}).map(([name,definition])=>'<label>'+esc(policyParameterCopy[name]||definition.label)+(definition.choices?'<select id="policy-'+key+'-'+name+'" data-policy-key="'+key+'" data-policy-field="'+name+'"><option value="">Choose an option</option>'+definition.choices.map(v=>'<option value="'+esc(v)+'" '+(rule[name]===v?'selected':'')+'>'+esc(policyChoiceCopy[v]||v)+'</option>').join('')+'</select>':'<input id="policy-'+key+'-'+name+'" inputmode="decimal" data-policy-key="'+key+'" data-policy-field="'+name+'" value="'+esc(rule[name]??'')+'">')+'</label>').join('');
}
function approvalPanel(){
 const form=proposalInput(),proposal=investorRecord?.data.proposals.find(p=>p.id===form.id);if(!proposal)return '<section><h3>Review and approve an order</h3><p>Save the order terms before approving them. Saving does not submit an order.</p></section>';
  if(['rejected','deferred'].includes(proposal.status))return '<section class="investor-note"><h3>Order '+esc(proposal.status)+'</h3><p>This revision cannot be approved or submitted. Edit the order above and save a new draft revision before reviewing it for approval.</p></section>';
 const entry=approvalForm(proposal.id),evaluation=proposal.risk_evaluation;
 const matches=['side','quantity','order_type','rationale'].every(k=>String(form[k]??'')===String(proposal.terms[k]??''))&&String(form.limit_price||'')===String(proposal.terms.limit_price||'')&&JSON.stringify(form.research||null)===JSON.stringify(proposal.terms.research||null)&&JSON.stringify([...(form.decision_evidence_scopes||[])].sort())===JSON.stringify([...(proposal.terms.decision_evidence_scopes||[])].sort());
 const authority=state.commands||{},data=authority.data||{},related=Object.values(data.approvals||{}).filter(a=>a.proposal_id===proposal.id),enabled=investorRecord.approval_records_enabled===true;
 const expires=number(entry.approval_max_age_seconds)>0?new Date(Date.now()+Number(entry.approval_max_age_seconds)*1000):null,expiryLabel=expires&&Number.isFinite(expires.getTime())?fullTime(expires.toISOString()):'Single-use; valid only while these exact terms and relevant conditions remain unchanged';
 return '<section class="investor-note"><h3>Approve exact saved terms</h3><p><strong>'+esc(proposal.terms.side+' '+proposal.terms.quantity+' '+proposal.terms.symbol+' · '+proposal.terms.order_type)+(proposal.terms.limit_price?' · limit USD '+esc(proposal.terms.limit_price):'')+'</strong> · account '+esc(proposal.terms.account_id)+' · proposal revision '+proposal.revision+' · policy revision '+investorRecord.data.policy.revision+'</p><p>DAY · regular session. '+esc(proposal.terms.rationale)+'</p><details><summary>Exact saved terms and source identity</summary><p>Proposal '+esc(proposal.id)+' · SHA-256 '+esc(proposal.terms_sha256)+'</p><pre>'+esc(JSON.stringify(proposal.terms,null,2))+'</pre></details><p>'+esc(!matches?'Unsaved terms differ. Save the revision before evaluating or approving.':enabled?'Approval records your review; it never submits an order. Submit remains a separate explicit action.':'Browse-only mode does not permit approval or submission.')+'</p><details><summary>Optional limits for this order</summary><p>Existing configured limits still apply. Blank optional values do not block approval.</p><div class="proposal-fields">'+[['quote_max_age_seconds','Quote age limit / seconds (optional)'],['approval_max_age_seconds','Approval lifetime / seconds (optional)'],...(proposal.terms.side==='BUY'&&proposal.terms.order_type==='MARKET'?[['max_execution_price','Observed buy-price limit / USD (optional; market fill is not guaranteed)']]:[]),['max_fees','Fee estimate bound / USD (optional)']].map(([key,label])=>'<label>'+label+'<input id="approval-'+key+'" data-approval-field="'+key+'" type="number" min="0" step="any" value="'+esc(entry[key])+'"></label>').join('')+'<p>Approval validity: '+expiryLabel+'. Any configured lifetime is recorded by the server.</p><label>Optional review note<textarea id="approval-note" data-approval-field="note" rows="2">'+esc(entry.note)+'</textarea></label></div></details><button id="evaluate-approval" '+(!matches||investorBusy?'disabled':'')+'>Check order</button><button id="record-approval" '+(!enabled||!matches||investorBusy?'disabled':'')+'>Approve this order</button><p role="status">'+esc(investorError||evaluation?.evaluated_at||'No server evaluation recorded')+'</p>'+(evaluation?'<p>Server checks '+(evaluation.passed?'pass for the recorded observation':'need attention')+'</p><ul>'+evaluation.checks.filter(c=>!c.passed).map(c=>'<li>'+esc(c.reason)+'</li>').join('')+'</ul><details id="approval-source-calculations"><summary>Current / pending / proposed calculations and source bindings</summary><pre>'+esc(JSON.stringify(evaluation,null,2))+'</pre></details>':'')+related.map(a=>{
  const command=Object.values(data.commands||{}).find(c=>c.approval_id===a.id&&c.state==='admitted_not_dispatched'),valid=authority.approval_states?.[a.id]==='approved_awaiting_admission'||authority.approval_states?.[a.id]==='admitted'&&command;
  const canSubmit=valid&&!proposal.terms.replacement&&matches&&authority.execution_enabled===true&&(data.new_orders_blocked??false)===false&&!data.recovery_required&&!investorBusy;
  return '<article><p>Approval '+esc(a.id)+' · '+esc(authority.approval_states?.[a.id])+' · expires '+(a.expires_at?fullTime(a.expires_at):'until used or relevant conditions change')+'</p><p>'+esc(data.revocations?.[a.id]?.reason||'Approval alone reserves no resources')+'</p><button data-revoke-approval="'+esc(a.id)+'" '+(!enabled||investorBusy?'disabled':'')+'>Revoke approval</button><button '+(command?'data-command-submit="'+esc(command.id)+'"':'data-approval-submit="'+esc(a.id)+'"')+' '+(!canSubmit?'disabled':'')+'>Submit '+esc(a.terms.side+' '+a.terms.quantity+' '+a.terms.symbol)+' to configured account</button></article>';
 }).join('')+'<p>Submit validates current authority and reserves resources before sending. Current account checks, the approved terms and your pause choice still apply. <a href="#orders">Open order actions</a>.</p></section>';
}
async function approvalAction(action,approvalId){
 if(investorBusy||investorConflict)return;
 const proposal=investorRecord.data.proposals.find(p=>p.id===proposalInput().id),entry=approvalForm(proposal.id);
 investorBusy=true;investorError='';
 try{
  const constraints={};for(const key of ['account_max_age_seconds','quote_max_age_seconds','evidence_max_age_seconds','approval_max_age_seconds','max_execution_price','max_fees'])if(entry[key]!=='')constraints[key]=entry[key];
  constraints.working_order_fee_caps=Object.fromEntries(Object.entries(entry.working_order_fee_caps).filter(([,value])=>value!==''));
  const request={action,id:proposal.id,approval_id:approvalId,proposal_revision:proposal.revision,policy_revision:investorRecord.data.policy.revision,expected_revision:investorRecord.revision,commands_revision:state.commands.revision,note:entry.note,constraints,evaluation_binding_sha256:proposal.risk_evaluation?.binding_sha256,terms_sha256:proposal.terms_sha256};
  if(action==='approve'){
    const checked=await api('/api/investor',{...request,action:'review'});investorRecord=checked;state.investor=checked;
    const evaluated=checked.data.proposals.find(p=>p.id===proposal.id).risk_evaluation;
    if(!evaluated.passed)throw new Error(evaluated.blockers.join('; '));
    request.expected_revision=checked.revision;request.evaluation_binding_sha256=evaluated.binding_sha256;
   }
   const result=await api(action==='review'?'/api/investor':'/api/approvals',request);
  investorRecord=action==='review'?result:result.investor;state.investor=investorRecord;if(result.commands)state.commands=result.commands;investorDirty=false;await readState();
 }catch(error){investorError=error.message;investorConflict=error.status===409;}
 finally{investorBusy=false;render();}
}
function bindApproval(root){
 root.addEventListener('input',e=>{if(!proposalInput().id)return;const entry=approvalForm(proposalInput().id),key=e.target.dataset.approvalField,order=e.target.dataset.approvalWorkingOrderFee;if(key)entry[key]=e.target.value;if(order)entry.working_order_fee_caps[order]=e.target.value;});
 root.addEventListener('click',e=>{if(e.target.id==='evaluate-approval')approvalAction('review');if(e.target.id==='record-approval')approvalAction('approve');const revoke=e.target.closest('[data-revoke-approval]');if(revoke)approvalAction('revoke',revoke.dataset.revokeApproval);});
}
function proposalEditor(){
 const item=proposalInput(),instrument=investorRecord?.instruments?.[symbol],research=researchFor(symbol),canLink=Boolean(research?.reports?.[reportKey]);
 const predecessors=(state.nautilus?.orders||[]).filter(o=>o.symbol===symbol&&['new','accepted','partially_filled','pending_new'].includes(o.status)&&state.investor?.broker_order_actions?.[o.id]?.supported===true);
 return '<section class="proposal-editor"><h3>Human trade proposal · '+esc(symbol)+'</h3><p>'+esc(instrument?.limitation||'Supported equity · whole shares only')+'</p><p>Local human proposal only; saving does not create a native Nautilus order draft or grant approval. DAY, regular session. Approval and submission are separate explicit actions. Submit validates the approved terms and reserves resources internally.</p>'+investorStatus()+'<div class="proposal-fields"><label>Replace an existing working order (optional)<select id="proposal-replacement"><option value="">New order</option>'+predecessors.map(o=>'<option value="'+esc(o.id)+'" '+(item.replacement?.order_id===o.id?'selected':'')+'>'+esc(o.side+' '+o.qty+' '+o.symbol+' · filled '+o.filled_qty+' · '+o.id)+'</option>').join('')+'</select></label><label>Side<select id="proposal-side"><option value="">Choose side</option>'+['BUY','SELL'].map(v=>'<option '+(item.side===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><label>Whole shares (total includes prior fills for replacement)<input id="proposal-quantity" inputmode="numeric" value="'+esc(item.quantity)+'"></label><label>Order type<select id="proposal-order-type"><option value="">Choose order type</option>'+['MARKET','LIMIT'].map(v=>'<option '+(item.order_type===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><label>Limit price / USD<input id="proposal-limit-price" inputmode="decimal" value="'+esc(item.limit_price||'')+'"></label><label>Optional order note<textarea id="proposal-rationale" rows="4" maxlength="10000">'+esc(item.rationale)+'</textarea></label><fieldset><legend>Additional inputs this decision depends on</legend><p>Account and exact LIMIT terms or dated market evidence are required. Configured spread, size and age checks still apply. Select additional inputs your decision depends on; enabled policies determine other requirements. Linked saved research preserves exact provenance without forcing its adapters to run again.</p>'+['history','news','corporate_actions','earnings','fundamentals','classification'].map(scope=>'<label><input type="checkbox" data-decision-evidence-scope="'+scope+'" '+((item.decision_evidence_scopes||[]).includes(scope)?'checked':'')+'> '+esc(scope)+'</label>').join('')+'</fieldset><label><input id="proposal-link-research" type="checkbox" '+(item.research?'checked':'')+' '+(!canLink&&!item.research?'disabled':'')+'> Link the selected saved report, exact revision</label><p>'+esc(item.research?'Linked '+item.research.report_key+' · '+item.research.run_id+' · revision '+item.research.revision:'No linked research. A saved report and a rationale are optional; your exact order approval is required.')+'</p><label>Optional revision note<textarea id="proposal-review-reason" rows="2">'+esc(proposalReason)+'</textarea></label></div><div class="row"><button id="preview-proposal" '+(!instrument?.supported?'disabled':'')+'>Preview exact terms</button><button id="save-proposal" '+(!instrument?.supported?'disabled':'')+'>Save local proposal '+(item.id?'revision':'draft')+'</button>'+(item.id?'<button id="reject-proposal">Reject</button><button id="defer-proposal">Defer</button><button id="new-proposal">New proposal</button>':'')+'</div><div id="proposal-impact">'+impactMarkup(proposalPreviews.get(symbol))+'</div></section>';
}
function policyPanel(){
 if(!investorRecord)return '';
 const rules=policyDraft||investorRecord.data.policy.rules,labels=investorRecord.rule_labels;
 return '<details id="investor-policy" class="panel" '+(policyOpen?'open':'')+'><summary>Your risk checks · revision '+investorRecord.data.policy.revision+'</summary>'+investorStatus()+'<p>You can decide later and keep browsing. Only configured checks apply. Unset optional checks do not block orders; they are not treated as disabled or assigned defaults. Saving these choices does not approve or submit orders; exact-revision review and the account order block still apply.</p><div class="policy-rules">'+Object.entries(labels).map(([key,label])=>{const rule=rules[key]||{state:'unset',value:'',reason:''},copy=policyRuleCopy[key]||[label,label,''];return '<fieldset><legend>'+esc(copy[0])+'</legend><p>'+esc(copy[2])+'</p><label>Use this rule<select id="policy-state-'+key+'" data-policy-key="'+key+'" data-policy-field="state">'+['unset','enabled','disabled'].map(v=>'<option value="'+v+'" '+(rule.state===v?'selected':'')+'>'+esc(policyChoiceCopy[v])+'</option>').join('')+'</select></label><label>'+esc(copy[1])+'<input inputmode="decimal" id="policy-value-'+key+'" data-policy-key="'+key+'" data-policy-field="value" value="'+esc(rule.value||'')+'"></label><label>Optional note about this choice<input id="policy-rule-reason-'+key+'" data-policy-key="'+key+'" data-policy-field="reason" value="'+esc(rule.reason||'')+'"></label>'+policyParameterMarkup(key,rule)+'</fieldset>';}).join('')+'</div><label for="policy-reason">Optional note about these changes<textarea id="policy-reason" rows="2">'+esc(policyReason)+'</textarea></label><button id="save-policy">Save risk-check choices</button><p>Saving a policy revision invalidates dependent approval records. Missing source data can block an applied rule; a price-fall estimate is not a guaranteed loss cap.</p><details><summary>Policy history</summary><pre>'+esc(JSON.stringify(investorRecord.data.policy_history,null,2))+'</pre></details></details><details class="panel" id="investor-proposals" '+(proposalListOpen?'open':'')+'><summary>Saved human proposals · '+investorRecord.data.proposals.length+'</summary>'+investorRecord.data.proposals.map(p=>'<article><h3>'+esc(p.terms.side+' '+p.terms.quantity+' '+p.terms.symbol)+' · '+esc(p.status)+' · revision '+p.revision+'</h3><p>'+fullTime(p.updated_at)+(p.restored_requires_review?' · Restored records; impact review required':p.conditions_stale?' · Policy changed; impact review invalidated':'')+'</p><button data-open-proposal="'+esc(p.id)+'">Open exact terms / revise / review</button><details><summary>Revision history and source references</summary><pre>'+esc(JSON.stringify(p.history,null,2))+'</pre></details></article>').join('')+'</details>';
}
let basketOpen=false,basketForm={targets:[],reason:'',fee_per_leg:'',slippage_bps:'',assumed_filled:[]},basketPreview=null;
function loadBasket(basket){
 if(!basket)return;const p=basket.preview;
 basketForm={id:basket.id,targets:p.targets.map(t=>({symbol:t.symbol,mode:t.mode,value:t.value,order_type:t.order_type,limit_price:t.limit_price||''})),reason:p.reason,fee_per_leg:p.fee_per_leg??'',slippage_bps:p.slippage_bps??'',assumed_filled:p.partial_scenario.assumed_filled};
 basketPreview=p;basketOpen=true;
}
function basketScenario(value,label){
 const unknown=v=>esc(v??'Unavailable');
 return '<section><h3>'+label+'</h3><dl>'+[['Gross buys / USD','gross_buys'],['Gross sells / USD','gross_sells'],['Estimated fees / USD','estimated_fees'],['Estimated slippage / USD','estimated_slippage'],['Turnover / % of observed equity','turnover_pct'],['Hypothetical cash / USD','hypothetical_cash']].map(([name,key])=>'<dt>'+name+'</dt><dd>'+unknown(value[key])+'</dd>').join('')+'<dt>Buys covered by observed spendable funds, excluding sales</dt><dd>'+unknown(value.buys_fit_observed_spendable_without_sales===null?null:value.buys_fit_observed_spendable_without_sales?'Yes, estimate only':'No')+'</dd></dl><div class="basket-scroll"><table><thead><tr><th>Holding</th><th>Hypothetical quantity</th><th>Estimated value / USD</th><th>Estimated equity weight %</th></tr></thead><tbody>'+value.holdings.map(h=>'<tr><td>'+esc(h.symbol)+(h.unchanged_observation?' · unchanged source observation':'')+'</td><td>'+unknown(h.quantity)+'</td><td>'+unknown(h.market_value_estimate)+'</td><td>'+unknown(h.equity_weight_pct_estimate)+'</td></tr>').join('')+'</tbody></table></div><p>Remaining legs: '+esc(value.remaining_legs.join(', ')||'None in this scenario')+'</p></section>';
}
function basketEvidence(){
 const p=basketPreview;if(!p)return '<p>No allocation preview yet. Enter your own targets and preview.</p>';
 return '<h3>Hypothetical allocation · account '+esc(p.account_id||'Unavailable')+'</h3><p>Observed '+fullTime(p.account_at)+' · policy revision '+p.policy_revision+' · source SHA-256 '+esc(p.observation_sha256)+'</p><p>Weight targets use the entered percentage of observed equity, then floor the desired position to whole shares. Residuals remain explicit. Current and pending source observations are separate from proposed holdings.</p><div class="basket-scroll"><table><thead><tr><th>Symbol / source</th><th>Current qty</th><th>Pending net qty</th><th>Qty if working orders fill</th><th>Target qty</th><th>Whole-share residual USD / weight %</th></tr></thead><tbody>'+p.targets.map(t=>'<tr><td>'+esc(t.symbol)+'<br>'+esc(t.valuation_price??'Price unavailable')+' · '+esc(t.valuation_basis)+'<br>Event ns '+esc(t.market_event_ns||'Unavailable')+'</td><td>'+esc(t.current_quantity??'Unavailable')+'</td><td>'+esc(t.pending_net_quantity??'Unavailable')+'</td><td>'+esc(t.quantity_if_working_orders_fill??'Unavailable')+'</td><td>'+esc(t.desired_quantity??'Unavailable')+'</td><td>'+esc(t.residual_cash??'Not a weight target / unavailable')+' / '+esc(t.residual_weight_pct??'Unavailable')+'</td></tr>').join('')+'</tbody></table></div><h3>Individual proposed legs</h3>'+p.legs.map(leg=>'<details><summary>'+esc(leg.terms.side+' '+leg.terms.quantity+' '+leg.symbol+' · '+leg.terms.order_type)+' · '+esc(leg.proposal_id||'Not saved')+'</summary>'+impactMarkup(leg)+'</details>').join('')+'<h3>Assume individual fills for a partial-completion preview</h3><p>A basket is not atomic. These selections do not execute anything or modify observed holdings.</p>'+p.legs.map(leg=>'<label><input type="checkbox" data-basket-fill="'+esc(leg.symbol)+'" '+(basketForm.assumed_filled.includes(leg.symbol)?'checked':'')+'> Assume '+esc(leg.symbol)+' filled</label>').join('')+'<button id="partial-basket">Recalculate assumed fills</button>'+basketScenario(p.complete_scenario,'All proposed legs assumed filled')+basketScenario(p.partial_scenario,'Selected individual legs assumed filled')+'<h3>Aggregate policy and adverse scenarios</h3><p>Complete and partial assumptions include current holdings and pending commitments. Configured rules still need their relevant source inputs. Unknown fees are excluded from estimates, not assumed zero.</p><details id="basket-policy-scenarios"><summary>Current / pending / proposed exposure, sector, correlation, liquidity and loss checks</summary><pre>'+esc(JSON.stringify(p.policy_scenarios||{unavailable:'This legacy preview predates source-bound aggregate policy calculations'},null,2))+'</pre></details><h3>Conditions and conflicts</h3><ul>'+p.conditions.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul><details><summary>Working orders and conflicting proposals</summary><pre>'+esc(JSON.stringify({working_orders:p.working_orders,other_proposal_ids:p.conflicting_proposal_ids},null,2))+'</pre></details><p>Hypothetical sale proceeds are not approval to fund buys. No order is submitted.</p>';
}
function basketPanel(){
 if(!investorRecord)return '';const instruments=Object.values(investorRecord.instruments),baskets=investorRecord.data.baskets||[];
 return '<details id="allocation-workspace" class="panel" '+(basketOpen?'open':'')+'><summary>Allocation targets and baskets · '+baskets.length+' saved</summary>'+investorStatus()+'<p>Local human basket only; saving creates local linked proposals and grants no approval or native order authority. Enter target quantities or weights. No targets are preselected. Holdings outside the watchlist remain available; unsupported observations retain their limitation.</p><label>Add target stock<select id="basket-add-symbol"><option value="">Choose a stock or holding</option>'+instruments.map(i=>'<option value="'+esc(i.symbol)+'" '+(!i.supported?'disabled':'')+'>'+esc(i.symbol+(i.holding?' · held':'')+(i.limitation?' · '+i.limitation:''))+'</option>').join('')+'</select></label><button id="basket-add-selected">Add selected universe stocks as empty targets</button><div class="basket-scroll"><table><thead><tr><th>Symbol</th><th>Target type</th><th>Your target</th><th>Order type</th><th>Limit / USD</th><th></th></tr></thead><tbody>'+basketForm.targets.map((t,i)=>'<tr><td>'+esc(t.symbol)+'</td><td><select id="basket-mode-'+i+'" data-target-index="'+i+'" data-target-field="mode"><option value="">Choose</option>'+['quantity','weight'].map(v=>'<option '+(t.mode===v?'selected':'')+'>'+v+'</option>').join('')+'</select></td><td><input id="basket-value-'+i+'" inputmode="decimal" data-target-index="'+i+'" data-target-field="value" value="'+esc(t.value)+'"></td><td><select id="basket-type-'+i+'" data-target-index="'+i+'" data-target-field="order_type"><option value="">Choose</option>'+['MARKET','LIMIT'].map(v=>'<option '+(t.order_type===v?'selected':'')+'>'+v+'</option>').join('')+'</select></td><td><input id="basket-limit-'+i+'" inputmode="decimal" data-target-index="'+i+'" data-target-field="limit_price" value="'+esc(t.limit_price)+'"></td><td><button data-remove-target="'+i+'">Remove</button></td></tr>').join('')+'</tbody></table></div><label>Target / revision / review rationale<textarea id="basket-reason" rows="3">'+esc(basketForm.reason)+'</textarea></label><label>Estimated fee per leg / USD · optional, unset until entered<input id="basket-fee" inputmode="decimal" value="'+esc(basketForm.fee_per_leg)+'"></label><label>Estimated slippage / basis points · optional<input id="basket-slippage" inputmode="decimal" value="'+esc(basketForm.slippage_bps)+'"></label><div class="row"><button id="preview-basket">Preview basket</button><button id="save-basket">Save local '+(basketForm.id?'basket revision':'basket draft')+'</button>'+(basketForm.id?'<button id="reject-basket">Reject basket and linked proposals</button><button id="defer-basket">Defer basket and linked proposals</button>':'')+'<button id="new-basket">New empty basket</button><a href="#orders">Review exact leg approvals and basket command controls</a></div><div id="basket-preview">'+basketEvidence()+'</div><h3>Saved baskets</h3>'+baskets.map(b=>'<article><p>'+esc(b.status)+' · revision '+b.revision+' · '+fullTime(b.updated_at)+' · '+(b.impact_review_valid?'Saved impact preview; each order still needs approval':'Preview needs review')+'</p><button data-open-basket="'+esc(b.id)+'">Open basket '+esc(b.id.slice(0,8))+'</button><details><summary>Revision history</summary><pre>'+esc(JSON.stringify(b.history,null,2))+'</pre></details></article>').join('')+'</details>';
}
function addBasketTarget(s){
 if(!investorRecord.instruments[s]?.supported||basketForm.targets.some(t=>t.symbol===s))return;
 basketForm.targets.push({symbol:s,mode:'',value:'',order_type:'',limit_price:''});basketForm.assumed_filled=[];basketPreview=null;basketOpen=true;investorDirty=true;
}
function bindBaskets(root){
 root.addEventListener('toggle',e=>{if(e.target.id==='allocation-workspace')basketOpen=e.target.open;},true);
 root.addEventListener('input',e=>{
  const index=e.target.dataset.targetIndex,field=e.target.dataset.targetField;
  if(index!==undefined){basketForm.targets[Number(index)][field]=e.target.value;basketForm.assumed_filled=[];basketPreview=null;investorDirty=true;}
  const fields={'basket-reason':'reason','basket-fee':'fee_per_leg','basket-slippage':'slippage_bps'};
  if(fields[e.target.id]){basketForm[fields[e.target.id]]=e.target.value;basketPreview=null;investorDirty=true;}
 });
 root.addEventListener('change',e=>{
  if(e.target.id==='basket-add-symbol'&&e.target.value){addBasketTarget(e.target.value);render();}
  if(e.target.dataset.basketFill){const s=e.target.dataset.basketFill;basketForm.assumed_filled=e.target.checked?[...new Set([...basketForm.assumed_filled,s])]:basketForm.assumed_filled.filter(v=>v!==s);investorDirty=true;}
 });
 root.addEventListener('click',e=>{
  const open=e.target.closest('[data-open-basket]'),remove=e.target.closest('[data-remove-target]');
  if(open){loadBasket(investorRecord.data.baskets.find(b=>b.id===open.dataset.openBasket));render();return;}
  if(remove){basketForm.targets.splice(Number(remove.dataset.removeTarget),1);basketForm.assumed_filled=[];basketPreview=null;investorDirty=true;render();return;}
  const id=e.target.id;
  if(id==='basket-add-selected'){selectedSymbols.forEach(addBasketTarget);render();}
  if(id==='new-basket'){basketForm={targets:[],reason:'',fee_per_leg:'',slippage_bps:'',assumed_filled:[]};basketPreview=null;render();}
  if(['preview-basket','partial-basket','save-basket','reject-basket','defer-basket'].includes(id))investorAction({...basketForm,action:({'preview-basket':'basket_preview','partial-basket':'basket_preview','save-basket':'basket_draft','reject-basket':'basket_reject','defer-basket':'basket_defer'})[id]});
 });
}
async function investorAction(request){
 if(investorBusy||investorConflict)return;investorBusy=true;investorError='';
 const isBasket=request.action.startsWith('basket_'),form=isBasket?basketForm:request.terms&&proposalForms.get(request.terms.symbol),snapshot=JSON.stringify(form),generation=state.store_generation;
 request=structuredClone(request);
 const current=()=>state.store_generation===generation&&(!form||form===(isBasket?basketForm:proposalForms.get(request.terms.symbol))&&JSON.stringify(form)===snapshot);
 try{
  const result=await api('/api/investor',{...request,expected_revision:investorRecord.revision});
  if(state.store_generation!==generation)return;
  if(request.action==='basket_preview'){if(current())basketPreview=result.preview;}
  else if(request.action==='preview'){if(current())proposalPreviews.set(request.terms.symbol,result.preview);}
  else{
   investorRecord=result;state.investor=result;if(current())investorDirty=false;
   if(isBasket){const item=result.data.baskets.find(b=>b.id===request.id)||result.data.baskets[0];if(current())loadBasket(item);else if(form===basketForm&&item)form.id=item.id;}
   else if(request.action==='policy'){policyDraft=null;policyReason='';}
   else{const item=result.data.proposals.find(p=>p.id===request.id)||result.data.proposals[0];if(current()){if(item){proposalForms.set(item.terms.symbol,{...item.terms,id:item.id});proposalPreviews.set(item.terms.symbol,item);}proposalReason='';}else if(form===proposalForms.get(request.terms.symbol)&&item)form.id=item.id;}
  }
 }catch(e){if(current()||!['preview','basket_preview'].includes(request.action)){investorError=e.message;investorConflict=e.status===409;}}
 finally{investorBusy=false;render();}
}
function bindInvestor(){
 const root=$('universe-review');if(!root||root.dataset.investorBound)return;root.dataset.investorBound='1';bindBaskets(root);bindAttention(root);bindApproval(root);
 root.addEventListener('toggle',e=>{if(e.target.id==='investor-policy')policyOpen=e.target.open;if(e.target.id==='investor-proposals')proposalListOpen=e.target.open;},true);
 root.addEventListener('input',e=>{
  const key=e.target.dataset.policyKey,field=e.target.dataset.policyField;
  if(key){if(!policyDraft)policyDraft=structuredClone(investorRecord.data.policy.rules);if(!policyDraft[key])policyDraft[key]={state:'unset',value:'',reason:''};policyDraft[key][field]=e.target.value;investorDirty=true;}
  if(e.target.id==='policy-reason'){policyReason=e.target.value;investorDirty=true;}
  const fields={'proposal-side':'side','proposal-quantity':'quantity','proposal-order-type':'order_type','proposal-limit-price':'limit_price','proposal-rationale':'rationale'};
  if(fields[e.target.id]){proposalInput()[fields[e.target.id]]=e.target.value;clearProposalPreview();}
  if(e.target.id==='proposal-review-reason'){proposalReason=e.target.value;investorDirty=true;}
 });
 root.addEventListener('change',e=>{
  if(e.target.id==='proposal-replacement'){
   const order=(state.nautilus?.orders||[]).find(o=>o.id===e.target.value),item=proposalInput();
   item.replacement=order?{order_id:order.id}:null;
   if(order){item.side=String(order.side).toUpperCase();item.order_type=String(order.type||order.order_type).toUpperCase();item.quantity=order.qty;item.limit_price=order.limit_price||'';}
   clearProposalPreview();render();
  }
  if(e.target.dataset.decisionEvidenceScope){
   const scope=e.target.dataset.decisionEvidenceScope,scopes=new Set(proposalInput().decision_evidence_scopes||[]);
   e.target.checked?scopes.add(scope):scopes.delete(scope);proposalInput().decision_evidence_scopes=[...scopes].sort();clearProposalPreview();render();
  }
  if(e.target.id==='proposal-link-research'){
   const r=researchFor(symbol);proposalInput().research=e.target.checked?{run_id:r.run_id,symbol,revision:r.revision||0,report_key:reportKey}:null;clearProposalPreview();
  }
 });
 root.addEventListener('click',async e=>{
  const id=e.target.id,open=e.target.closest('[data-open-proposal]');
  if(open){const item=investorRecord.data.proposals.find(p=>p.id===open.dataset.openProposal);proposalForms.set(item.terms.symbol,{...item.terms,id:item.id});proposalPreviews.set(item.terms.symbol,item);openStock(item.terms.symbol,open);return;}
  if(id==='reload-investor'){try{investorRecord=await api('/api/investor');state.investor=investorRecord;investorDirty=false;investorError='';investorConflict=false;policyDraft=null;policyReason='';proposalReason='';proposalForms.clear();proposalPreviews.clear();basketForm={targets:[],reason:'',fee_per_leg:'',slippage_bps:'',assumed_filled:[]};basketPreview=null;render();}catch(error){investorError=error.message;render();}}
  if(id==='save-policy'){const rules=structuredClone(policyDraft||investorRecord.data.policy.rules);for(const key of Object.keys(investorRecord.rule_labels))if(!rules[key])rules[key]={state:'unset',value:null,reason:''};investorAction({action:'policy',rules,reason:policyReason});}
  if(['preview-proposal','save-proposal','reject-proposal','defer-proposal'].includes(id)){const item=proposalInput();investorAction({action:({'preview-proposal':'preview','save-proposal':'draft','reject-proposal':'reject','defer-proposal':'defer'})[id],id:item.id,terms:item,reason:proposalReason});}
  if(id==='new-proposal'){proposalForms.delete(symbol);proposalPreviews.delete(symbol);proposalReason='';render();}
 });
}
let attentionRecord=null,attentionDirty=false,attentionError='',attentionConflict=false,attentionBusy=false,attentionOpen=false;
let ruleDraft={name:'',kind:'',scope:'',symbol:'',threshold:'',max_age_seconds:'',proposal_id:'',condition:'',active:false};
const reviewDrafts=new Map();
const reviewKey=s=>{const r=researchFor(s);return r?s+':'+r.run_id+':'+(r.revision||0):'';};
function reviewDisposition(s){const saved=attentionRecord?.data.reviews?.[reviewKey(s)];return saved?.review_required?{...saved,recorded_disposition:saved.disposition,disposition:'needs_review'}:saved;}
function ownedRows(){return DATA.held_stocks||[];}
function reviewReason(s){
 const r=DATA.research[s.symbol],review=reviewDisposition(s.symbol),position=DATA.holdings.find(p=>p.symbol===s.symbol);
 return (position?'Owned · account '+(DATA.account_observed_at||'observation unavailable')+(position.import_error?' · '+position.import_error:'')+'; ':'')+(r?'Saved research '+r.trade_date+' · run '+r.run_id+' revision '+(r.revision||0)+' · '+(review?.disposition||'No human review recorded'):'No saved research; no recommendation is implied')+(s.quote.price==null?' · price missing':s.quote.stale?' · stale price at '+(s.quote.timestamp||'unknown time'):' · price event '+s.quote.timestamp);
}
function reviewEditor(){
 const r=researchFor(symbol);if(!r)return '<section><h3>Research review priority</h3><p>No saved result for this stock. New research is separate from reviewing this saved result.</p></section>';
 const key=reviewKey(symbol),saved=reviewDisposition(symbol);if(!reviewDrafts.has(key))reviewDrafts.set(key,{disposition:saved?.recorded_disposition||saved?.disposition||'',notes:saved?.notes||'',prioritize:saved?.prioritize||false});
 const draft=reviewDrafts.get(key),today=marketDate(),age=Math.round((Date.parse(today+'T00:00:00Z')-Date.parse(r.trade_date+'T00:00:00Z'))/86400000);
 return '<section class="investor-note"><h3>Review this saved revision</h3><p>Run '+esc(r.run_id)+' · revision '+esc(r.revision||0)+' · research date '+esc(r.trade_date)+' · '+esc(Number.isFinite(age)?(age<0?'research date is after the current market date':age+' calendar days old')+' · America/New_York date '+today:'age unavailable')+'</p><p>Observed gaps: '+esc(stock().quote.error||'See the dated source receipts and saved market-evidence gaps')+'</p><label>Human disposition<select id="research-disposition"><option value="">Choose a disposition</option>'+['reviewed','needs_review','deferred'].map(v=>'<option '+(draft.disposition===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><label for="research-review-notes">Review notes<textarea id="research-review-notes" rows="3">'+esc(draft.notes)+'</textarea></label><label><input id="research-priority" type="checkbox" '+(draft.prioritize?'checked':'')+'> Prioritize future research · does not start a job</label><button id="save-research-review">Save revision review</button><p>'+esc(attentionError||(saved?.review_required?'Review required: '+saved.review_reasons.join('; '):saved?.saved_at)||'No saved disposition')+'</p><details><summary>Saved opposing arguments and source text</summary>'+(Object.entries(r.reports||{}).filter(([key])=>/debate/.test(key)).map(([key,value])=>'<h4>'+esc(key)+'</h4><pre>'+esc(asText(value))+'</pre>').join('')||'<p>No separate debate artifact was saved. Select the source reports above.</p>')+'</details></section>';
}
async function attentionAction(request){
 if(attentionBusy||attentionConflict)return;attentionBusy=true;attentionError='';
 try{const result=await api('/api/attention',{...request,expected_revision:attentionRecord.revision});attentionRecord=result;state.attention=result;attentionDirty=false;if(request.action==='save')ruleDraft={name:'',kind:'',scope:'',symbol:'',threshold:'',max_age_seconds:'',proposal_id:'',condition:'',active:false};}
 catch(error){attentionError=error.message;attentionConflict=error.status===409;}
 finally{attentionBusy=false;render();}
}
function attentionPanel(){
 if(!attentionRecord)return '';const observed=attentionRecord.observations.data,monitor=observed.monitor,age=monitor.last_evaluated_at?(Date.now()-Date.parse(monitor.last_evaluated_at))/1000:null;
 const rules=Object.values(attentionRecord.data.rules).filter(r=>!r.removed),occurrences=Object.values(observed.occurrences).sort((a,b)=>b.created_at.localeCompare(a.created_at));
 const covered=DATA.stocks.filter(s=>liveQuoteState(s.quote)==='current').length,unconfigured=DATA.stocks.filter(s=>s.quote.freshness_configured!==true||number(s.quote.max_age_seconds)===null).length;
 return '<details id="attention-workspace" class="panel" '+(attentionOpen?'open':'')+'><summary>Attention and alert rules · '+occurrences.filter(o=>o.unread).length+' unread</summary><p role="status">'+esc(attentionError||'Rule configuration revision '+attentionRecord.revision)+'</p>'+(attentionError?'<button id="reload-attention">Reload saved attention state (discard rule edits)</button>':'')+'<p>Monitor '+esc(age===null?'not yet evaluated':age>15?'evaluation stale / interrupted':monitor.state)+' · evaluated '+fullTime(monitor.last_evaluated_at)+' · '+covered+' within their price-age limit; '+unconfigured+' / '+DATA.stocks.length+' stocks have no price-age limit configured. An unset limit does not establish freshness.</p><p>Rules use existing snapshots. Configured rules do not prove an interval was continuously observed. Acknowledgment never approves a trade.</p><details><summary>Monitoring gaps</summary><pre>'+esc(JSON.stringify(monitor.gaps,null,2))+'</pre></details><h3>Attention occurrences</h3>'+occurrences.map(o=>'<article><h4>'+esc(o.name)+' · '+esc(o.symbol||o.scope)+' · '+(o.unread?'Unread':'Acknowledged')+'</h4><p>'+esc(o.evaluation.reason)+' · source '+fullTime(o.evaluation.source_at)+' · evaluated '+fullTime(o.evaluation.at)+'</p><p>Rule '+esc(o.rule_id)+' revision '+o.rule_revision+' · input '+esc(o.evaluation.input_identity)+'</p>'+(o.symbol?'<button data-attention-stock="'+esc(o.symbol)+'">Open stock evidence</button>':'')+(o.unread?'<button data-ack-attention="'+esc(o.id)+'">Acknowledge</button>':'<p>Acknowledged '+fullTime(o.acknowledged_at)+'</p>')+'</article>').join('')+'<h3>Your alert rules</h3>'+rules.map(r=>{const observation=observed.rule_states[r.id],evaluation=observation?.rule_revision===r.revision?observation.evaluation:null;return '<article><p>'+esc(r.name)+' · '+esc(r.kind)+' · '+esc(r.scope)+' / '+esc(r.symbol||'account')+' · revision '+r.revision+' · '+(r.active?'Active configuration':'Paused')+'</p><p>'+esc(evaluation?.state||'Not evaluated')+' · '+esc(evaluation?.reason||(r.active?'Awaiting an observation for this revision':'This paused revision has not been evaluated'))+'</p><button data-edit-rule="'+esc(r.id)+'">Edit</button><button data-rule-action="'+(r.active?'pause':'resume')+'" data-rule-id="'+esc(r.id)+'">'+(r.active?'Pause':'Resume')+'</button><button data-rule-action="remove" data-rule-id="'+esc(r.id)+'">Remove</button></article>';}).join('')+'<h3>'+esc(ruleDraft.id?'Edit rule':'Create an explicit rule')+'</h3><div class="proposal-fields"><label>Rule name<input id="alert-name" value="'+esc(ruleDraft.name)+'"></label><label>Rule type<select id="alert-kind"><option value="">Choose</option>'+['price_above','price_below','movement','source_missing','source_stale','policy_condition'].map(v=>'<option '+(ruleDraft.kind===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><label>Source scope<select id="alert-scope"><option value="">Choose</option>'+['quote','account','research','history','news','earnings','fundamentals','corporate_actions','classification'].map(v=>'<option '+(ruleDraft.scope===v?'selected':'')+'>'+v+'</option>').join('')+'</select></label><label>Symbol · blank for account condition<input id="alert-symbol" value="'+esc(ruleDraft.symbol)+'"></label><label>Price threshold / USD or absolute movement / %<input id="alert-threshold" inputmode="decimal" value="'+esc(ruleDraft.threshold)+'"></label><label>Maximum source age / seconds<input id="alert-age" inputmode="decimal" value="'+esc(ruleDraft.max_age_seconds)+'"></label><label>Proposal ID · policy condition only<input id="alert-proposal" value="'+esc(ruleDraft.proposal_id)+'"></label><label>Exact saved policy condition · policy rule only<textarea id="alert-condition" rows="2">'+esc(ruleDraft.condition)+'</textarea></label><label><input id="alert-active" type="checkbox" '+(ruleDraft.active?'checked':'')+'> Evaluate this rule while the service runs</label><button id="save-alert-rule">Save rule</button></div><h3>Future research priorities</h3><p>'+esc(Object.values(attentionRecord.data.reviews).filter(r=>r.prioritize).map(r=>r.symbol+' · '+r.run_id+' revision '+r.research_revision).join('; ')||'No priorities saved')+'</p><p>Provider '+esc(state.config.llm_provider)+' · fast model '+esc(state.config.quick_think_llm)+' · deep model '+esc(state.config.deep_think_llm)+' · selected stocks '+esc([...selectedSymbols].join(', ')||'None')+'</p><p>Recorded usage belongs to the saved runs. New-run estimates appear in the existing research confirmation. Cancellation of a future run cannot erase completed saved evidence.</p><p>Start new research through the existing research controls when this session permits it.</p></details>';
}
function bindAttention(root){
 root.addEventListener('toggle',e=>{if(e.target.id==='attention-workspace')attentionOpen=e.target.open;},true);
 root.addEventListener('input',e=>{
  const fields={'alert-name':'name','alert-kind':'kind','alert-scope':'scope','alert-symbol':'symbol','alert-threshold':'threshold','alert-age':'max_age_seconds','alert-proposal':'proposal_id','alert-condition':'condition'};
  if(fields[e.target.id]){ruleDraft[fields[e.target.id]]=e.target.value;attentionDirty=true;}
  const draft=reviewDrafts.get(reviewKey(symbol));if(draft){if(e.target.id==='research-disposition')draft.disposition=e.target.value;if(e.target.id==='research-review-notes')draft.notes=e.target.value;}
 });
 root.addEventListener('change',e=>{if(e.target.id==='alert-active'){ruleDraft.active=e.target.checked;attentionDirty=true;}if(e.target.id==='research-priority')reviewDrafts.get(reviewKey(symbol)).prioritize=e.target.checked;});
 root.addEventListener('click',async e=>{
  const open=e.target.closest('[data-attention-stock]'),ack=e.target.closest('[data-ack-attention]'),edit=e.target.closest('[data-edit-rule]'),action=e.target.closest('[data-rule-action]');
  if(open)openStock(open.dataset.attentionStock,open);
  if(ack){const occurrence=attentionRecord.observations.data.occurrences[ack.dataset.ackAttention];attentionAction({action:'acknowledge',id:occurrence.id,occurrence_revision:occurrence.revision});}
  if(edit){const rule=attentionRecord.data.rules[edit.dataset.editRule];ruleDraft={...rule,...rule.parameters};attentionOpen=true;render();}
  if(action)attentionAction({action:action.dataset.ruleAction,id:action.dataset.ruleId});
  if(e.target.id==='save-alert-rule')attentionAction({action:'save',id:ruleDraft.id,name:ruleDraft.name,kind:ruleDraft.kind,scope:ruleDraft.scope,symbol:ruleDraft.symbol.toUpperCase(),active:ruleDraft.active,parameters:{threshold:ruleDraft.threshold,max_age_seconds:ruleDraft.max_age_seconds,proposal_id:ruleDraft.proposal_id,condition:ruleDraft.condition}});
  if(e.target.id==='save-research-review'){const r=researchFor(symbol);attentionAction({action:'review',symbol,run_id:r.run_id,research_revision:r.revision||0,...reviewDrafts.get(reviewKey(symbol))});}
  if(e.target.id==='reload-attention'){try{attentionRecord=await api('/api/attention');state.attention=attentionRecord;attentionDirty=false;attentionError='';attentionConflict=false;ruleDraft={name:'',kind:'',scope:'',symbol:'',threshold:'',max_age_seconds:'',proposal_id:'',condition:'',active:false};render();}catch(error){attentionError=error.message;render();}}
 });
}
function noteEditor(){
 const saved=workspaceRecord.data.notes?.[symbol],draft=noteDrafts.has(symbol)?noteDrafts.get(symbol):saved?.text||'';
 return '<section class="investor-note"><h3>Investor note · '+esc(symbol)+'</h3><label for="investor-note">Your rationale and questions</label><textarea id="investor-note" rows="5" maxlength="20000">'+esc(draft)+'</textarea><button id="save-investor-note">Save note</button><p class="muted">'+(saved?'Saved '+fullTime(saved.updated_at):'No saved note')+' · notes do not run research or authorize trading.</p></section>';
}
function bindNote(){
 const input=$('investor-note');if(input&&!input.dataset.bound){input.dataset.bound='1';const noteSymbol=symbol;input.addEventListener('input',e=>noteDrafts.set(noteSymbol,e.target.value));}
 $('save-investor-note')?.addEventListener('click',()=>{queueWorkspace({notes:{[symbol]:{text:noteDrafts.get(symbol)??workspaceRecord.data.notes?.[symbol]?.text??''}}});saveWorkspace();});
}
function bindReport(){
 bindNote();bindEvidence();
 $('report-select')?.addEventListener('change',e=>{
  reportKey=e.target.value;persistPreferences();const box=$('detail-content'),scroll=box.scrollTop;box.querySelector('.research').outerHTML=research();bindReport();box.scrollTop=scroll;$('report-select')?.focus();
 });
}
function openStock(s,trigger,context=null){
 returnWindowScroll=window.scrollY;paneScroll=[0,0];
 marketController?.abort();symbol=s;researchOrigin=context;bridgeContext();detailOpen=true;reportKey=context?.report_key||'final_trade_decision';returnFocus=trigger;$('detail-title').textContent=s+' / Stock review';$('stock-detail').hidden=false;$('workspace').classList.add('detail-open');
 $('detail-content').innerHTML=evidence()+research();$('detail-content').scrollTop=0;bindReport();
 document.querySelectorAll('[data-row]').forEach(row=>{const active=row.dataset.row===s;row.classList.toggle('row-active',active);row.querySelector('[data-stock]').setAttribute('aria-pressed',String(active));});
 $('close-detail').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});persistPreferences();loadDetail(s);loadStockEvidence(s);if((marketModes.get(s)||(DATA.research[s]?'saved':'current'))==='current')loadCurrentHistory(s,marketForm(s).key);
}
function closeStock(){marketController?.abort();detailOpen=false;
 $('stock-detail').hidden=true;$('workspace').classList.remove('detail-open');
 document.querySelectorAll('[data-row]').forEach(row=>{row.classList.remove('row-active');row.querySelector('[data-stock]').setAttribute('aria-pressed','false');});
 if(returnFocus?.isConnected)returnFocus.focus();else $('stock-search').focus();
 window.scrollTo({top:returnWindowScroll,behavior:'instant'});
}

let detailOpen=false, detailScroll=0, restored=false, paneScroll=[0,0], tableScroll=[0,0];
const results=new Map(), history=new Map(), pending=new Set(), failures=new Map();
const cacheKey=s=>{const r=researchFor(s);return r?r.run_id+':'+s+':'+(r.revision||0):'';};
function research(){
 const r=researchFor(symbol),key=cacheKey(symbol);
 if(r&&!r.reports)return '<section class="panel research"><h2>'+esc(symbol)+' saved research</h2>'+noteEditor()+proposalEditor()+approvalPanel()+reviewEditor()+'<p>'+esc(failures.get(key)||'Loading the existing saved report…')+'</p>'+(failures.has(key)?'<button id="ur-retry-detail">Retry saved data</button>':'')+'</section>';
 return savedResearch().replace('<section class="panel research">','<section class="panel research">'+noteEditor()+proposalEditor()+approvalPanel()+reviewEditor());
}
async function loadDetail(s){
 const r=researchFor(s),key=cacheKey(s);if(!r||pending.has(key)||results.has(key))return;
 pending.add(key);failures.delete(key);
 try{
  const [result,chart]=await Promise.all([api('/api/runs/'+encodeURIComponent(r.run_id)+'/results/'+encodeURIComponent(s)),api('/api/instruments/'+encodeURIComponent(s)+'?run_id='+encodeURIComponent(r.run_id))]);
  if(result.symbol!==s||(result.revision||0)!==(r.revision||0)||chart.symbol!==s||chart.run_id!==r.run_id)throw new Error('Saved evidence does not match the selected stock and run.');
  results.set(key,result);history.set(key,chart);
 }catch(e){failures.set(key,e.message);}finally{pending.delete(key);if(activePage==='overview')render();}
}
function refreshData(source){
 if(!attentionRecord||!attentionDirty&&!attentionBusy&&source.attention?.revision>attentionRecord.revision)attentionRecord=source.attention;else if(attentionRecord&&source.attention)attentionRecord.observations=source.attention.observations;
 if(!investorRecord||!investorDirty&&!investorBusy&&source.investor?.revision>investorRecord.revision)investorRecord=source.investor;
 if(investorRecord&&source.investor)investorRecord.instruments=source.investor.instruments;
 const connected=Boolean(source.connection?.connected&&source.account), names=source.company_names||{};
 const research=Object.fromEntries(Object.entries(source.saved_research||source.research||{}).filter(([,r])=>r.run_id&&r.status==='completed').map(([s,r])=>{const key=r.run_id+':'+s+':'+(r.revision||0);return [s,{...r,...results.get(key)}];}));
 DATA={name:source.config.name,captured_at:new Date().toISOString(),account:connected?source.account:{},account_observed_at:source.updated_at,prices_checked_at:source.quotes_updated_at,connected,market_open:source.clock?.is_open,
  positions_count:connected&&source.broker_observation?.positions_complete===true?source.positions?.length:null,open_orders_count:connected&&source.broker_observation?.orders_complete===true?source.open_orders?.length:null,research,history:{},
  holdings:Array.isArray(source.positions)?source.positions:[],holdings_available:connected&&Array.isArray(source.positions)&&source.broker_observation?.positions_complete===true,connection_message:source.connection?.message,reconciliation:source.reconciliation||{status:'pending'},fills:source.fills||[],orders:source.orders||[],
  stocks:source.config.universe.map(s=>{const q=source.nautilus?.market_data?.[s]?.quote;return {symbol:s,company:names[s]||s,quote:source.quotes?.[s]||{},bid:q?.bid_price,ask:q?.ask_price,quote_event_ns:q?.ts_event};})};
 for(const s of Object.keys(research)){const saved=history.get(cacheKey(s));if(saved)DATA.history[s]=saved;}
 DATA.held_stocks=DATA.holdings.map(p=>{const q=source.nautilus?.market_data?.[p.symbol]?.quote;return {symbol:p.symbol,company:names[p.symbol]||p.symbol,quote:source.quotes?.[p.symbol]||{error:'Current holding quote unavailable'},bid:q?.bid_price,ask:q?.ask_price,quote_event_ns:q?.ts_event,owned:true,limitation:p.import_error};});
 const valid=new Set([...DATA.stocks,...DATA.held_stocks].map(s=>s.symbol));for(const s of selectedSymbols)if(!valid.has(s))selectedSymbols.delete(s);
 if(!restored){restoreWatchlists();adoptWorkspace(source.workspace,true);restored=true;}else adoptWorkspace(source.workspace);
 if(detailOpen&&marketModes.get(symbol)==='current')queueMicrotask(()=>loadCurrentHistory(symbol,marketForm(symbol).key));
 if(detailOpen)queueMicrotask(()=>loadStockEvidence(symbol));
}
function bind(){
 const container=document.getElementById('universe-review');if(!container||container.dataset.bound)return;container.dataset.bound='1';
 $('stock-search').value=search;
 const nameInput=$('watchlist-name');nameInput.value=watchlistName;if(!nameInput.dataset.bound){nameInput.dataset.bound='1';nameInput.addEventListener('input',e=>{watchlistName=e.target.value;renderSelection(filteredRows());});}
 $('universe-size').textContent=DATA.stocks.length;
 $('account-connection-label').textContent=stateErrorMessage?'Last known account · refresh failed':DATA.connected?'Connected account':'Account unavailable';
 $('balances').innerHTML=[['cash','Cash'],['equity','Equity'],['buying_power','Buying power'],['long_market_value','Long market value']].map(([key,label])=>'<div class="balance"><span>'+label+' · USD</span><strong>'+money(DATA.account[key])+'</strong></div>').join('')+'<div class="balance"><span>Positions / open orders</span><strong>'+(DATA.positions_count??'Unavailable')+' / '+(DATA.open_orders_count??'Unavailable')+'</strong></div>';
 $('snapshot-status').innerHTML='<b>'+(stateErrorMessage?'Connection unconfirmed · showing last snapshot':DATA.connected?'Nautilus connected':'Nautilus disconnected · balances unavailable')+'</b><span>Account observed '+fullTime(DATA.account_observed_at)+'</span><span>Prices checked '+fullTime(DATA.prices_checked_at)+'</span><span>Market '+(DATA.market_open===true?'open':DATA.market_open===false?'closed':'unknown')+'</span><strong>'+DATA.stocks.filter(s=>s.quote.price==null).length+' prices missing · '+DATA.stocks.filter(s=>liveQuoteState(s.quote)==='stale').length+' prices stale / '+DATA.stocks.length+' stocks</strong>';
 $('snapshot-status').insertAdjacentHTML('beforeend','<span>Account import '+esc(DATA.reconciliation.status||'pending')+'</span>');
 $('provenance').innerHTML='<p>Account and latest available prices come from the existing Nautilus runtime. Native import supports the documented USD CASH equity slice; unsupported records remain visible with reconciliation gaps. Broker cost basis and market value remain source reported.</p><p>Price age uses the provider event time and advances independently of the quote-check timestamp. Native IEX snapshots are polled; this is not a full tick stream.</p><p>Charts and reports are dated saved research inputs. Missing history is not fetched or estimated. Company names are shown only when present in the existing local constituent file.</p><p>Named watchlists, preferences and investor notes are stored by the app. Minimum movement means absolute change greater than or equal to the threshold; missing change is retained when the minimum is zero. Watchlists do not select stocks for research, create drafts or authorize trades. <a href="#settings">Edit the configured universe</a>.</p>';
 renderTable();renderColumns();showPortfolio();workspaceStatus();bindInvestor();
 $('table-scroll').scrollTop=tableScroll[0];$('table-scroll').scrollLeft=tableScroll[1];
 if(detailOpen){$('stock-detail').hidden=false;$('workspace').classList.add('detail-open');$('detail-title').textContent=symbol+' / Stock review';$('detail-content').innerHTML=evidence()+research();$('detail-content').scrollTop=detailScroll;Array.from($('detail-content').children).forEach((panel,i)=>panel.scrollTop=paneScroll[i]||0);bindReport();}
 for(const id of disclosureViews.get(activePage+':'+selectedSymbol)||[]){const detail=document.getElementById(id);if(detail?.tagName==='DETAILS')detail.open=true;}
 $('stock-search').addEventListener('input',e=>{search=e.target.value.trim().toLowerCase();$('feedback').textContent='';renderTable(true);});
$('universe-views').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(b){view=b.dataset.view;$('feedback').textContent='';renderTable(true);}});
$('sort-by').addEventListener('change',e=>{sortKey=e.target.value;renderTable(true);});
$('sort-direction').addEventListener('click',()=>{descending=!descending;renderTable(true);});
$('universe-table').querySelector('thead').addEventListener('click',e=>{const b=e.target.closest('[data-sort]');if(b){descending=sortKey===b.dataset.sort?!descending:false;sortKey=b.dataset.sort;renderTable(true);}});
$('clear-filters').addEventListener('click',()=>{search='';view='all';activeListId='';minMove=0;sortKey='symbol';descending=false;$('stock-search').value='';persistShortlist();$('feedback').textContent='Filters cleared. All configured stocks are shown; saved watchlists are retained.';renderTable(true);});
$('min-move').addEventListener('change',e=>{minMove=Number(e.target.value);renderTable(true);});
$('watchlist-select').addEventListener('change',e=>{activeListId=e.target.value;targetListId=activeListId||'shortlist';selectedSymbols.clear();persistShortlist();renderTable(true);$('feedback').textContent='Watchlist changed. Bulk selection cleared.';});
$('watchlist-target').addEventListener('change',e=>{targetListId=e.target.value;persistShortlist();renderSelection(filteredRows());});
$('create-watchlist').addEventListener('click',createWatchlist);
$('select-filtered').addEventListener('click',()=>{filteredRows().forEach(s=>selectedSymbols.add(s.symbol));renderTable();});
$('universe-table').querySelector('thead').addEventListener('change',e=>{if(e.target.id==='select-all'){filteredRows().forEach(s=>e.target.checked?selectedSymbols.add(s.symbol):selectedSymbols.delete(s.symbol));renderTable();}});
$('clear-selection').addEventListener('click',()=>{selectedSymbols.clear();renderTable();});
$('stock-rows').addEventListener('change',e=>{const s=e.target.dataset.select;if(s){e.target.checked?selectedSymbols.add(s):selectedSymbols.delete(s);renderSelection(filteredRows());}});
$('stock-rows').addEventListener('click',e=>{const b=e.target.closest('[data-stock]');if(b)openStock(b.dataset.stock,b);});
$('add-shortlist').addEventListener('click',()=>bulkShortlist(true));$('remove-shortlist').addEventListener('click',()=>bulkShortlist(false));$('close-detail').addEventListener('click',closeStock);
container.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('stock-detail').hidden)closeStock();});

 container.addEventListener('click',async e=>{if(e.target.id==='ur-retry-detail')loadDetail(symbol);if(e.target.id==='export-selected-holdings'){try{const record=await api('/api/reporting');const result=await api('/api/reporting',{action:'export_csv',kind:'holdings',symbols:[...selectedSymbols],expected_revision:record.revision});download(result.csv,result.filename,'text/csv;charset=utf-8');}catch(error){$('feedback').textContent=error.message;}}});
 $('holdings-body').addEventListener('click',e=>{const button=e.target.closest('[data-stock]');if(button)openStock(button.dataset.stock,button);});
 $('holdings-body').addEventListener('input',e=>{if(e.target.id==='holdings-query'){holdingsQuery=e.target.value;persistPreferences();render();}});
 $('holdings-body').addEventListener('change',e=>{if(e.target.id==='holdings-sort')holdingsSort=e.target.value;else if(e.target.id==='holdings-filter')holdingsFilter=e.target.value;else return;persistPreferences();render();});
 $('holdings-body').addEventListener('click',e=>{if(e.target.id==='holdings-direction'){holdingsDescending=!holdingsDescending;persistPreferences();render();}});
 for(const name of ['holdings','universe'])$('show-'+name).addEventListener('click',()=>{portfolioView=name;detailOpen=false;$('stock-detail').hidden=true;$('workspace').classList.remove('detail-open');showPortfolio();persistPreferences();});
 $('column-picker').addEventListener('toggle',e=>{columnsOpen=e.target.open;});
 $('column-options').addEventListener('change',e=>{const key=e.target.dataset.column;if(!key)return;e.target.checked?visibleColumns.add(key):visibleColumns.delete(key);persistColumns();renderTable();});
 $('column-options').addEventListener('click',e=>{const button=e.target.closest('[data-column-move]');if(!button)return;const i=columnOrder.indexOf(button.dataset.columnMove),j=i+Number(button.dataset.step);if(j<0||j>=columnOrder.length)return;[columnOrder[i],columnOrder[j]]=[columnOrder[j],columnOrder[i]];persistColumns();renderColumns();renderTable();$('column-'+button.dataset.columnMove).focus();});
 $('reset-columns').addEventListener('click',()=>{columnOrder=COLUMN_OPTIONS.map(c=>c.key);visibleColumns=new Set(['price','change','age','research']);persistColumns();renderColumns();renderTable();});
}
function liveView(source){
 const oldTable=$('table-scroll');
 if(!oldTable)tableScroll=[0,0];
 else if($('universe-review')?.dataset.bound)tableScroll=[oldTable.scrollTop,oldTable.scrollLeft];
 if($('detail-content'))paneScroll=Array.from($('detail-content').children).map(panel=>panel.scrollTop);
 detailScroll=$('detail-content')?.scrollTop??detailScroll;refreshData(source);requestAnimationFrame(bind);
 return "<div id=\"universe-review\">\n<header class=\"app-header\"><div class=\"header-row\"><div><h1>TradingAgents / Universe review</h1><div class=\"muted\"><span id=\"account-connection-label\">Account connection pending</span> \u00b7 <span id=\"universe-size\">\u2026</span> stocks</div></div><div class=\"balances\" id=\"balances\" aria-label=\"Nautilus account\"></div></div><div class=\"snapshot-strip\" id=\"snapshot-status\" role=\"status\">Reading Nautilus account and configured universe\u2026</div><nav class=\"portfolio-tabs\" aria-label=\"Portfolio views\"><button id=\"show-holdings\" aria-pressed=\"false\">Holdings</button><button id=\"show-universe\" aria-pressed=\"true\">Stock universe</button></nav></header>\n<div id=\"workspace-save-status\" class=\"feedback\" role=\"status\" aria-live=\"polite\"></div><main class=\"workspace\" id=\"workspace\">\n<section id=\"holdings-view\" aria-label=\"Account holdings\" hidden><h2>Account holdings</h2><div id=\"holdings-body\"></div></section><section id=\"universe-view\" class=\"universe\" aria-label=\"Stock universe\">\n<div class=\"section-heading\"><h2>Scan the universe. Manage your watchlists.</h2><p>Watchlists and notes are saved by the app. Order submission requires your exact approval and explicit command action.</p></div>\n<nav class=\"view-tabs\" id=\"universe-views\" aria-label=\"Universe views\"></nav>\n<div class=\"filters\"><label class=\"search-control\" for=\"stock-search\">Search symbol or company<input type=\"search\" id=\"stock-search\" placeholder=\"Ticker or company\u2026\" autocomplete=\"off\"></label><label for=\"min-move\">Min |change| \u2265<select id=\"min-move\"><option value=\"0\">0% \u00b7 no minimum</option><option value=\"0.5\">0.5%</option><option value=\"1\">1%</option><option value=\"2\">2%</option><option value=\"3\">3%</option><option value=\"5\">5%</option></select></label><label for=\"sort-by\">Sort by<select id=\"sort-by\"><option value=\"symbol\">Symbol</option><option value=\"company\">Company</option><option value=\"price\">Price</option><option value=\"change\">Change %</option><option value=\"magnitude\">Move size %</option><option value=\"age\">Price age</option><option value=\"date\">Research date</option><option value=\"rating\">Saved rating</option></select></label><button id=\"sort-direction\" aria-label=\"Sort descending\">Ascending \u2191</button><button id=\"clear-filters\">Clear filters</button></div>\n<div class=\"filters watchlist-controls\"><label for=\"watchlist-select\">View watchlist<select id=\"watchlist-select\"></select></label><label class=\"search-control\" for=\"watchlist-name\">New watchlist name<input type=\"text\" id=\"watchlist-name\" maxlength=\"60\" placeholder=\"Name this selection\" autocomplete=\"off\"></label><button id=\"create-watchlist\" disabled>Create from selected</button></div><div class=\"bulk-toolbar\"><span class=\"selection-count\" id=\"selection-count\">0 selected</span><button id=\"select-filtered\">Select all filtered</button><button id=\"clear-selection\" disabled>Clear selection</button><button id=\"export-selected-holdings\" disabled>Export selected observed holdings CSV</button><label for=\"watchlist-target\">Edit list <select id=\"watchlist-target\"></select></label><button id=\"add-shortlist\" disabled>Add to shortlist</button><button id=\"remove-shortlist\" disabled>Remove from shortlist</button></div>\n<details id=\"column-picker\" class=\"column-picker\"><summary>Manage universe columns</summary><p id=\"column-note\" class=\"muted\"></p><div id=\"column-options\" class=\"column-options\"></div><button id=\"reset-columns\" type=\"button\">Reset default columns</button></details><div class=\"view-status\"><span id=\"result-count\" role=\"status\"></span><span>View counts reflect search \u00b7 price timestamps identify market events</span></div><div class=\"feedback\" id=\"feedback\" role=\"status\" aria-live=\"polite\"></div>\n<div class=\"table-scroll\" id=\"table-scroll\" tabindex=\"0\" aria-label=\"Configured stock universe\"><table id=\"universe-table\"><thead><tr id=\"universe-head\"></tr></thead><tbody id=\"stock-rows\"></tbody></table></div>\n<div class=\"universe-foot\"><p id=\"shortlist-storage\">Named watchlists are saved by the app and restored on reload. They do not start research or change broker orders.</p><details><summary>Snapshot provenance and data boundaries</summary><div id=\"provenance\"></div></details></div>\n</section>\n<aside class=\"detail\" id=\"stock-detail\" aria-label=\"Selected stock review\" hidden><div class=\"detail-header\"><h2 id=\"detail-title\">Stock review</h2><button id=\"close-detail\">Back to universe</button></div><div class=\"detail-content\" id=\"detail-content\"></div></aside>\n</main>\n</div>".replace(/<\/div>$/,policyPanel()+basketPanel()+attentionPanel()+'</div>');
}
return {render:liveView,openProposal(s,trigger,context,proposalId){if(proposalId){const item=state.investor?.data.proposals.find(p=>p.id===proposalId);if(item){proposalForms.set(s,{...item.terms,id:item.id});proposalPreviews.set(s,item);}}openStock(s,trigger,context);},generationChanged(){researchOrigin=null;workspaceConflict=true;workspaceError='Application records were restored. Reload saved workspace to reconcile or discard unsaved edits.';investorConflict=true;investorError='Application records were restored. Reload saved investor records before saving.';attentionConflict=true;attentionError='Application records were restored. Reload saved attention records before saving.';results.clear();history.clear();currentHistory.clear();currentHistoryVersions.clear();supplementaryCache.clear();supplementaryVersions.clear();},resetAfterRestore(){researchOrigin=null;restored=false;attentionRecord=null;attentionDirty=false;attentionConflict=false;attentionError='';reviewDrafts.clear();currentHistory.clear();currentHistoryVersions.clear();supplementaryCache.clear();supplementaryVersions.clear();workspaceChanges={};workspaceConflict=false;workspaceError='';noteDrafts.clear();investorRecord=null;investorDirty=false;investorConflict=false;investorError='';policyDraft=null;proposalForms.clear();proposalPreviews.clear();basketForm={targets:[],reason:'',fee_per_leg:'',slippage_bps:'',assumed_filled:[]};basketPreview=null;results.clear();history.clear();failures.clear();}};

})();

window.addEventListener('focus',()=>{if(!document.hidden)readState();});
window.addEventListener('online',()=>readState({force:true}));
window.addEventListener('offline',()=>{stateErrorMessage='Browser connection is offline. Displayed observations retain their original source times.';renderNotice();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)readState();});


function decisionOutcomeMarkup(item){
 const links=(item.decision_links||[]).map(id=>'<button class="link-button" data-journal-decision="'+esc(id)+'">'+esc(id)+'</button>').join(' · ');
 return '<p>'+links+'</p>'+(item.command_outcomes||[]).map(c=>'<article><h3>Command '+esc(c.command_id)+'</h3><p>Broker outcome: '+esc(c.broker_outcome)+' · filled '+esc(c.filled_quantity)+' · native application: '+esc(c.native_application)+'</p>'+commandReceiptLinks(c)+'<p>Broker IDs '+esc(c.broker_order_ids.join(', ')||'None recorded')+' · fills '+esc(c.fill_ids.join(', ')||'None recorded')+'</p><details><summary>Command approval, exact terms, broker receipts and historical native receipts</summary><pre>'+esc(JSON.stringify(c,null,2))+'</pre></details></article>').join('')+(item.execution_plans?.length?'<details><summary>Non-atomic basket completion and paused legs</summary><pre>'+esc(JSON.stringify(item.execution_plans,null,2))+'</pre></details>':'');
}


function commandReceiptLinks(command){
 const found=new Map();
 function walk(value){if(!value||typeof value!=='object')return;if(value.path&&/^[0-9a-f]{64}$/.test(value.sha256||''))found.set(value.sha256,value.path);for(const child of Object.values(value))if(child&&typeof child==='object')walk(child);}
 walk(command.native_receipts);walk(command.timeline);
 return [...found].map(([sha,path])=>'<p><a href="/api/commands/'+encodeURIComponent(command.command_id)+'/receipts/'+sha+'" target="_blank" rel="noopener">Open saved receipt '+esc(path)+'</a> · SHA-256 '+esc(sha)+'</p>').join('');
}
