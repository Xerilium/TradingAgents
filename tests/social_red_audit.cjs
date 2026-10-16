// Independent offline rendering check; reuses the existing no-network harness.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const harness = fs.readFileSync(path.join(__dirname, 'ui_gate_regressions.cjs'), 'utf8').split('const opened =')[0];
vm.runInNewContext(harness + `
const f = fixture();
const html = f.run("reportSocial({status:'partial',model:'multilingual',sources:{reddit:{status:'deferred',note:'Coverage: 0 of 20 fetched posts classified; 20 retained. Screening deferred: post_budget_exhausted; fetched posts remain available, not a source failure. Unscreened is not neutral.',counts:{bullish:0,bearish:0,neutral:0,unclear:0,off_topic:0,unscreened:20},posts:[]}}})");
assert.match(html, /deferred/);
assert.match(html, /0 of 20 fetched posts classified/);
assert.match(html, /20 retained/);
assert.match(html, /not a source failure/);
assert.match(html, /Unscreened is not neutral/);
assert.doesNotMatch(html, /unavailable/);
console.log('Deferred coverage rendering audit passed; no network access.');
`, {require, __dirname, console, URL, AbortController});
