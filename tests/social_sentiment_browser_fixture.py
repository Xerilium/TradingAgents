"""Offline social UI fixture; synthetic data only, no broker/model/source traffic.

Run: python -m tests.social_sentiment_browser_fixture
Open: http://127.0.0.1:18766/#research
"""
from http.server import HTTPServer
import argparse
import socket
from tests import ui_gate_browser_fixture as fixture

fixture.BOOT = fixture.BOOT.replace(
    "window.fetch=async", """
const social={status:'partial',model:'multilingual',sources:{
 stocktwits:{status:'completed',counts:{bullish:1,bearish:1,neutral:0,unclear:1,off_topic:1,unscreened:0},note:'Synthetic classifications for UI verification only.',posts:[
 {text:'Synthetic: I expect AAPL to rise.',text_sha256:'fixture-bullish-hash',provenance:'Full StockTwits post (synthetic)',status:'classified',stance:'bullish',stance_probability:.92,about_probability:.98,model:'multilingual'},
 {text:'Synthetic: I expect AAPL to fall.',text_sha256:'fixture-bearish-hash',provenance:'Full StockTwits post (synthetic)',status:'classified',stance:'bearish',stance_probability:.94,about_probability:.97,model:'multilingual'},
 {text:'Synthetic: Maybe AAPL?',text_sha256:'fixture-unclear-hash',provenance:'Full StockTwits post (synthetic)',status:'classified',stance:'unclear',stance_probability:.40,about_probability:.75,model:'multilingual'},
 {text:'Synthetic: This is about another company.',text_sha256:'fixture-off-topic-hash',provenance:'Full StockTwits post (synthetic)',status:'off_topic',stance:'unclear',about_probability:.10,model:'multilingual'}]},
 reddit:{status:'unavailable',counts:{bullish:0,bearish:0,neutral:0,unclear:0,off_topic:0,unscreened:2},note:'Synthetic timeout; posts retained unscreened.',posts:[{text:'Synthetic Reddit text retained after timeout.',text_sha256:'fixture-unscreened-hash',provenance:'Reddit excerpt (synthetic)',status:'unscreened',stance:'unclear'},{text:'Synthetic second Reddit post retained.',text_sha256:'fixture-unscreened-two-hash',provenance:'Reddit excerpt (synthetic)',status:'unscreened',stance:'unclear'}]}}};
fixtureState.runs[0].results[0].social_sentiment=social;
fixtureState.runs[0].results[0].laya={contract:{grade:'auto_execute'},answers:{evidence_complete:{value:true}},summary:'Synthetic legacy artifact retained unchanged.'};
fixtureState.runs[0].results[1].social_sentiment={status:'unavailable',model:'multilingual',sources:{reddit:social.sources.reddit}};
fixtureState.research={AAPL:{status:'completed',social_sentiment:social},META:{status:'completed',social_sentiment:fixtureState.runs[0].results[1].social_sentiment}};
window.fetch=async""",
)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18766)
    args = parser.parse_args()
    server = HTTPServer(('127.0.0.1',args.port),fixture.Handler, bind_and_activate=False)
    server.allow_reuse_address = False
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.server_bind()
    server.server_activate()
    server.serve_forever()
