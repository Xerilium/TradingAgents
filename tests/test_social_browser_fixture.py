import json
import subprocess


def test_social_fixture_boot_executes_and_seeds_two_results():
    from tests.social_sentiment_browser_fixture import fixture
    script = fixture.BOOT.replace('<script>', '').replace('</script>', '')
    harness = "const window={};const document={addEventListener(){}};\n" + script
    harness += "\nconsole.log(JSON.stringify(fixtureState.runs[0].results));"
    completed = subprocess.run(['node', '-e', harness], capture_output=True, text=True, timeout=10, check=True)
    results = json.loads(completed.stdout)
    assert [r['symbol'] for r in results] == ['AAPL', 'META']
    assert results[0]['social_sentiment']['sources']['stocktwits']['counts']['bullish'] == 1
    assert results[1]['social_sentiment']['status'] == 'unavailable'
