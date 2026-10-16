// T-1.6: offline real-source display regressions. No backend or timers run.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'..','tradingagents','web','static');
const quote={price:736.58,timestamp:'2026-10-15T19:59:59Z',quote_timestamp:'2026-10-15T19:59:59Z'};
const clock={is_open:false,timestamp:'2026-10-15T23:31:12Z',next_open:'2026-10-16T13:30:00Z',next_close:'2026-10-16T20:00:00Z'};
function fixture(now='2026-10-15T23:53:00Z',q=quote,c=clock){
  const nodes=new Map();
  const node=s=>{if(!nodes.has(s))nodes.set(s,{textContent:'',innerHTML:'',addEventListener(){},classList:{toggle(){}},querySelector(){return node('child');},querySelectorAll(){return [];}});return nodes.get(s);};
  const NativeDate=Date;
  class FrozenDate extends NativeDate {constructor(...args){super(...(args.length?args:[now]));}static now(){return NativeDate.parse(now);}}
  const context=vm.createContext({Date:FrozenDate,Intl,console,URL,AbortController,
    document:{hidden:false,addEventListener(){},querySelector:node,querySelectorAll(){return[];}},
    window:{addEventListener(){}},location:{hash:'#overview'},localStorage:{getItem(){return null;}},
    setInterval(){},setTimeout(){},clearTimeout(){},fetch(){throw Error('Network forbidden');}});
  vm.runInContext(fs.readFileSync(path.join(root,'lists.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/^readState\(\);\r?$/m,''),context);
  const run=code=>vm.runInContext(code,context);
  context.fixtureQuote=q;context.fixtureClock=c;
  run(`state={clock:fixtureClock,quotes:{META:fixtureQuote},updated_at:fixtureClock?.timestamp,config:{name:'FANGMAN',universe:['META']},connection:{connected:true},proposals:[],orders:[],positions:[],research:{},runs:[]};`);
  return {run,status:()=>run('DeskLists.quoteState(fixtureQuote,Date.now(),state.clock)'),label:()=>run('quoteStatus(fixtureQuote)'),header:()=>{run('renderChrome()');return node('#last-updated').textContent;}};
}
test('aged closed clock: header and latest-session row agree after 22 minutes',()=>{
  const f=fixture();assert.match(f.header(),/Market closed/);assert.equal(f.status(),'closed');assert.match(f.label(),/Market closed/);assert.doesNotMatch(f.label(),/stale/i);
});
test('latest-session reference remains closed overnight until verified next open',()=>{
  assert.equal(fixture('2026-10-16T12:30:00Z').status(),'closed');
});
test('Friday reference remains closed over weekend with broker supplied Monday next open',()=>{
  const f=fixture('2026-10-18T18:00:00Z',{...quote,timestamp:'2026-10-16T19:59:59Z',quote_timestamp:'2026-10-16T19:59:59Z'},{...clock,timestamp:'2026-10-16T20:10:00Z',next_open:'2026-10-19T13:30:00Z',next_close:'2026-10-19T20:00:00Z'});
  assert.equal(f.status(),'closed');
});
test('older-date reference is unverified because clock supplies no previous session boundary',()=>{
  const f=fixture('2026-10-15T23:35:00Z',{...quote,timestamp:'2026-10-14T19:59:59Z',quote_timestamp:'2026-10-14T19:59:59Z'});
  assert.equal(f.status(),'unverified');assert.match(f.label(),/session unverified/i);assert.doesNotMatch(f.label(),/stale/i);
});
test('next-open boundary invalidates old closed observation without claiming market closed',()=>{
  const f=fixture(clock.next_open);assert.notEqual(f.status(),'closed');assert.doesNotMatch(f.header(),/Market closed/);assert.match(f.header(),/unknown|unavailable|unverified|status not/i);
});
test('missing is_open is unknown, not false/closed',()=>{
  const f=fixture(undefined,quote,{timestamp:clock.timestamp,next_open:clock.next_open});
  assert.notEqual(f.status(),'closed');assert.doesNotMatch(f.header(),/Market closed/);assert.match(f.header(),/unknown|unavailable|unverified|status not/i);
});
test('invalid clock timestamp cannot prove market closed',()=>{
  const f=fixture(undefined,quote,{...clock,timestamp:'invalid'});assert.notEqual(f.status(),'closed');assert.doesNotMatch(f.header(),/Market closed/);
});
test('future clock cannot prove market closed',()=>{
  const f=fixture(undefined,quote,{...clock,timestamp:'2026-10-16T01:00:00Z'});assert.notEqual(f.status(),'closed');assert.doesNotMatch(f.header(),/Market closed/);
});
test('verified open-market old quote remains stale',()=>{
  const f=fixture('2026-10-15T18:00:00Z',{...quote,timestamp:'2026-10-15T17:00:00Z',quote_timestamp:'2026-10-15T17:00:00Z'},{is_open:true,timestamp:'2026-10-15T17:59:00Z',next_close:'2026-10-15T20:00:00Z',next_open:'2026-10-16T13:30:00Z'});
  assert.equal(f.status(),'stale');assert.match(f.header(),/Market open/);
});
test('verified open-market recent quote remains current',()=>{
  const f=fixture('2026-10-15T18:00:00Z',{...quote,timestamp:'2026-10-15T17:59:00Z',quote_timestamp:'2026-10-15T17:59:00Z'},{is_open:true,timestamp:'2026-10-15T17:59:00Z',next_close:'2026-10-15T20:00:00Z',next_open:'2026-10-16T13:30:00Z'});
  assert.equal(f.status(),'current');
});
test('missing price stays missing regardless of closed clock',()=>assert.equal(fixture(undefined,{...quote,price:null}).status(),'missing'));
test('closed reference label remains last trade, never official close',()=>{
  const f=fixture('2026-10-15T23:35:00Z');assert.equal(f.status(),'closed');assert.match(f.label(),/Last trade/);assert.doesNotMatch(f.label(),/official clos|closing price|auction/i);
});

test('Sunday refreshed clock cannot establish which prior date was last trading session',()=>{
  const f=fixture('2026-10-18T18:00:00Z',{...quote,timestamp:'2026-10-16T19:59:59Z',quote_timestamp:'2026-10-16T19:59:59Z'},{...clock,timestamp:'2026-10-18T17:59:00Z',next_open:'2026-10-19T13:30:00Z'});
  assert.equal(f.status(),'unverified');assert.match(f.header(),/Market closed/);assert.match(f.label(),/session unverified/);assert.doesNotMatch(f.label(),/stale/i);
});

test('broker holiday and DST boundary is used without fixed weekday or UTC-hour assumptions',()=>{
  const f=fixture('2026-11-01T22:00:00Z',{...quote,timestamp:'2026-10-30T19:59:59Z',quote_timestamp:'2026-10-30T19:59:59Z'},{...clock,timestamp:'2026-10-30T21:00:00Z',next_open:'2026-11-02T14:30:00Z'});
  assert.equal(f.status(),'closed');
});

test('open observation expires exactly at supplied early close',()=>{
  const c={is_open:true,timestamp:'2026-11-27T16:59:00Z',next_close:'2026-11-27T18:00:00Z'};
  const f=fixture(c.next_close,quote,c);assert.match(f.header(),/unknown/);assert.equal(f.status(),'unknown');
});

test('missing boundary and absent clock leave market explicitly unknown',()=>{
  for(const c of [null,{...clock,next_open:null},{...clock,next_open:'invalid'}]){
    const f=fixture(undefined,quote,c);assert.equal(f.status(),'unknown');assert.match(f.label(),/market status unknown/);assert.match(f.header(),/unknown/);
  }
});
