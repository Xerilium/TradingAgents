"""Isolated UI replay of the actual saved META choice review; no backend calls."""
import json
from pathlib import Path
import ui_gate_browser_fixture as fixture
from tradingagents.web.laya_review import QUESTION_CONTRACT_VERSION, RESERVE, approved_review

root = Path(__file__).resolve().parents[1]
packet = json.loads((root / '.paper-desk/laya-saved-packet-review.json').read_text(encoding='utf-8'))
receipt = json.loads((root / '.paper-desk/laya-control-cachefix-saved_meta-forward.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'verified_transport'
audit = {'question_contract_version': QUESTION_CONTRACT_VERSION,
         'parameters': receipt['parameters'], 'token_budget': receipt['preflight'],
         'reserve_tokens': RESERVE, 'summary_attempts': 1}
laya = dict(receipt['result'], question_contract_version=QUESTION_CONTRACT_VERSION)
laya['auto_execute'] = approved_review(laya, audit)
result = dict(symbol='META', status='completed', rating=packet['source']['rating'],
              reports=packet['source']['reports'], laya_review=audit, laya=laya)
seed = "fixtureState.runs[0].symbols=['META'];fixtureState.runs[0].results=[" + json.dumps(result, ensure_ascii=True) + "];fixtureState.runs[0].counts={completed:1};"
fixture.BOOT = fixture.BOOT.replace('window.fetch=async', seed + '\nwindow.fetch=async')
if __name__ == '__main__':
    fixture.HTTPServer(('127.0.0.1', 18765), fixture.Handler).serve_forever()
