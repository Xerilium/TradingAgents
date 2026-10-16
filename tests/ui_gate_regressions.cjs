// Offline acceptance tests for T-1.2--T-1.5. No packages, browser, or network.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..', 'tradingagents', 'web', 'static');

function fixture() {
  const handlers = {document:{},window:{}};
  const fields = new Map(), nodes = new Map();
  const register = scope => (name, fn) => (handlers[scope][name] ||= []).push(fn);
  function node(id='') {
    return {id, dataset:{}, tagName:'DIV', value:'', scrollTop:0, scrollLeft:0,
      addEventListener(){}, querySelectorAll(){return [];}, querySelector(s){return query(s);},
      classList:{contains(){return false;},toggle(){}}, focus(){}, setAttribute(){},
      getAttribute(){return null;}, insertAdjacentHTML(){}, closest(){return null;}};
  }
  const main = node('main');
  let html='';
  Object.defineProperty(main,'innerHTML',{get(){return html;},set(value){
    html=value;fields.clear();
    for(const m of value.matchAll(/<(input|textarea)\b([^>]*)(?:>([^<]*)<\/textarea>)?/g)) {
      const id=/\bid="([^"]+)"/.exec(m[2])?.[1], name=/\bname="([^"]+)"/.exec(m[2])?.[1];
      if(!id||!name)continue;
      const el=node(id);el.name=name;el.tagName=m[1].toUpperCase();el.value=m[1]==='textarea'?m[3]||'':/\bvalue="([^"]*)"/.exec(m[2])?.[1]||'';
      el.closest=s=>s==='#settings-form'?query(s):null;fields.set(id,el);
    }
  }});
  nodes.set('#main',main);
  function query(s){if(fields.has(s.slice(1)))return fields.get(s.slice(1));if(!nodes.has(s))nodes.set(s,node(s.slice(1)));return nodes.get(s);}
  const context=vm.createContext({console,Intl,URL,AbortController,Date,
    location:{hash:'#overview'},localStorage:{getItem(){return null;},setItem(){}},
    document:{hidden:false,activeElement:null,addEventListener:register('document'),querySelector:query,querySelectorAll(){return [];},getElementById:id=>fields.get(id)||null},
    window:{addEventListener:register('window'),scrollTo(){}},setInterval(){},setTimeout(){},clearTimeout(){},
    fetch(){throw Error('Network forbidden in UI regression fixture');},
    FormData:class {constructor(){this.values=[...fields.values()].map(e=>[e.name,e.value]);} [Symbol.iterator](){return this.values[Symbol.iterator]();}},
    confirm(){return false;}});
  vm.runInContext(fs.readFileSync(path.join(root,'lists.js'),'utf8'),context);
  const source=fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/^readState\(\);\r?$/m,'');
  vm.runInContext(source,context);
  const run=code=>vm.runInContext(code,context);
  run(`state={config:{name:'FANGMAN',universe:['AAPL','META'],allocation_pct:80,max_position_pct:20,reserve_pct:20,max_order_notional:1000,llm_provider:'chatgpt',backend_url:'',deep_think_llm:'deep',quick_think_llm:'quick'},connection:{connected:false,paper_verified:false},quotes:{},proposals:[],orders:[],positions:[],runs:[],research:{}};
    renderChrome=()=>{};renderNotice=()=>{};observeChartSize=()=>{};ensureChart=()=>{};ensureResultDetail=()=>{};`);
  return {run,main,fields,context, async event(scope,name,target={}){for(const fn of handlers[scope][name]||[])await fn({target,preventDefault(){}});}};
}
const opened = html => [...html.matchAll(/<details\b([^>]*)>/g)].filter(m=>/class="report-section"/.test(m[1])&&/\sopen(?:\s|$|=)/.test(m[1])).map(m=>/data-report="([^"]+)"/.exec(m[1])[1]);
test('historical choice assessments retain meanings, version, and original labels',()=>{
  const f=fixture();const html=f.run(`reportLaya({question_contract_version:'research-choice-v1',contract:{grade:'auto_execute'},answers:{evidence_complete:{value:'A'},decision_consistent:{value:'B'}}})`);
  assert.match(html,/research-choice-v1/);assert.match(html,/Essential evidence supports assessment/);
  assert.match(html,/Rating is unsupported or disregards restrictions/);assert.match(html,/>A</);assert.match(html,/>B</);
});

test('unclear social stance shows raw prediction and grade without rewriting historical counts',()=>{
  const f=fixture();const html=f.run(`reportSocial({sources:{reddit:{admission_version:'stance-contract-v1',counts:{unclear:1},posts:[{status:'classified',stance:'unclear',raw_prediction:'bearish',stance_grade:'reconsider',stance_probability:.8475}]}}})`);
  assert.match(html,/>Unclear</);assert.match(html,/Raw prediction/);assert.match(html,/bearish/);assert.match(html,/Stance grade/);assert.match(html,/reconsider/);
  assert.doesNotMatch(html,/Historical screening/);
  const old=f.run(`reportSocial({sources:{reddit:{counts:{bearish:11},posts:[{stance:'bearish',result:{answers:{stance:{grade:'reconsider'}}}}]}}})`);
  assert.match(old,/Historical screening/);assert.match(old,/>11</);assert.match(old,/Original evidence is preserved/);
});

test('retired Laya proposal blockers show historical label and creation time',()=>{
  const f=fixture();f.run(`state.proposals=[{id:'old',symbol:'META',status:'blocked',reason:'Laya has not authorized automatic execution',created_at:'2026-10-15T00:00:00Z'}];`);
  const html=f.run('renderOrders()');assert.match(html,/Historical · retired Laya check/);assert.match(html,/2026/);
  assert.match(html,/Laya has not authorized automatic execution/);
});

test('order preview explains policy sizing and links the exact associated research',async()=>{
  const f=fixture();f.run(`$('#order-dialog').showModal=()=>{};$('#order-dialog').close=()=>{};state.proposals=[{id:'new',run_id:'original-run',symbol:'META',status:'proposed',side:'buy',qty:5,limit_price:100,notional:500}];previewOrder('new');`);
  const html=f.run(`$('#order-preview').innerHTML`);assert.match(html,/configured allocation policy/);assert.match(html,/Research commentary is advisory/);assert.match(html,/Review associated research/);
  await f.event('document','click',{closest(){return {dataset:{action:'inspect-proposal',proposal:'new'}};}});
  assert.equal(f.run('selectedRunId'),'original-run');assert.equal(f.run('selectedSymbol'),'META');
});
test('T-1.10 historical approval is retired and cannot label stocks cleared',()=>{
  const f=fixture();const html=f.run(`reportLaya({contract:{grade:'auto_execute'},answers:{evidence_complete:{value:true},decision_consistent:{value:true}}})`);
  assert.match(html,/retired/);assert.doesNotMatch(html,/fresh research is required/);
  f.run(`state.research={AAPL:{status:'completed',laya:{auto_execute:true,grade:'auto_execute'}},META:{status:'completed',laya:{auto_execute:true,grade:'auto_execute',question_contract_version:'research-choice-v1'}}};listViews.watch.filter='cleared';`);
  assert.equal(f.run('reviewLabel(state.research.AAPL)'),'Social screening not recorded');
  assert.doesNotMatch(f.run('watchlist()'),/Laya cleared|Laya review required|Legacy review|Review required/);
});
test('T-1.10 social evidence separates unavailable from neutral and preserves posts',()=>{
  const f=fixture();const html=f.run(`renderReports({reports:{},social_sentiment:{status:'partial',model:'multilingual',sources:{reddit:{status:'partial',counts:{bullish:1,bearish:0,neutral:0,unclear:1,off_topic:0,unscreened:2},note:'Time budget reached',posts:[{text:'<script>post</script>',text_sha256:'hash123',provenance:'Reddit excerpt',status:'classified',stance:'bullish',stance_probability:0.91}]}}}})`);
  for(const label of ['Laya social sentiment','Unscreened','Unclear','Neutral','Time budget reached','Reddit excerpt','hash123','does not approve trades'])assert.ok(html.includes(label),label);
  assert.match(html,/&lt;script&gt;post/);assert.doesNotMatch(html,/<script>/);assert.deepEqual(opened(html),[]);
  assert.equal(f.run(`reviewLabel({status:'completed',social_sentiment:{status:'unavailable',sources:{}}})`),'Social screening unavailable');
});
function disclosure(name,open){return {dataset:{report:name},open,isConnected:true,matches:s=>s==='.report-section'};}

test('T-1.2 disconnected quote control is disabled with recovery, or gives actionable feedback',async()=>{
  const f=fixture(); const html=f.run('watchlist()');
  const button=/<button\b[^>]*data-action="refresh-quotes"[^>]*>/.exec(html)?.[0]||'';
  assert.match(html,/data-action="refresh-source">Refresh connection/,'Recovery must use the broker reconnect operation, not only reread cached state');
  await f.run('refreshQuotes({manual:true})');
  const feedback=f.run('errorMessage');
  assert.ok((/\bdisabled\b/.test(button)&&/disconnect|connect|unavailable|settings|retry/i.test(html.replace(/Edit index/g,'')))||/connect|disconnect|retry|settings/i.test(feedback),'Disconnected click must not silently do nothing');
});
test('T-1.2 recovery permits one mocked refresh and only success changes checked timestamp',async()=>{
  const f=fixture();f.run(`render=()=>{};state.connection.connected=true;state.quotes_updated_at='old';globalThis.calls=0;api=async()=>{calls++;return {quotes:{},clock:{is_open:false},quotes_updated_at:'success'};};`);
  await f.run('refreshQuotes({manual:true})');assert.equal(f.run('calls'),1);assert.equal(f.run('state.quotes_updated_at'),'success');
  f.run(`api=async()=>{throw Error('offline');};setError=m=>errorMessage=m;`);
  await f.run('refreshQuotes({manual:true})');assert.equal(f.run('state.quotes_updated_at'),'success');
});
test('T-1.3 filtered proposals offer Clear filters without instructing new research',()=>{
  const f=fixture();f.run(`state.proposals=[{id:'p1',symbol:'AAPL',status:'ready'}];listViews.proposals.query='ZZZZ';`);
  const html=f.run('renderOrders()');
  assert.ok(/Clear (?:filters|search)/i.test(html),'Filtered-empty proposals need a clear-filters recovery control');assert.ok(!/Complete a research run/.test(html),'Filtered-empty proposals must not instruct new research');
});
test('T-1.3 truly empty proposals explain research prerequisites',()=>{
  const f=fixture();const html=f.run('renderOrders()');assert.match(html,/No proposals yet/);assert.match(html,/research run/);
});
test('T-1.4 all settings draft fields survive background refresh and navigation, or navigation is cancelled',async()=>{
  const f=fixture();f.run(`activePage='settings';render();`);
  const expected={name:'Unsaved desk',universe:'META, NVDA',allocation_pct:'70',max_position_pct:'15',reserve_pct:'25',max_order_notional:'1234',llm_provider:'test-provider',backend_url:'https://example.invalid/v1',deep_think_llm:'draft-deep',quick_think_llm:'draft-quick'};
  for(const [key,value]of Object.entries(expected)){const el=f.fields.get('config-'+key);assert.ok(el,key);el.value=value;await f.event('document','input',el);}
  f.run(`state.config.name='Server changed';render();`);
  assert.equal(f.fields.get('config-name').value,expected.name,'Background updates must not replace edits');
  f.context.location.hash='#overview';await f.event('window','hashchange');
  f.context.location.hash='#settings';await f.event('window','hashchange');
  for(const [key,value]of Object.entries(expected))assert.equal(f.fields.get('config-'+key)?.value,value,'Lost draft field '+key);
});
test('T-1.5 first report arrives collapsed',()=>{const f=fixture();assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'First'}})`)),[]);});
test('T-1.5 final Laya-only report arrives collapsed',()=>{const f=fixture();assert.deepEqual(opened(f.run(`renderReports({reports:{},laya:{grade:'ask_human'}})`)),[]);});
test('T-1.5 sequential final report/Laya arrival preserves explicit open choice',async()=>{
  const f=fixture();await f.event('document','toggle',disclosure('market_report',true));
  const html=f.run(`renderReports({reports:{market_report:'Updated',final_trade_decision:'Last analyst result'},laya:{grade:'ask_human'}})`);
  assert.deepEqual(opened(html),['market_report']);assert.match(html,/Full source artifact/);assert.match(html,/<summary[^>]*>Historical Laya research check/);
});
test('T-1.5 collapse-all stays collapsed after rerender and later arrival',async()=>{
  const f=fixture();await f.event('document','toggle',disclosure('market_report',true));await f.event('document','toggle',disclosure('market_report',false));
  assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'Updated',final_trade_decision:'Decision'},laya:{grade:'ask_human'}})`)),[]);
});
test('T-1.5 selecting another stock does not expand reports',()=>{
  const f=fixture();f.run(`render=()=>{};activePage='research';openReportNames.add('market_report');selectStock('META');`);
  assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'META'}})`)),[]);
});
test('T-1.5 switching run starts new reports collapsed',async()=>{
  const f=fixture();f.run(`render=()=>{};readState=async()=>{};state.runs=[{id:'run2',symbols:['AAPL']}];openReportNames.add('market_report');`);
  await f.event('document','change',{id:'run-select',value:'run2',dataset:{},classList:{contains(){return false;}}});
  assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'Different run'}})`)),[]);
});
test('T-1.5 queued toggle from replaced DOM must not open a report in new selection',async()=>{
  const f=fixture();const detached=disclosure('market_report',true);detached.isConnected=false;
  await f.event('document','toggle',detached);
  assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'New view',news_report:'News'}})`)),[]);
});

function actionTarget(action){return {dataset:{action},closest(s){return s==='[data-action]'?this:null;}};}
test('T-1.3 clear filters activates locally and restores all four proposals',async()=>{
  const f=fixture();f.run(`activePage='orders';state.proposals=Array.from({length:4},(_,i)=>({id:'p'+i,symbol:'AAPL',status:'ready'}));Object.assign(listViews.proposals,{query:'ZZZZ',filter:'blocked',page:3});render();`);
  await f.event('document','click',actionTarget('clear-proposal-filters'));
  assert.equal(f.run('listViews.proposals.query'),'');assert.equal(f.run('listViews.proposals.filter'),'all');assert.equal(f.run('listViews.proposals.page'),0);
  assert.equal((f.main.innerHTML.match(/data-proposal=/g)||[]).length,4);
});
test('T-1.4 explicit discard and reset-universe use complete draft',async()=>{
  const f=fixture();f.run(`activePage='settings';render();`);
  f.fields.get('config-name').value='Draft';await f.event('document','input',f.fields.get('config-name'));
  await f.event('document','click',actionTarget('reset-universe'));
  assert.equal(f.run('settingsDraft.universe'),'META, AAPL, NVDA, GOOGL, MSFT, AMZN, NFLX');
  await f.event('document','click',actionTarget('discard-settings'));
  assert.equal(f.fields.get('config-name').value,'FANGMAN');assert.equal(f.run('settingsDraft'),null);assert.equal(f.run('settingsDirty'),false);
});
test('T-1.4 save failure retains draft and successful save clears it',async()=>{
  const f=fixture();f.run(`activePage='settings';render();act=async()=>{throw Error('fixture failure')};`);
  f.fields.get('config-name').value='Draft';await f.event('document','input',f.fields.get('config-name'));
  await f.event('document','submit',{id:'settings-form'});assert.equal(f.run('settingsDraft.name'),'Draft');assert.equal(f.run('settingsDirty'),true);
  f.run(`act=async(key,path,c)=>{state.config=c;};`);await f.event('document','submit',{id:'settings-form'});
  assert.equal(f.run('settingsDraft'),null);assert.equal(f.run('settingsDirty'),false);assert.equal(f.fields.get('config-name').value,'Draft');
});
test('T-1.5 returning to a view restores only its explicit choices',async()=>{
  const f=fixture();f.run(`activePage='research';selectedSymbol='AAPL';syncReportView();render=()=>{};`);
  await f.event('document','toggle',disclosure('market_report',true));f.run(`selectStock('META');`);
  assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'META'}})`)),[]);
  f.run(`selectStock('AAPL');`);assert.deepEqual(opened(f.run(`renderReports({reports:{market_report:'AAPL'}})`)),['market_report']);
});
test('T-1.1 review evidence exposes actual summary model and token budget collapsed',()=>{
  const f=fixture();const html=f.run(`renderReports({laya_review:{parameters:{state:{summary:'Exact review input'},model:'laya-model'},token_budget:4096}})`);
  assert.match(html,/Exact review input/);assert.match(html,/laya-model/);assert.match(html,/4096/);assert.deepEqual(opened(html),[]);
});
test('T-1.1 structured Laya audit renders summary and per-question budget without object coercion or duplicate preview',()=>{
  const audit={parameters:{state:{evidence_basis:'Summary of research; not the complete source packet.',source_sha256:'fixture-sha',summary:{recommendation:'Overweight',supporting_evidence:'Measured support',counterarguments:'Material counterargument',unresolved_gaps:'Unresolved evidence gap',execution_conditions:'Fresh quote required',source_references:'Original source report'}},model:'multilingual',questions:{evidence_complete:{kind:'yes_no'},decision_consistent:{kind:'yes_no'}},threshold:'high'},token_budget:{model:'multilingual',max_tokens:8192,effective_max_tokens:8192,state_complete:true,questions_complete:true,sequence_tokens:{evidence_complete:2673,decision_consistent:2677},sequence_sha256:{evidence_complete:'first-hash',decision_consistent:'second-hash'}},reserve_tokens:256,summary_attempts:1};
  const f=fixture();f.context.audit=audit;const html=f.run('renderReports({laya_review:audit})');
  const preview=html.split('<details class="report-raw"')[0];
  assert.doesNotMatch(html,/\[object Object\]/);
  for(const label of ['Model','Effective token cap','Model token cap','Reserved tokens','Summary attempts','Full input tokens per question','Evidence complete','Decision consistent','Supporting evidence','Counterarguments','Unresolved gaps','Execution conditions','Source references'])assert.ok(preview.includes(label),label);
  for(const value of ['multilingual','8192','256','2673','2677','Overweight'])assert.ok(preview.includes(value),value);
  assert.equal((preview.match(/Measured support/g)||[]).length,1,'Summary must appear once in preview');
  assert.match(html,/first-hash/,'Exact token audit remains in full source artifact');assert.match(html,/fixture-sha/,'Source fingerprint remains in full source artifact');
  assert.deepEqual(opened(html),[]);
});
test('T-1.4 imported CSV is captured as a draft across navigation',async()=>{
  const f=fixture();f.run(`activePage='settings';render();`);
  await f.event('document','change',{id:'index-file',dataset:{},classList:{contains(){return false;}},files:[{size:30,text:async()=> 'Symbol\nMETA\nNVDA\nMETA'}]});
  assert.equal(f.run('settingsDraft.universe'),'META, NVDA');
  f.context.location.hash='#orders';await f.event('window','hashchange');f.context.location.hash='#settings';await f.event('window','hashchange');
  assert.equal(f.fields.get('config-universe').value,'META, NVDA');
});
