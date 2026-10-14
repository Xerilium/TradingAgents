// Bounded request failures and recovery. No broker, model, or network access.
const source = require('node:fs').readFileSync('.impeccable/review/paper-desk-render-check.cjs','utf8');
const harness = source.split("assert(render('renderOverview()')")[0];
const checks = String.raw`
context.setTimeout=setTimeout;context.clearTimeout=clearTimeout;
context.AbortController=AbortController;
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  context.fetch=()=>new Promise(()=>{});
  const start=performance.now();
  await assert.rejects(render("api('/api/state',undefined,{timeoutMs:20})"),/did not respond in time/);
  assert(performance.now()-start<500);
  await assert.rejects(render("api('/api/orders',{proposal_id:'test'},{timeoutMs:20})"),/outcome may be unknown/);
  await assert.rejects(render("api('/api/orders/cancel',{order_id:'test'},{timeoutMs:20})"),/Do not resend cancellation/);
  // Use the existing action path, shortening only its fixture deadline.
  render("const realApi=api;api=(path,body,options)=>realApi(path,body,{...options,timeoutMs:20});");
  let cancelRequests=0;
  context.fetch=path=>{if(path==='/api/orders/cancel')cancelRequests++;return new Promise(()=>{});};
  await assert.rejects(render("cancelOrder('timed-out-order')"),/outcome may be unknown/);
  assert.equal(render('busy.size'),0);
  assert(render("cancellationPending('timed-out-order')"));
  await render("cancelOrder('timed-out-order')");
  assert.equal(cancelRequests,1,'A timed-out cancellation must not resend after busy clears');
  assert(render('mutationUncertain()'),'New plans and submissions must remain blocked');
  context.AbortController=undefined;
  await assert.rejects(render("api('/api/state',undefined,{timeoutMs:20})"),/did not respond in time/);
  context.fetch=async()=>({ok:true,status:200,json:()=>new Promise(()=>{})});
  await assert.rejects(render("api('/api/state',undefined,{timeoutMs:20})"),/did not respond in time/);
  context.fetch=async()=>({ok:true,status:200,json:async()=>fixture});
  assert.equal((await render("api('/api/state',undefined,{timeoutMs:100})")).config.name,'FANGMAN');
  console.log('PASS: stalled fetch and body have deadlines, submission ambiguity is explicit, requests recover.');
})().catch(error=>{console.error(error);process.exitCode=1;});
`;
new Function('require','AbortController','setTimeout','clearTimeout','setImmediate','performance','process',harness+checks)(
  require,AbortController,setTimeout,clearTimeout,setImmediate,performance,process);
