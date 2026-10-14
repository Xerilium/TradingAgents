"""Actual desk HTTP/UI with an offline Gateway; expires after ten minutes."""
import asyncio
import json
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tradingagents.integrations.maenifold import MaenifoldGateway
from tradingagents.web.server import DeskServer

root=Path('.impeccable/review')
attempts={}
stamp=datetime.now(UTC)
bars=[{'t':(stamp-timedelta(days=25-i)).isoformat(),'o':100+i,'h':103+i,'l':99+i,'c':102+i,'v':1000} for i in range(25)]
class Transport:
    async def call_tool(self,name,args):
        symbol=args['parameters']['symbols']
        attempts[symbol]=attempts.get(symbol,0)+1
        (root/'retry-uat-counts.json').write_text(json.dumps(attempts))
        if symbol=='NVDA' or symbol=='META' and attempts[symbol]<=3:
            return {'error':{'code':429,'retry_after':1}}
        return {'symbol':symbol,'bars':bars}
gateway=MaenifoldGateway(transport=Transport())
config={'name':'OFFLINE UAT · simulated rate limits','universe':['AAPL','META','NVDA'],
        'llm_provider':'chatgpt','quick_think_llm':'test','deep_think_llm':'test',
        'allocation_pct':70,'reserve_pct':20,'max_position_pct':15,'max_order_notional':5000}
state={'config':config,'config_revision':1,'connection':{'connected':True,'paper_verified':False,'message':'OFFLINE UAT: synthetic data. No broker, model, or orders.'},
       'account':{'equity':100000,'cash':100000,'buying_power':100000},'positions':[],'orders':[],'runs':[],
       'research':{},'proposals':[],'errors':[],'history':{},'bars':{'META':[]},'quotes':{},'updated_at':stamp.isoformat()}
class Service:
    def state(self,**kwargs): return state
    def chart(self,symbol,**kwargs):
        return asyncio.run(gateway._call('GatewayExecute',{'domain':'alpaca','command':'get_stock_bars','parameters':{'symbols':symbol}}))
server=DeskServer(('127.0.0.1',8090),Service())
timer=threading.Timer(600,server.shutdown)
timer.daemon=True
timer.start()
try: server.serve_forever(poll_interval=.25)
finally: server.server_close()
