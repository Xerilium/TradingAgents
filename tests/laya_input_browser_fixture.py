"""Read-only exact saved audit fixture; actual app assets, no backend traffic."""
import json
from pathlib import Path
import ui_gate_browser_fixture as fixture

packet = json.loads((Path(__file__).resolve().parents[1] / '.paper-desk/laya-saved-packet-review.json').read_text(encoding='utf-8'))
result = dict(symbol='META', status='completed', rating=packet['source']['rating'],
              reports=packet['source']['reports'], laya_review=packet['audit'])
seed = "fixtureState.runs[0].symbols=['META'];fixtureState.runs[0].results=[" + json.dumps(result, ensure_ascii=True) + "];fixtureState.runs[0].counts={completed:1};"
fixture.BOOT = fixture.BOOT.replace('window.fetch=async', seed + '\nwindow.fetch=async')
if __name__ == '__main__':
    fixture.HTTPServer(('127.0.0.1', 18765), fixture.Handler).serve_forever()
