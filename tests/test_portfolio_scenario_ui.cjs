// Isolated synthetic DOM harness; no desk or network requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('tradingagents/web/static/app.js', 'utf8');
const listeners = {};
let status = {textContent: ''}, exported, request, finish;
const model = {id: 'synthetic-id', inputs: [{symbol: 'MSFT', run_id: 'synthetic-run'}], result: {capital: 200000, allocations: [{symbol: 'MSFT', weight: 0.12}]}};
const document = {
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  getElementById(id) { return id === 'portfolio-scenario-status' ? status : {value: id}; },
  createElement() { return {click() { exported = this; }}; },
};
const context = vm.createContext({document, state: {portfolio_model: model}, Blob, URL: {createObjectURL(blob) { context.blob = blob; return 'blob:synthetic'; }, revokeObjectURL() {}}, setTimeout() {}, api(_path, body) { request = body; return new Promise(resolve => { finish = resolve; }); }, evaluationAction: async () => {}, esc: x => String(x), evaluationItem: null, strategyView: ''});
const exportHandler = source.match(/document\.addEventListener\('click',event=>\{if\(!event\.target\.closest\('#portfolio-model-export'\)\).*?\}\);/);
const scenario = source.slice(source.indexOf('let portfolioScenarioFile='), source.indexOf('function evaluationMarkup()'));
assert.ok(exportHandler && scenario.includes('async function runPortfolioScenario()'));
vm.runInContext(exportHandler[0] + '\n' + scenario, context);
const archive = new Blob([JSON.stringify(model)], {type: 'application/json'});
archive.name = 'original.json';
listeners.change[0]({target: {id: 'portfolio-scenario-model', files: [archive]}});
assert.equal(status.textContent, 'Selected: original.json');
const markupStatus = source.match(/<pre id="portfolio-scenario-status" role="status">'\+esc\(portfolioScenarioStatus\)\+'<\/pre>/);
assert.ok(markupStatus, 'rendered status must use retained state');
status = {textContent: vm.runInContext('portfolioScenarioStatus', context)};
assert.equal(status.textContent, 'Selected: original.json');
(async () => {
  const pending = vm.runInContext('runPortfolioScenario()', context);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(JSON.parse(JSON.stringify(request.model)), model);
  assert.equal(status.textContent, 'Running hindsight scenario…');
  status = {textContent: vm.runInContext('portfolioScenarioStatus', context)};
  assert.equal(status.textContent, 'Running hindsight scenario…');
  finish({id: 'synthetic-result'});
  await pending;
  assert.equal(context.evaluationItem.id, 'synthetic-result');
  assert.equal(context.strategyView, 'results');
  context.api = async () => { throw new Error('synthetic failure'); };
  await vm.runInContext('runPortfolioScenario()', context);
  status = {textContent: vm.runInContext('portfolioScenarioStatus', context)};
  assert.equal(status.textContent, 'synthetic failure');
  listeners.click[0]({target: {closest: selector => selector === '#portfolio-model-export'}});
  assert.equal(exported.download, 'portfolio-model-synthetic-id.json');
  assert.deepEqual(JSON.parse(await context.blob.text()), model);
  console.log('UI isolated harness: selected archive, pending status, result transition, and exact export passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
