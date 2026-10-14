// Render-only fixtures. This file never contacts a broker or submits an order.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let focusCalls=0;
const listeners=new Map();
const requests=[];
const observers=[];
let rejectedPath='';
const node = () => ({innerHTML:'',textContent:'',hidden:false,disabled:false,classList:{toggle(){}},addEventListener(){},insertAdjacentHTML(){},focus(){focusCalls++;},close(){},querySelectorAll(){return context.document.activeElement?[context.document.activeElement]:[];}});
const elements = new Map();
const fixture = {
  config:{name:'FANGMAN',universe:['META','AAPL'],allocation_pct:70,max_position_pct:15,max_order_notional:5000,reserve_pct:20,llm_provider:'openai',deep_think_llm:'model',quick_think_llm:'model',backend_url:null},
  connection:{connected:true,paper_verified:true,domains:['alpaca','laya','maenifold.memory']},
  readiness:{ready:true},account:{equity:'100000',cash:'100000',buying_power:'100000'},
  positions:[],orders:[],quotes:{META:{price:99,change_pct:1,bid:98.9,ask:99.1,timestamp:'2026-10-13T20:00:00Z'}},
  bars:{META:[{o:90,c:91,h:93,l:89,v:100,t:'2026-10-12'},{o:91,c:99,h:101,l:90,v:200,t:'2026-10-13'}]},
  history:{equity:[99000,100000],timestamp:[1791849600,1791936000]},runs:[],proposals:[],errors:[],updated_at:'2026-10-13T20:00:00Z',csrf_token:'test'
};
const context = {
  console,Intl,Date,JSON,Map,Set,Number,String,Array,Object,Math,Boolean,URL,
  document:{querySelector(s){if(!elements.has(s))elements.set(s,node());return elements.get(s);},querySelectorAll(){return [];},getElementById(id){return elements.get(`#${id}`);},addEventListener(type,handler){if(!listeners.has(type))listeners.set(type,[]);listeners.get(type).push(handler);},activeElement:null,hidden:false},
  window:{addEventListener(){},scrollTo(){}},location:{hash:'#overview'},
  fetch:async(path,options)=>{requests.push({path,options});return {ok:path!==rejectedPath,json:async()=>path===rejectedPath?{error:'Isolated test rejection'}:path.startsWith('/api/state')?fixture:path==='/api/runs'?{run_id:'test-run'}:{}};},setInterval(){},setTimeout(){},clearTimeout(){},
  ResizeObserver:class {constructor(callback){this.callback=callback;observers.push(this);}observe(target){this.target=target;}disconnect(){}},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('tradingagents/web/static/lists.js','utf8'),context);
vm.runInContext(fs.readFileSync('tradingagents/web/static/app.js','utf8'),context);
vm.runInContext(`state=${JSON.stringify(fixture)};selectedSymbol='META';selectedSymbols=new Set(['META','AAPL']);`,context);
const render = expression => vm.runInContext(expression,context);
assert(render('renderOverview()').includes('$100,000.00'));
assert(render('stockChart()').includes('daily price candles, 2 sessions'));
assert(!render('stockChart()').includes('NaN'));
assert(render("barDate('2026-10-13T04:00:00Z')").includes('13'));
assert(render('renderResearch()').includes('Your first research run'));
assert(render('renderOrders()').includes('No proposals yet'));
assert(!render('renderSettings()').match(/id="config-backend_url"[^>]*required/));
vm.runInContext(`state.runs=[{id:'test-run',status:'completed',symbols:['META'],created_at:'2026-10-13',results:[{symbol:'META',rating:'Buy',status:'completed',reports:{market_report:'<img src=x onerror=alert(1)>'},laya:{source:'example'}}],events:[{timestamp:'2026-10-13',symbol:'META',message:'complete'}]}];state.proposals=[{id:'proposal-1',symbol:'META',side:'buy',qty:2,limit_price:99,notional:198,status:'pending',reason:'Test fixture'}];`,context);
assert(render('renderResearch()').includes('&lt;img src=x onerror=alert(1)&gt;'));
assert(!render('renderResearch()').includes('<img src=x'));
// The persisted AAPL run encodes debate state as JSON strings, with repeated role histories.
const nestedReports={status:'completed',reports:{
  investment_debate_state:JSON.stringify({history:'Bull Analyst: **Demand** holds.\n\nBear Analyst: *Valuation* is stretched.',bull_history:'Bull Analyst: **Demand** holds.',bear_history:'Bear Analyst: *Valuation* is stretched.',current_response:'### Committee view\nUnderweight until evidence improves.',count:2}),
  risk_debate_state:JSON.stringify({history:'Aggressive Analyst: Keep the position small.\n\nConservative Analyst: Preserve cash.\n\nNeutral Analyst: Wait for confirmation.',aggressive_history:'Aggressive Analyst: Keep the position small.',conservative_history:'Conservative Analyst: Preserve cash.',neutral_history:'Neutral Analyst: Wait for confirmation.',current_aggressive_response:'Aggressive Analyst: Keep the position small.',latest_speaker:'Judge',count:3}),
  market_report:'# Price evidence\n\n**Trend:** weakening.\n\n- Support is nearby.\n- *Volume* is elevated.\n\n| Measure | Value |\n| --- | --- |\n| Close | $100.00 |\n\n[Broker source](https://example.com/quote?symbol=AAPL&date=2026-10-13)',
  final_trade_decision:'**Rating**: Sell\n\n## Executive Summary\nWait for stronger evidence.',
  investment_plan:'### Committee view\nUnderweight until evidence improves.',
  trader_investment_plan:'1. Review evidence.\n2. Keep sizing within policy.'
},laya:{grade:'ask_human',summary:'Two answers need human review.',contract:{grade:'ask_human',summary:'Two answers need human review.',decisions:{evidence_complete:{value:'true',confidence:.516,margin:.016}}},answers:{evidence_complete:{kind:'yes_no',value:true,confidence:.516,margin:.032,grade:'ask_human',reason:'Confidence is below the required threshold.'},decision_consistent:{kind:'yes_no',value:false,confidence:.5429,grade:'ask_human',reason:'A second review is needed.'}}}};
const artifactHtml=render(`renderReports(${JSON.stringify(nestedReports)})`);
assert.match(artifactHtml,/<details class="report-section" data-report="final_trade_decision" open>/,'The final decision must be the first open report');
assert(artifactHtml.indexOf('data-report="final_trade_decision"')<artifactHtml.indexOf('data-report="market_report"'));
assert(artifactHtml.indexOf('data-report="market_report"')<artifactHtml.indexOf('data-report="investment_debate_state"'));
assert(artifactHtml.includes('<strong>Rating</strong>: Sell'));
assert(artifactHtml.includes('<h4>Executive Summary</h4>'));
assert(artifactHtml.includes('<ul><li>Support is nearby.</li><li><em>Volume</em> is elevated.</li></ul>'));
assert(artifactHtml.includes('<th scope="col">Measure</th>'));
assert(artifactHtml.includes('<td>$100.00</td>'));
assert(artifactHtml.includes('href="https://example.com/quote?symbol=AAPL&amp;date=2026-10-13" target="_blank" rel="noopener noreferrer"'));
assert(!artifactHtml.includes('<details class="report-raw" open>'),'Raw artifacts must stay secondary and collapsed');
const debateHtml=render(`reportDebate(${JSON.stringify(nestedReports.reports.investment_debate_state)},${JSON.stringify(nestedReports.reports.investment_plan)})`);
assert.equal((debateHtml.match(/Bull Analyst:/g)||[]).length,1);
assert.equal((debateHtml.match(/Bear Analyst:/g)||[]).length,1);
assert(debateHtml.includes('<h3>Committee decision</h3>'));
assert(!debateHtml.includes('bull_history')&&!debateHtml.includes('\\n'));
assert(artifactHtml.includes('<h3>Committee decision</h3>'),'Report rendering must pass the authoritative manager output');
const interimDebate={history:'Bull: A\n\nBear: B',current_response:'Bear: B'};
const interimHtml=render(`reportDebate(${JSON.stringify(interimDebate)})`);
assert.equal((interimHtml.match(/Bear: B/g)||[]).length,1,'The latest analyst response already present in history must not repeat');
assert(!interimHtml.includes('Committee decision')&&!interimHtml.includes('Latest response'));
const freshResponse={history:'Bull: A',current_response:'Bear: B'};
const freshResponseHtml=render(`reportDebate(${JSON.stringify(freshResponse)},'Manager: C')`);
assert(freshResponseHtml.includes('<h3>Latest response</h3>'));
assert(!freshResponseHtml.includes('<h3>Committee decision</h3>'),'An analyst response must not be promoted to committee output');
const interimArtifact=render(`renderReports(${JSON.stringify({status:'running',reports:{investment_debate_state:JSON.stringify(interimDebate)}})})`);
assert(!interimArtifact.includes('<h3>Committee decision</h3>'));
assert.equal(render(`reportMarkdown(${JSON.stringify('3. Trim\n4. Review')})`),'<ol start="3"><li>Trim</li><li>Review</li></ol>');
assert.equal(render(`reportMarkdown(${JSON.stringify('7) Check\n8) Confirm')})`),'<ol start="7"><li>Check</li><li>Confirm</li></ol>');
assert.equal(render(`reportInline('free_cash_flow and debt__to__equity; _emphasis_ and __strong__.')`),'free_cash_flow and debt__to__equity; <em>emphasis</em> and <strong>strong</strong>.');
assert.equal(render(`reportInline('métrique_par_action and (_caution_)')`),'métrique_par_action and (<em>caution</em>)');
const riskHtml=render(`reportDebate(${JSON.stringify(nestedReports.reports.risk_debate_state)})`);
assert.equal((riskHtml.match(/Aggressive Analyst:/g)||[]).length,1);
assert(!riskHtml.includes('latest_speaker')&&!riskHtml.includes('current_aggressive_response'));
const layaHtml=render(`reportLaya(${JSON.stringify(nestedReports.laya)})`);
assert.equal((layaHtml.match(/Two answers need human review\./g)||[]).length,1);
assert(layaHtml.includes('<dd>Ask human</dd>'));
assert(layaHtml.includes('<h3>Evidence complete</h3>')&&layaHtml.includes('<h3>Decision consistent</h3>'));
assert(layaHtml.includes('<p>Yes</p>')&&layaHtml.includes('<p>No</p>'));
assert(layaHtml.includes('Yes no · 52% confidence · Ask human'));
assert(!layaHtml.includes('0.016')&&!layaHtml.includes('0.032'),'Do not conflate contract and answer margins');
const hostileReport='# <img src=x onerror=alert(1)>\n\n<script>alert(1)</script>\n\n**<svg onload=alert(1)>**\n\n[bad](javascript:alert(1)) [entity](javascript&#58;alert) [data](data:text/html,payload) [local](file:///secret) [relative](//example.com)\n\n![external image](https://example.com/pixel.png)\n\n| Field | Payload |\n| --- | --- |\n| x | <iframe src=javascript:alert(1)> |\n\n```html\n<img src=x onerror=alert(1)>\n```';
const hostileHtml=render(`reportMarkdown(${JSON.stringify(hostileReport)})`);
assert(!/<(?:script|img|svg|iframe)\b/i.test(hostileHtml),'Source HTML and images must never become elements');
assert(!hostileHtml.includes('<a '),'Unsafe, relative, and image destinations must never become links');
assert(hostileHtml.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
assert(hostileHtml.includes('<strong>&lt;svg onload=alert(1)&gt;</strong>'));
assert(hostileHtml.includes('<pre><code>&lt;img src=x onerror=alert(1)&gt;</code></pre>'));
assert(render(`reportMarkdown(${JSON.stringify('>'.repeat(100)+' <script>bad</script>')})`).includes('&lt;script&gt;'));
assert(!render(`reportStructured(${JSON.stringify({heading:'<img src=x onerror=alert(1)>',answers:['[bad](javascript:alert)']})})`).includes('<img'));
vm.runInContext("selectedSymbol='AAPL';",context);
assert(render('renderResearch()').includes('<h2>AAPL</h2>'),'Opening evidence must preserve the chosen stock');
assert(render('renderOrders()').includes('Review order'));
vm.runInContext('state.trading_paused=true;',context);
assert.match(render('renderOrders()'),/data-proposal="proposal-1" disabled/);
vm.runInContext(`state.readiness={ready:false,message:'Missing model configuration'};`,context);
assert(render('researchButton()').includes('Configure research'));
vm.runInContext(`state.errors=[{source:'positions',message:'Positions request failed'},{source:'orders',message:'Orders request failed'}];`,context);
assert(render('positionsTable()').includes('Positions could not be loaded'));
assert(!render('positionsTable()').includes('No open positions'));
assert(render('orderBlotter()').includes('Order blotter could not be loaded'));
assert(render('accountLedger()').includes('Positions unavailable'));
assert(!render('accountLedger()').includes('0 open positions'));
async function keyboardAction(action,path,dataset={}){
  const button={...node(),tagName:'BUTTON',id:'',dataset:{action,...dataset},closest(){return this;}};
  context.document.activeElement=button;
  const before=requests.length;
  await listeners.get('click')[0]({target:button});
  assert(requests.slice(before).some(request=>request.path===path&&request.options.method==='POST'),`${action} must reach its POST request with keyboard focus`);
  assert.equal(render('busy.size'),0,`${action} must clear busy state`);
}
(async()=>{
  // Flush the boot-time state fetch, then exercise only fake local responses.
  await new Promise(resolve=>setImmediate(resolve));
  fixture.runs=[{id:'test-run',status:'completed',symbols:['META'],created_at:'2026-10-13',results:[],events:[]}];
  render(`state=${JSON.stringify(fixture)};selectedSymbol='META';selectedSymbols=new Set(['META']);initialRefreshTriggered=true;`);
  await keyboardAction('run','/api/runs');
  await keyboardAction('build-proposals','/api/proposals');
  await keyboardAction('submit-order','/api/orders',{proposal:'proposal-1'});
  await keyboardAction('cancel-order','/api/orders/cancel',{order:'order-1'});
  const cancelCount=()=>requests.filter(r=>r.path==='/api/orders/cancel').length;
  const firstCount=cancelCount();
  await render("cancelOrder('order-1')");
  assert.equal(cancelCount(),firstCount,'Repeated cancellation must not POST again');
  rejectedPath='/api/orders/cancel';
  await keyboardAction('cancel-order','/api/orders/cancel',{order:'order-2'});
  rejectedPath='';
  assert(render("cancellationPending('order-2')"),'An ambiguous error must not restore cancellation');
  const owned={id:'owned',symbol:'META',status:'accepted',broker_order_id:'order-1',
    broker_receipt:{id:'order-1',symbol:'META',side:'buy',qty:'2',limit_price:'99',filled_qty:'0',status:'accepted'},
    cancellation:{status:'requested'}};
  render(`state.orders=[];state.proposals=${JSON.stringify([owned,{id:'next',symbol:'AAPL',status:'proposed'}])};state.errors=[];state.trading_paused=false;`);
  assert(render('orderBlotter()').includes('Cancellation requested · Refresh to reconcile'));
  assert(render('orderBlotter()').includes('Last verified receipt'));
  assert.match(render('orderBlotter()'),/data-order="order-1" disabled/);
  assert.match(render('renderOrders()'),/data-proposal="next" disabled/);
  render("state.errors=[{source:'orders',message:'offline'}]");
  assert(render('orderBlotter()').includes('Cancellation requested'),'Local cancellation remains visible during broker list failure');
  render("state.proposals[0].cancellation.status='unknown';state.proposals[0].status='partially_filled';");
  assert(render('orderBlotter()').includes('Cancellation outcome unknown'));
  assert(render("cancellationPending('order-1')"),'Open or partial receipts cannot clear uncertainty');
  render("state.proposals[0].cancellation.status='resolved';state.proposals[0].status='canceled';state.proposals[0].broker_receipt.status='canceled';");
  assert(!render("cancellationPending('order-1')"));
  assert(render('orderBlotter()').includes('Cancellation resolved'));
  assert(!render('orderBlotter()').includes('data-action="cancel-order"'));
  // A fill discovered before cancellation dispatch has no cancellation record.
  fixture.proposals=[{...owned,status:'filled',cancellation:undefined,
    broker_receipt:{...owned.broker_receipt,status:'filled',filled_qty:'2'}},
    {id:'next',symbol:'AAPL',status:'proposed'}];
  fixture.orders=[];
  fixture.errors=[];
  render("pendingCancellations.clear();pendingCancellations.add('order-1');state={...state,proposals:[]};");
  assert(render('mutationUncertain()'),'Missing owned evidence cannot clear a pending cancellation');
  await render('readState({force:true})'); // Explicit refresh returns the authoritative terminal receipt.
  assert(!render("cancellationPending('order-1')"));
  assert(!render('mutationUncertain()'),'Terminal-before-cancel must restore new action eligibility');
  assert(!/data-proposal="next" disabled/.test(render('renderOrders()')));
  for(const status of ['accepted','partially_filled']){
    render(`pendingCancellations.add('order-1');state.proposals[0].status='${status}';state.proposals[0].broker_receipt.status='${status}';`);
    assert(render('mutationUncertain()'),'Open or partial evidence must retain the browser latch');
  }
  render("state.proposals[0].status='filled';state.proposals[0].broker_receipt.status='filled';state.proposals[0].reconciliation_error='conflicting receipt';");
  assert(render('mutationUncertain()'),'Conflicting terminal evidence cannot clear uncertainty');
  render("delete state.proposals[0].reconciliation_error;");
  for(const status of ['intent','requested','unknown']){
    render(`state.proposals[0].cancellation={status:'${status}'};`);
    assert(render('mutationUncertain()'),'Unresolved durable cancellation cannot be overridden by a stale terminal receipt');
  }
  fixture.runs[0].status='running';
  await keyboardAction('stop-run','/api/runs/cancel');
  assert(focusCalls>0,'Rendering must restore matching keyboard focus');
  context.document.activeElement=null;
  render("activePage='overview';chartMode='stock';render();");
  observers.at(-1).callback([{contentRect:{width:327,height:214}}]);
  assert(elements.get('.chart-wrap').innerHTML.includes('viewBox="0 0 327 214"'));
  assert(render('stockChart()').includes('viewBox="0 0 327 214"'));
  assert(render('equityChart()').includes('viewBox="0 0 327 214"'));
  const svgScale=327/render('chartSize.width');
  assert.equal(11*svgScale,11,'Mobile chart labels must retain an 11px rendered size');
  assert.equal(render('chartSize.height'),214,'Mobile plot must retain the full available content height');
  console.log('PASS: empty/populated renders, safe Markdown and nested live-shaped debate/Laya reports, truthful failures, keyboard run/build/submit/cancel requests and busy reset, responsive chart pixel geometry.');
})().catch(error=>{console.error(error);process.exitCode=1;});
