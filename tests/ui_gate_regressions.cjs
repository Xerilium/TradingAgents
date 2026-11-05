// Offline acceptance tests for T-1.2--T-1.5. No packages, browser, or network.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..', 'tradingagents', 'web', 'static');

function fixture(storage = new Map()) {
  const handlers = {document:{},window:{}};
  const fields = new Map(), nodes = new Map();
  const register = scope => (name, fn) => (handlers[scope][name] ||= []).push(fn);
  function node(id='') {
    return {id, dataset:{}, tagName:'DIV', value:'', scrollTop:0, scrollLeft:0,
      listeners:{}, addEventListener(name,fn){this.listeners[name]=fn;}, append(){}, after(){}, querySelectorAll(){return [];}, querySelector(s){return query(s);},
      classList:{contains(){return false;},toggle(){},add(){}}, focus(){}, setAttribute(){},
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
  const context=vm.createContext({console,Intl,URL,URLSearchParams,AbortController,Date,
    location:{hash:'#overview'},localStorage:{getItem(){return null;},setItem(){}},sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    document:{hidden:false,activeElement:null,addEventListener:register('document'),querySelector:query,querySelectorAll(){return [];},getElementById:id=>fields.get(id)||null},
    window:{addEventListener:register('window'),scrollTo(){}},setInterval(){},setTimeout(){},clearTimeout(){},
    fetch(){throw Error('Network forbidden in UI regression fixture');},
    FormData:class {constructor(){this.values=[...fields.values()].map(e=>[e.name,e.value]);} [Symbol.iterator](){return this.values[Symbol.iterator]();}},
    confirm(){return false;}});
  vm.runInContext(fs.readFileSync(path.join(root,'lists.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(root,'report-format.js'),'utf8'),context);
  const source=fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/^readState\(\);\r?$/m,'');
  vm.runInContext(source,context);
  const run=code=>vm.runInContext(code,context);
  run(`state={config:{name:'FANGMAN',universe:['AAPL','META'],allocation_pct:80,max_position_pct:20,reserve_pct:20,max_order_notional:1000,llm_provider:'chatgpt',backend_url:'',deep_think_llm:'deep',quick_think_llm:'quick'},connection:{connected:false,paper_verified:false},quotes:{},proposals:[],orders:[],positions:[],runs:[],research:{}};
    renderChrome=()=>{};renderNotice=()=>{};observeChartSize=()=>{};ensureChart=()=>{};ensureResultDetail=()=>{};`);
  return {run,main,fields,context, async event(scope,name,target={}){for(const fn of handlers[scope][name]||[])await fn({target,preventDefault(){}});}};
}
test('portfolio prompt uses the server mapping and preserves a complete bundle and conflicting draft',async()=>{
  const f=fixture();
  f.run(`globalThis.sent=null;api=async (path,body)=>{if(body){sent=body;throw Object.assign(Error('conflict'),{status:409});}return path==='/api/workflows'?{active:'Default'}:{name:'Default',revision:'r1',joint_portfolio_file:'prompts/custom.txt',files:{'workflow.yaml':'unchanged','prompts/custom.txt':'original','other.txt':'keep'}};};`);
  await f.run('loadPortfolioPrompt()');
  f.run(`portfolioPrompt.draft='<new prompt>';`);
  await f.run('savePortfolioPrompt()');
  assert.equal(f.run(`sent.files['prompts/custom.txt']`),'<new prompt>');
  assert.equal(f.run(`sent.files['other.txt']`),'keep');
  assert.equal(f.run('sent.revision'),'r1');
  assert.equal(f.run('portfolioPrompt.draft'),'<new prompt>');
  assert.match(f.run('portfolioPrompt.message'),/draft is retained/i);
  assert.match(f.run('portfolioPromptMarkup()'),/&lt;new prompt&gt;/);
});
test('portfolio prompt retains mapping after save and reloads a changed active workflow',async()=>{
  const f=fixture();f.run(`globalThis.active='One';api=async (path,body)=>body?{name:body.name,revision:'r2',files:body.files}:path==='/api/workflows'?{active}:{name:active,revision:'r1',joint_portfolio_file:'custom.txt',files:{'custom.txt':active,'workflow.yaml':'keep'}};`);
  await f.run('loadPortfolioPrompt()');f.run(`portfolioPrompt.draft='edited'`);await f.run('savePortfolioPrompt()');
  assert.equal(f.run('portfolioPrompt.draft'),'edited');assert.equal(f.run('portfolioPrompt.bundle.joint_portfolio_file'),'custom.txt');
  f.run(`active='Two'`);await f.run('loadPortfolioPrompt()');assert.equal(f.run('portfolioPrompt.draft'),'Two');
  f.run(`portfolioPrompt.draft='unsaved';active='Three'`);await f.run('loadPortfolioPrompt()');
  assert.equal(f.run('portfolioPrompt.draft'),'unsaved');assert.match(f.run('portfolioPrompt.message'),/active workflow changed/i);
});
test('portfolio prompt input handler recovers a refresh and reports storage failure',async()=>{
  const storage=new Map(), f=fixture(storage);
  f.run(`portfolioPrompt.bundle={name:'Default',revision:'r1',joint_portfolio_file:'prompt.txt',files:{'prompt.txt':'original'}};portfolioPrompt.draft='original';portfolioPromptChecked=true;settingsTab='Research';updateModelLimits=()=>{};fetchModelLimits=()=>{};bindSettings();`);
  const input=f.context.document.querySelector('#portfolio-prompt');
  input.listeners.input({target:{value:'edited'}});
  const refreshed=fixture(storage);
  assert.equal(refreshed.run('portfolioPrompt.draft'),'edited');
  f.context.sessionStorage.setItem=()=>{throw Error('storage unavailable');};
  input.listeners.input({target:{value:'still here'}});
  assert.equal(f.run('portfolioPrompt.draft'),'still here');
  assert.match(f.run('portfolioPromptMarkup()'),/refresh.*lose|lost.*refresh/i);
  assert.match(f.run('portfolioPrompt.storageError'),/refresh/i);
});
test('portfolio prompt save rejects an active workflow switch and retains draft',async()=>{
  const f=fixture();
  f.run(`portfolioPrompt.bundle={name:'One',revision:'r1',joint_portfolio_file:'prompt.txt',files:{'prompt.txt':'original'}};portfolioPrompt.draft='edited';portfolioPromptChecked=true;settingsTab='Research';updateModelLimits=()=>{};fetchModelLimits=()=>{};api=async(path,body)=>{if(!body)return {active:'One'};if(body.expected_active!=='One')throw Error('missing active precondition');throw Object.assign(Error('Active workflow changed.'),{status:409});};bindSettings();`);
  await f.context.document.querySelector('#portfolio-prompt-save').listeners.click();
  assert.equal(f.run('portfolioPrompt.draft'),'edited');
  assert.match(f.run('portfolioPrompt.message'),/active workflow changed/i);
});
test('portfolio trace displays escaped completed prompt, metadata and explanations',()=>{
  const f=fixture();
  f.run(`state.portfolio_model={id:'run',status:'completed',capital:'100',provider:'provider',model:'model',created_at:'2026-11-04T00:00:00Z',elapsed_seconds:3,inputs:[],exclusions:[],result:{provider:'provider',model:'model',capital:'100',reference_value:'0',cash:'100',target_cash_weight:'1',cash_rationale:'<cash>',system_prompt:'<actual prompt>',response_metadata:{marker:'<meta>'},allocations:[{symbol:'X',weight:'0',shares:0,reference_value:'0',reference:{price:'10',timestamp:'2026-11-04T00:00:00Z',basis:'close'},rationale:'<why zero>',entry_conditions:'<entry>'}]}};`);
  const html=f.run('renderProposedPortfolio()');
  for(const text of ['&lt;actual prompt&gt;','&lt;meta&gt;','&lt;cash&gt;','&lt;why zero&gt;','&lt;entry&gt;'])assert.ok(html.includes(text),text);
  assert.match(html,/provider \/ model/);assert.match(html,/3s/);
});
test('portfolio trace escapes retained content and labels unavailable history',()=>{
  const f=fixture();f.run(`state.portfolio_model={id:'run',status:'completed',capital:'100',inputs:[{symbol:'X',final_decision:'<script>bad</script>'}],exclusions:[],result:null};`);
  const html=f.run('renderProposedPortfolio()');
  assert.match(html,/Unavailable for this run/);
  assert.match(html,/Raw model response is not retained/);
  assert.match(html,/&lt;script&gt;bad&lt;\/script&gt;/);
  assert.doesNotMatch(html,/<script>bad/);
});
test('compact research retains coverage gaps for row warnings without changing completion status',()=>{
  const storeSource=fs.readFileSync(path.join(root,'..','store.py'),'utf8');
  const projection=/data\["research"\]\[result\["symbol"\]\]\s*=\s*\{\s*\*\*\{key: status\.get\(key\) for key in\s*\(([^)]+)\)/.exec(storeSource);
  assert.ok(projection,'shared compact per-symbol projection must be found');
  assert.match(projection[1],/"coverage_gaps"/,'compact projection must retain the detail coverage warnings');
  assert.match(projection[1],/"completion_gaps"/,'completion evidence remains separate');
  const f=fixture();f.run(`state.research={AAPL:{run_id:'saved',status:'completed',coverage_gaps:['News unavailable','Memory write rejected']}};`);
  assert.match(f.run('researchCollection(null)'),/2 coverage gaps/);
  assert.equal(f.run('state.research.AAPL.status'),'completed');
});
test('research collection reads loaded drift evidence without starting instrument requests',()=>{
  const f=fixture();f.run(`globalThis.calls=[];api=async path=>{calls.push(path);return {};};
    state.research={AAPL:{run_id:'saved',trade_date:'2026-11-03',status:'completed'},META:{run_id:'saved',trade_date:'2026-11-03',status:'completed'}};
    state.quotes={AAPL:{price:110}};
    chartEvidence.set('saved:AAPL',{symbol:'AAPL',run_id:'saved',bars:[{t:'2026-11-03',raw:{c:100}}]});`);
  assert.match(f.run('researchCollection(null)'),/research-picker-row/);
  assert.equal(f.run('calls.length'),0,'rendering missing drift must not queue full instrument histories');
  assert.equal(f.run('researchDrift("AAPL")'),f.run('percent(10)'));
  assert.equal(f.run('researchDrift("META")'),'—');
});
test('request errors preserve deadline phase, route, cause and HTTP details',async()=>{
  const f=fixture();let deadline;
  f.context.setTimeout=callback=>{deadline=callback;return 1;};
  f.context.fetch=()=>new Promise(()=>{});
  const pending=f.run('api("/api/state?compact=1",undefined,{timeoutMs:15})');
  deadline();
  await assert.rejects(pending,error=>{
    assert.match(error.message,/GET \/api\/state/);assert.match(error.message,/15\s*ms/);
    assert.match(error.message,/no HTTP response/i);assert.match(error.message,/deadline/i);
    assert.equal(error.cause.message,'Request deadline exceeded.');return true;
  });
  f.context.fetch=async()=>{const error=new Error('Transport canceled by browser');error.name='AbortError';throw error;};
  await assert.rejects(f.run('api("/api/runs/saved")'),error=>{
    assert.match(error.message,/GET \/api\/runs\/saved/);assert.match(error.message,/Transport canceled by browser/);
    assert.doesNotMatch(error.message,/timed out|exceeded.*deadline/i);assert.equal(error.cause.name,'AbortError');return true;
  });
  f.context.fetch=async()=>({status:503,ok:false,json:async()=>({error:'Saved evidence is unavailable'})});
  await assert.rejects(f.run('api("/api/runs/saved")'),error=>error.status===503&&error.message.includes('Saved evidence is unavailable'));
  f.context.fetch=async()=>({status:200,ok:true,json:()=>new Promise(()=>{})});
  const bodyPending=f.run('api("/api/runs/saved",undefined,{timeoutMs:15})');
  await Promise.resolve();deadline();
  await assert.rejects(bodyPending,error=>{
    assert.match(error.message,/HTTP 200/);assert.match(error.message,/body|reading.*response/i);return true;
  });
});
test('research Activity retries a cached error only after the run version changes or explicit refresh',async()=>{
  const f=fixture();
  f.run(`globalThis.run={id:'activity-run',status:'running',event_count:1};
    globalThis.calls=0;globalThis.paths=[];
    api=async path=>{calls++;paths.push(path);throw Error('The local service did not respond in time.');};`);
  await f.run('loadResearchRun(run)');
  assert.equal(f.run('calls'),1);
  assert.match(f.run('researchReadNotice(researchRunDetails.get(researchRunKey(run)))'),/class="negative"/);
  f.run('researchRunDetails.get(researchRunKey(run)).at=0;');
  await f.run('loadResearchRun(run)');
  assert.equal(f.run('calls'),1,'unchanged failed version must not automatically retry even after the polling interval');
  f.run(`run.event_count++;globalThis.finishRead=null;
    api=path=>{calls++;paths.push(path);return new Promise(resolve=>finishRead=resolve);};
    globalThis.reload=loadResearchRun(run);`);
  assert.equal(f.run('calls'),2,'changed version must permit a normal detail read');
  await f.run('loadResearchRun(run)');
  await f.run('loadResearchRun(run,true)');
  assert.equal(f.run('calls'),2,'automatic and forced reads must deduplicate the in-flight read');
  f.run(`finishRead({id:run.id,events:[{message:'Saved activity recovered'}]});`);
  await f.run('reload');
  assert.equal(f.run('researchRunDetails.get(researchRunKey(run)).error'),'');
  assert.equal(f.run('researchRunDetails.get(researchRunKey(run)).data.events[0].message'),'Saved activity recovered');
  assert.doesNotMatch(f.run('researchReadNotice(researchRunDetails.get(researchRunKey(run)))'),/class="negative"/);
  f.run(`run.event_count++;api=async path=>{calls++;paths.push(path);throw Error('Another timeout');};`);
  await f.run('loadResearchRun(run)');
  assert.equal(f.run('calls'),3);
  f.run(`api=async path=>{calls++;paths.push(path);return {id:run.id,events:[]};};`);
  await f.run('loadResearchRun(run,true)');
  assert.equal(f.run('calls'),4,'explicit refresh must bypass an unchanged failed version');
  assert.equal(f.run('researchRunDetails.get(researchRunKey(run)).error'),'');
  assert.equal(f.run(`paths.every(path=>path==='/api/runs/activity-run')`),true);
});
const opened = html => [...html.matchAll(/<details\b([^>]*)>/g)].filter(m=>/class="report-section"/.test(m[1])&&/\sopen(?:\s|$|=)/.test(m[1])).map(m=>/data-report="([^"]+)"/.exec(m[1])[1]);
// Frozen prefix shape from completed META run 3f948cc2 (2026-10-16).
// Narrative is shortened; repeated labels and their line boundaries are exact.
const duplicatedPortfolio = '**Rating**: Overweight\n\n**Executive Summary**: **Rating**\nOverweight\n\n**Executive Summary**\nFavor gradual exposure only after fresh execution checks; this authorizes no order.\n\n**Investment Thesis**: **Investment Thesis**\nPositive cash generation does not prove incremental AI returns.\n\n**Price Target**: Not provided';
function artifactParts(f,name,content){
  f.context.portfolioInput=content;
  const html=f.run(`renderReportArtifact(${JSON.stringify(name)},portfolioInput)`);
  return {html,body:html.split('<details class="report-raw"')[0],raw:html.match(/<pre>([\s\S]*)<\/pre><\/details>$/)?.[1]};
}
test('T-1.12 repeated portfolio prefixes appear once without changing source artifact',()=>{
  const f=fixture();const {body,raw}=artifactParts(f,'final_trade_decision',duplicatedPortfolio);
  for(const label of ['Rating','Executive Summary','Investment Thesis']){
    assert.equal((body.match(new RegExp(`<strong>${label}</strong>`,'g'))||[]).length,1,`${label} displayed once`);
  }
  assert.match(body,/Favor gradual exposure only after fresh execution checks; this authorizes no order\./);
  assert.match(body,/Positive cash generation does not prove incremental AI returns\./);
  assert.match(body,/Not provided/);
  assert.equal(raw,f.run('esc(portfolioInput)'),'raw artifact retains original repeated labels and bytes after HTML escaping');
  assert.equal(f.context.portfolioInput,duplicatedPortfolio,'caller input must not change');
});
test('T-1.12 conflicting inner rating and substantive repeated words are never hidden',()=>{
  const f=fixture();const source=duplicatedPortfolio.replace('**Rating**\nOverweight','**Rating**\nSell')+'\n\n**Investment Thesis**\nThis later heading introduces a counterargument. Rating changes require evidence.';
  const {body,raw}=artifactParts(f,'final_trade_decision',source);
  assert.match(body,/Sell/,'conflicting inner rating remains visible');
  assert.match(body,/This later heading introduces a counterargument\. Rating changes require evidence\./);
  assert.ok(body.includes('<strong>Investment Thesis</strong>'),'later thesis heading survives');
  assert.equal(raw,f.run('esc(portfolioInput)'));
});
test('T-1.12 normalization is restricted to portfolio decision and leaves ordinary reports alone',()=>{
  const f=fixture();const {body,raw}=artifactParts(f,'market_report',duplicatedPortfolio);
  assert.equal((body.match(/<strong>Executive Summary<\/strong>/g)||[]).length,2);
  assert.equal((body.match(/<strong>Rating<\/strong>/g)||[]).length,2);
  assert.equal(raw,f.run('esc(portfolioInput)'));
  const ordinary='**Rating**: Overweight\n\n**Executive Summary**: Rating confidence is limited.\n\n**Investment Thesis**: Investment Thesis is a named research document.';
  const rendered=artifactParts(f,'final_trade_decision',ordinary).body;
  assert.match(rendered,/Rating confidence is limited\./);
  assert.match(rendered,/Investment Thesis is a named research document\./);
});
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
