// Offline request-count regression. Never contacts the live desk or Gateway.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const intervals=[];
const base=fs.readFileSync('.impeccable/review/paper-desk-render-check.cjs','utf8').split("assert(render('renderOverview()")[0];
eval(base.replace("const fs = require('node:fs');",'').replace("const vm = require('node:vm');",'').replace("const assert = require('node:assert/strict');",'').replace('setInterval(){}','setInterval(fn){intervals.push(fn)}')+`globalThis.traffic={context,render,fixture,requests};`);
const {context,render,fixture,requests}=globalThis.traffic;
(async()=>{
 await render('stateWait');
 // An idle or disconnected desk must perform no periodic reads or refreshes.
 render('state.account=null;state.runs=[];');requests.length=0;
 for(let tick=0;tick<100;tick++)for(const fn of intervals)await fn();
 assert.equal(requests.length,0);
 render("state.runs=[{id:'running',status:'running'}];state.connection.connected=false;");
 for(let tick=0;tick<100;tick++)for(const fn of intervals)await fn();
 assert.equal(requests.length,0,'Disconnected active runs must not poll');
 render("state.connection.connected=true;stateErrorMessage='Timed out';");
 for(let tick=0;tick<100;tick++)for(const fn of intervals)await fn();
 assert.equal(requests.length,0,'A failed read must stop automatic polling');
 await render('readState()');
 assert(!requests.some(r=>r.path==='/api/refresh'),'Opening/reading a desk must not refresh the broker');
 // A newer or older detail revision must not recurse into an HTTP request loop.
 for(const revision of [2,0]){
  render(`state.runs=[{id:'r',status:'running',symbols:['META'],results:[{symbol:'META',revision:1,status:'running'}]}];selectedRunId='r';selectedSymbol='META';activePage='research';resultDetails.clear();detailLoadedFor.clear();detailErrors.clear();`);
  let reads=0;
  context.fetch=async()=>{if(++reads>3)throw new Error('Request loop');return {ok:true,json:async()=>({symbol:'META',revision,status:'running',reports:{market_report:'Fixture'}})}};
  await render('ensureResultDetail()');
  for(let i=0;i<10;i++)await Promise.resolve();
  assert.equal(reads,1,`revision ${revision} should fetch once`);
  await render('ensureResultDetail()');assert.equal(reads,1);
  await render('ensureResultDetail(true)');assert.equal(reads,2,'Explicit report refresh is allowed');
 }
 // Positive control: the old equality guard produces repeated requests.
 const source=fs.readFileSync('tradingagents/web/static/app.js','utf8');
 const implementation=source.slice(source.indexOf('async function ensureResultDetail('),source.indexOf('async function ensureChart('));
 const faulty=implementation.replace('(!force&&resultDetails.has(key)&&(resultDetails.get(key).revision>=summary.revision||detailLoadedFor.get(key)===summary.revision))','(!force&&resultDetails.get(key)?.revision===summary.revision)');
 assert.notEqual(faulty,implementation);
 vm.runInContext(faulty,context);
 render('resultDetails.clear();detailLoadedFor.clear();detailErrors.clear();');
 let repeated=0;
 context.fetch=async()=>{if(++repeated>3)throw new Error('Offline positive-control cap');return {ok:true,json:async()=>({symbol:'META',revision:2,reports:{market_report:'Fixture'}})}};
 await render('ensureResultDetail()');for(let i=0;i<30;i++)await Promise.resolve();
 assert.equal(repeated,4,'The former guard must reproduce the loop, capped offline at four requests');
 vm.runInContext(implementation,context);
 context.document.activeElement={id:'removed-checkbox',tagName:'INPUT'};
 assert.doesNotThrow(()=>render('render()'),'Removing a focused filtered row must not break rendering');
 context.fetch=async()=>({ok:true,json:async()=>({symbol:'META',status:'failed',error:'Review step failed',reports:{market_report:'Retained evidence'}})});
 const failedDetail=await render("api('/api/runs/r/results/META')");
 assert.equal(failedDetail.error,'Review step failed');
 assert.equal(failedDetail.reports.market_report,'Retained evidence','A failed review must not hide completed reports');
 // Cooldown is a server deadline, not an automatic retry timer. Advance only fake time.
 let now=Date.parse('2026-10-14T12:00:00Z');
 context.Date=class extends Date {static now(){return now;}};
 render('state.runs=[];stateErrorMessage="";');
 for(const [header,seconds] of [['900',900],['60',60],['5',5],['garbage',30],[null,30],['NaN',30],['Infinity',30],['0',1],[new Date(now+900000).toUTCString(),900]]){
  now=Date.parse('2026-10-14T12:00:00Z');
  const start=now;let calls=0;
  render('rateLimitedUntil=0;');
  context.fetch=async()=>{calls++;return {ok:false,status:429,headers:{get:()=>header}};};
  await assert.rejects(render("api('/api/refresh',{})"),e=>e.status===429);
  assert.equal(render('rateLimitedUntil'),start+seconds*1000);
  assert(render('rateLimitMessage()').includes(render('time(rateLimitedUntil)')));
  for(const elapsed of [...new Set([Math.min(60000,seconds*1000-1),seconds*1000-1])]){
   now=start+elapsed;for(const fn of intervals)await fn();
   assert.equal(render("$('#refresh').disabled"),true);
   for(const path of ['/api/refresh','/api/instruments/META','/api/runs','/api/proposals','/api/orders','/api/orders/cancel'])
    await assert.rejects(render(`api(${JSON.stringify(path)},{})`),/rate limit/);
   assert.equal(calls,1,'Blocked actions and countdown ticks must not send requests');
  }
  now=start+seconds*1000;for(const fn of intervals)await fn();
  assert.equal(render('coolingDown()'),false);
  assert.equal(render("$('#refresh').disabled"),false);
  assert.equal(calls,1,'Expiry must not replay refresh, research or orders');
  context.fetch=async()=>{calls++;return {ok:true,status:200,json:async()=>({})};};
  await render("api('/api/refresh',{})");
  assert.equal(calls,2,'An explicit action is allowed after the true deadline');
 }
 console.log('PASS: 900-second and HTTP-date cooldowns remain blocked after 60 seconds; normal and malformed delays expire without replay.');
 console.log('PASS: zero idle polling, no automatic broker refresh, old revision-loop reproduced offline (4 capped requests), fixed guard fetches once.');
})().catch(e=>{console.error(e);process.exitCode=1});
