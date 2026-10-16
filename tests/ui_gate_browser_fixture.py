"""Isolated offline UI fixture. No broker, research, config, or Gateway traffic."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'tradingagents/web/static'
BOOT=r'''
<script>
const fixtureReport=Array.from({length:110},(_,i)=>`Paragraph ${i+1}. Offline research evidence for geometry and keyboard navigation. This is synthetic fixture content only.`).join('\n\n')+'\n\n| Column one | Column two | Column three | Column four | Column five |\n|---|---|---|---|---|\n| Wide evidence | Second observation | Third observation | Fourth observation | Fifth observation |\n\nLAST REPORT PARAGRAPH';
const fixtureState={config:{name:'OFFLINE FIXTURE',universe:['AAPL','META'],allocation_pct:80,max_position_pct:20,reserve_pct:20,max_order_notional:1000,llm_provider:'chatgpt',backend_url:'',deep_think_llm:'deep',quick_think_llm:'quick'},connection:{connected:false,paper_verified:false},quotes:{},proposals:Array.from({length:4},(_,i)=>({id:'p'+i,symbol:'AAPL',status:'ready'})),orders:[],positions:[],research:{},runs:[{id:'fixture-run',status:'completed',symbols:['AAPL','META'],counts:{completed:2},created_at:'2026-10-15T12:00:00Z',results:[{symbol:'AAPL',status:'completed',reports:{market_report:fixtureReport}},{symbol:'META',status:'completed',reports:{news_report:'Synthetic META evidence'}}],events:Array.from({length:12},(_,i)=>({message:'Fixture event '+i,stage:'offline'}))}]};
window.fetch=async(path,opts={})=>{
 const url=String(path);let value;
 if(url.startsWith('/api/state'))value=fixtureState;
 else if(url==='/api/refresh'){fixtureState.connection.connected=true;value=fixtureState;}
 else if(url==='/api/quotes/refresh')value={quotes:{},clock:{is_open:false},quotes_updated_at:new Date().toISOString()};
 else if(url==='/api/config'){if(window.fixtureFailSave)throw Error('Fixture save failed');fixtureState.config=JSON.parse(opts.body);value=fixtureState;}
 else throw Error('Offline fixture blocked '+url);
 return {ok:true,status:200,headers:{get:()=>null},json:async()=>structuredClone(value)};
};
window.setInterval=()=>0;
document.addEventListener('DOMContentLoaded',()=>{
 const bar=document.createElement('div');bar.style='position:fixed;bottom:0;right:0;z-index:10000;background:#172a38;padding:5px';
 bar.innerHTML='<button id="fixture-update">Append final Laya</button><button id="fixture-connect">Connect fixture</button><button id="fixture-fail-save">Fail next save</button>';
 document.body.append(bar);
 document.querySelector('#fixture-update').onclick=()=>{fixtureState.runs[0].results[0].reports.news_report='New report';fixtureState.runs[0].results[0].laya={grade:'ask_human',summary:'Offline final review'};readState();};
 document.querySelector('#fixture-connect').onclick=()=>{fixtureState.connection.connected=true;readState();};
 document.querySelector('#fixture-fail-save').onclick=()=>{window.fixtureFailSave=!window.fixtureFailSave;};
});
</script>
'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  path=self.path.split('?')[0]
  if path=='/':
   data=(ROOT/'index.html').read_text(encoding='utf-8').replace('<script src="/static/lists.js"',BOOT+'<script src="/static/lists.js"').replace('<title>','<title>OFFLINE FIXTURE — ');kind='text/html'
  elif path in ['/static/app.js','/static/lists.js','/static/app.css']:
   data=(ROOT/path.split('/')[-1]).read_text(encoding='utf-8');kind='text/css' if path.endswith('.css') else 'application/javascript'
  else:self.send_error(404);return
  body=data.encode();self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
if __name__=='__main__':HTTPServer(('127.0.0.1',18764),Handler).serve_forever()
