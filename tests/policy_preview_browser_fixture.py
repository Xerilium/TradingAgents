"""Offline preview/navigation UAT only; every request stays in the fixture."""
from http.server import HTTPServer
from tests import ui_gate_browser_fixture as fixture

fixture.BOOT = fixture.BOOT.replace('window.fetch=async', """
fixtureState.config.name='OFFLINE POLICY PREVIEW';
fixtureState.connection={connected:true,paper_verified:true};
fixtureState.proposals=[{id:'synthetic-policy-preview',symbol:'AAPL',side:'buy',status:'proposed',qty:10,limit_price:100,notional:1000,run_id:'fixture-run',created_at:'2026-10-15T12:00:00Z',reason:'Synthetic preview only; not an executable broker order.'}];
window.fetch=async""")

if __name__ == '__main__':
    HTTPServer(('127.0.0.1',18768),fixture.Handler).serve_forever()
