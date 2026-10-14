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
  fetch:async(path,options)=>{requests.push({path,options});return {ok:path!==rejectedPath,json:async()=>path===rejectedPath?{error:'Isolated test rejection'}:path==='/api/state'?fixture:path==='/api/runs'?{run_id:'test-run'}:{}};},setInterval(){},setTimeout(){},clearTimeout(){},
  ResizeObserver:class {constructor(callback){this.callback=callback;observers.push(this);}observe(target){this.target=target;}disconnect(){}},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('tradingagents/web/static/lists.js','utf8'),context);
vm.runInContext(fs.readFileSync('tradingagents/web/static/app.js','utf8'),context);
vm.runInContext(`state=${JSON.stringify(fixture)};selectedSymbol='META';selectedSymbols=new Set(['META','AAPL']);`,context);
const render = expression => vm.runInContext(expression,context);

const symbols=Array.from({length:500},(_,i)=>"S"+String(i).padStart(3,"0"));
const sample=structuredClone(fixture); sample.config.universe=symbols;
sample.config.name="500-stock verification fixture";
sample.quotes=Object.fromEntries(symbols.map((s,i)=>[s,{price:100+i,change_pct:(i%21-10)/10,timestamp:"2026-10-13T20:00:00Z"}]));
vm.runInContext("state="+JSON.stringify(sample)+"; selectedSymbol='S000'; selectedSymbols=new Set(state.config.universe);",context);
const started=performance.now(); const html=render("renderOverview()");
console.log(JSON.stringify({fixture:true,stocks:500,render_ms:Number((performance.now()-started).toFixed(2)),html_bytes:Buffer.byteLength(html),watchlist_rows:(html.match(/class="symbol-select"/g)||[]).length,linked_symbol_chips:(html.match(/class="symbol-chip/g)||[]).length}));
