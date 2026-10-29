'use strict';

const workflowEditor = {names: [], active: '', name: '', files: {}, saved: {}, revision: null, file: '', selected: '', loading: false, initialized: false, message: '', error: false, diagram: null, diagramFiles: null, prompt: '', saveAsOpen: false, saveAsName: '', saveAsError: '', view: 'prompts', node: '', search: '', tools: 'idle'};
const workflowDirty = () => JSON.stringify(workflowEditor.files) !== JSON.stringify(workflowEditor.saved);
function workflowCanLeave() { if (!workflowDirty()) return true; if (!confirm('Discard unsaved workflow changes?')) return false; workflowResetEditorStates(); workflowEditor.files = {...workflowEditor.saved}; workflowEditor.message = 'Changes discarded.'; workflowEditor.error = false; return true; }
window.addEventListener('beforeunload', event => { if (workflowDirty()) { event.preventDefault(); event.returnValue = ''; } });
function workflowRefresh() { if (activePage === 'workflows') { workflowCaptureEditorStates(); render({force: true}); } }
let workflowPollAt = 0, workflowPollPending = false, workflowCatalogGeneration = 0, workflowPreviewGeneration = 0;
async function workflowPoll() {
  if (workflowEditor.loading || workflowPollPending || Date.now() < workflowPollAt) return;
  workflowPollAt = Date.now() + 30000; workflowPollPending = true;
  const generation = workflowCatalogGeneration;
  try {
    const result = await api('/api/workflows');
    if (workflowEditor.loading || generation !== workflowCatalogGeneration) return;
    workflowEditor.active = result.active || '';
    const label = document.getElementById('workflow-active');
    if (activePage === 'workflows' && label) label.textContent = workflowEditor.active || 'None selected';
    const button = document.getElementById('workflow-activate');
    if (activePage === 'workflows' && button) button.disabled = workflowDirty() || workflowEditor.active === workflowEditor.name;
  } catch { const label = document.getElementById('workflow-active'); if (activePage === 'workflows' && label) label.textContent = (workflowEditor.active || 'None selected') + ' (last known; refresh failed)'; }
  finally { workflowPollPending = false; }
}
function workflowError(error) { return error.status === 409 ? `This workflow changed in another session. Your draft is still here. Use Save as to preserve your complete draft as a new workflow, or discard it and load the latest version. ${error.message}` : error.message; }
async function workflowList() {
  if (workflowEditor.loading) return;
  workflowEditor.loading = true; workflowRefresh();
  try {
    const result = await api('/api/workflows');
    workflowEditor.names = result.workflows; workflowEditor.active = result.active || '';
    workflowEditor.selected = workflowEditor.selected || workflowEditor.active || workflowEditor.names[0] || '';
    workflowEditor.initialized = true; workflowPollAt = Date.now() + 30000;
    if (workflowEditor.error && !workflowEditor.name) { workflowEditor.message = ''; workflowEditor.error = false; }
  } catch (error) { workflowEditor.initialized = true; workflowEditor.message = error.message; workflowEditor.error = true; }
  finally { workflowEditor.loading = false; workflowRefresh(); }
}
function workflowSetBundle(result) {
  workflowEditor.name = result.name; workflowEditor.selected = result.name;
  workflowEditor.files = {...result.files}; workflowEditor.saved = {...result.files};
  workflowEditor.diagram = result.diagram || null; workflowEditor.diagramFiles = JSON.stringify(result.files); workflowEditor.prompt = Object.hasOwn(result.files, workflowEditor.prompt) ? workflowEditor.prompt : Object.keys(result.files).find(path => path !== 'workflow.yaml') || ''; workflowEditor.revision = result.revision; workflowEditor.file = Object.hasOwn(result.files, workflowEditor.file) ? workflowEditor.file : Object.keys(result.files).find(path => path === 'workflow.yaml') || Object.keys(result.files)[0] || '';
  if (result.active !== undefined) workflowEditor.active = result.active || '';
}
async function workflowLoad() {
  const name = $('#workflow-select')?.value;
  if (!name || (workflowDirty() && !confirm('Discard unsaved workflow changes and load the selected workflow?'))) return;
  ++workflowCatalogGeneration; ++workflowPreviewGeneration;
  workflowEditor.loading = true; workflowRefresh();
  try { const result = await api('/api/workflows?name=' + encodeURIComponent(name)); workflowResetEditorStates(); workflowSetBundle(result); workflowEditor.message = 'Workflow loaded.'; workflowEditor.error = false; }
  catch (error) { workflowEditor.message = workflowError(error); workflowEditor.error = true; }
  finally { workflowEditor.loading = false; workflowRefresh(); }
}
async function workflowAction(action, newName) {
  if (!workflowEditor.name || workflowEditor.loading) return;
  let name = workflowEditor.name;
  if (action === 'save_as') {
    name = newName || ''; workflowEditor.saveAsName = name;
    workflowEditor.saveAsError = !/^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$/.test(name) || / $/.test(name) ? 'Use 1–64 letters, numbers, spaces, underscores or hyphens; start with a letter or number.' : /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(name) ? 'Choose a different workflow name.' : '';
    if (workflowEditor.saveAsError) { $('#workflow-save-as-error').textContent = workflowEditor.saveAsError; return; }
  }
  if (action === 'activate' && workflowDirty()) { workflowEditor.message = 'Save or discard changes before selecting this workflow for new research.'; workflowEditor.error = true; workflowRefresh(); return; }
  const body = action === 'activate' ? {action, name, revision: workflowEditor.revision} : action === 'save_as' ? {action, name, files: workflowEditor.files} : {action, name, files: workflowEditor.files, revision: workflowEditor.revision};
  ++workflowCatalogGeneration; ++workflowPreviewGeneration;
  workflowEditor.loading = true; workflowRefresh();
  try {
    const result = await api('/api/workflows', body);
    workflowSetBundle(result); workflowEditor.saveAsOpen = false; workflowEditor.saveAsError = '';
    if (!workflowEditor.names.includes(result.name)) workflowEditor.names.push(result.name);
    workflowEditor.message = (action === 'activate' ? 'Selected for new research.' : 'Workflow saved.') + (result.warning ? ' ' + result.warning : ''); workflowEditor.error = false;
  } catch (error) { workflowEditor.message = workflowError(error); workflowEditor.error = true; if (action === 'save_as') workflowEditor.saveAsError = workflowError(error); }
  finally { workflowEditor.loading = false; workflowRefresh(); }
}
function workflowPromptLabel(path) {
  return path.replace(/^prompts\//, '').replace(/\.[^.]+$/, '').replace(/_/g, ' ');
}
const workflowPromptDescriptions = {
  aggressive_debator: 'Argues for a more aggressive risk position.',
  conservative_debator: 'Argues for a more conservative risk position.',
  neutral_debator: 'Balances the competing risk arguments.',
  bull_researcher: 'Develops the bullish research argument.',
  bear_researcher: 'Develops the bearish research argument.',
  market_analyst: 'Guides technical market analysis.',
  news_analyst: 'Guides analysis of news and macro developments.',
  sentiment_analyst: 'Guides social sentiment analysis.',
  fundamentals_analyst: 'Guides company fundamentals analysis.',
  fundamentals_analyst_etf: 'Guides fundamentals analysis for an ETF.',
  fundamentals_review_etf: 'Review instructions for ETF analysis.',
  fundamentals_review_stock: 'Review instructions for stock analysis.',
  fundamentals_review_tools: 'Tool guidance for fundamentals review.',
  analyst_wrapper: 'Frames an analyst task and available tools.',
  wrap_up: 'Requests a final analyst report.',
  sentiment_wrapper: 'Frames the sentiment analyst task.',
  sentiment_reddit_stock: 'Reddit context for stock sentiment.',
  sentiment_reddit_crypto: 'Reddit context for crypto sentiment.',
  sentiment_reddit_crypto_specific: 'Instrument-specific crypto Reddit context.',
  research_manager: 'Directs the research manager’s synthesis.',
  research_manager_desk: 'Desk-specific research manager instructions.',
  trader_system: 'Sets the trader’s role and proposal task.',
  trader_system_desk: 'Desk-specific trader instructions.',
  trader_user: 'Presents inputs to the trader.',
  trader_user_desk: 'Presents desk inputs to the trader.',
  trader_grounding: 'Grounds the trader in available evidence.',
  trader_grounding_desk: 'Desk-specific grounding for the trader.',
  trader_report_section: 'Frames a report section for the trader.',
  portfolio_manager: 'Directs the final portfolio decision.',
  portfolio_manager_desk: 'Desk-specific portfolio decision instructions.',
  portfolio_lessons: 'Frames lessons for the portfolio manager.',
  joint_portfolio: 'Directs a joint portfolio proposal.',
  joint_allocations: 'Frames allocation choices in a joint proposal.',
  joint_cash_rationale: 'Requests reasoning for cash in a joint proposal.',
  allocation_weight: 'Describes an allocation weight.',
  allocation_rationale: 'Describes the reason for an allocation.',
  allocation_entry_conditions: 'Describes conditions for entering an allocation.',
  desk_quote_context: 'Frames the desk’s quote context.',
  desk_historical_quote: 'Frames a historical quote for the desk.',
  desk_execution_policy: 'Describes the desk execution policy.',
  desk_exclude_fred: 'Guidance about excluding FRED data.',
  no_external_tools: 'Instructions for a turn without external tools.',
  shared_language: 'Specifies the response language.',
  shared_instrument: 'Identifies the instrument and ticker.',
  shared_historical_identity: 'Identifies an instrument at a historical date.',
  shared_resolved_identity: 'Presents resolved instrument identity details.',
  shared_etf: 'Provides ETF-specific context.',
  shared_crypto: 'Provides crypto-specific context.',
  shared_snapshot: 'Identifies an available snapshot by digest.',
  shared_snapshot_missing: 'Explains that a snapshot is unavailable.',
  shared_report_absent: 'Identifies a missing source report.',
  shared_portfolio_missing: 'Explains that portfolio context is unavailable.',
  shared_portfolio_holdings_missing: 'Explains that portfolio holdings are unavailable.',
  shared_opponent_opening: 'Introduces an opposing debate participant.',
  shared_evidence_reference: 'Labels an evidence reference.',
  shared_evidence_wrapper: 'Frames the text of a piece of evidence.',
  shared_request_inputs: 'Requests inputs through tools.',
  shared_duplicate_filing: 'Identifies a previously seen filing.',
  shared_tools_spent: 'Signals that the tool allowance is exhausted.',
  shared_called_tools: 'Records tools called in a turn.',
  shared_tool_returned: 'Identifies a returned tool response.',
  shared_memory_base: 'Introduces memory guidance.',
  shared_memory_tools: 'Describes available memory tools.',
  shared_memory_build_context: 'Guidance for building memory context.',
  shared_memory_find_similar: 'Guidance for finding related memory concepts.',
  shared_memory_search: 'Guidance for searching memories.',
  shared_memory_read: 'Guidance for reading a memory.',
  shared_memory_thinking: 'Guidance for sequential thinking.',
  shared_memory_tool_instruction: 'Frames an individual memory tool instruction.',
  shared_memory_no_graph: 'Guidance when graph tools are unavailable.',
  shared_memory_unavailable: 'Guidance when memory is unavailable.',
  shared_memory_final: 'Closing guidance for memory use.'
};
function workflowPromptDescription(path) {
  const name = path.replace(/^prompts\//, '').replace(/\.[^.]+$/, '');
  if (name.startsWith('schema_')) {
    const match = name.match(/^schema_([^_]+)_(.+)$/);
    if (match) return `Describes the ${match[2].replace(/_/g, ' ')} field of ${match[1].replace(/([a-z])([A-Z])/g, '$1 $2')}.`;
  }
  return workflowPromptDescriptions[name] || 'Prompt file for ' + workflowPromptLabel(path) + '.';
}
function workflowPromptGroup(path) {
  const name = path.replace(/^prompts\//, '');
  if (name.startsWith('shared_')) return 'Shared context and tools';
  if (name.startsWith('schema_')) return 'Output schemas';
  if (/(conditional|memory|tool|follow|revision|no_graph)/i.test(name)) return 'Conditional fragments';
  return 'Primary and other prompts';
}
function workflowPromptOptions(w) {
  const groups = {}, query = w.search.trim().toLowerCase();
  Object.keys(w.files).filter(path => path !== 'workflow.yaml' && (!query || `${path} ${workflowPromptLabel(path)} ${workflowPromptDescription(path)}`.toLowerCase().includes(query))).sort().forEach(path => (groups[workflowPromptGroup(path)] ||= []).push(path));
  return Object.entries(groups).map(([group, paths]) => `<optgroup label="${esc(group)}">${paths.map(path => `<option value="${esc(path)}" ${path === w.prompt ? 'selected' : ''}>${esc(workflowPromptLabel(path))} — ${esc(workflowPromptDescription(path))}</option>`).join('')}</optgroup>`).join('');
}
function workflowRelated() {
  const node = workflowEditor.diagram?.nodes?.[workflowEditor.node];
  if (!node) return '<span class="muted">Select an agent node in the diagram (click or press Enter/Space) to inspect its primary prompt, shared context fragments, and output schema.</span>';
  const groups = node.prompt_groups || {};
  const agent = (groups.agent || (node.prompt_files || []).map((file, index) => ({file, description: index === 0 ? 'Primary prompt' : 'Related agent prompt'}))).filter(item => Object.hasOwn(workflowEditor.files, item.file));
  const shared = (groups.shared || []).filter(item => Object.hasOwn(workflowEditor.files, item.file));
  const schema = (groups.schema || []).filter(item => Object.hasOwn(workflowEditor.files, item.file));
  const buttons = entries => `<div class="workflow-related-files">${entries.map(item => `<button type="button" class="button workflow-related-file" data-prompt="${esc(item.file)}"><strong>${esc(workflowPromptLabel(item.file))}</strong><span>${esc(item.description || workflowPromptDescription(item.file))}</span></button>`).join('')}</div>`;
  const extra = (label, entries) => entries.length ? `<details class="workflow-related-group"><summary>${esc(label)} (${entries.length})</summary>${buttons(entries)}</details>` : '';
  return `<strong>${esc(node.name)}</strong><span>${esc(node.caption || (node.synthetic ? 'Visual summary, not a separate agent.' : 'Workflow agent.'))}</span>${agent.length ? buttons(agent) : '<span>No agent-specific prompt file.</span>'}${extra('Shared context and tools', shared)}${extra('Output schema fields', schema)}`;
}
function workflowShowNode(id) {
  workflowEditor.node = id;
  const detail = $('#workflow-node-detail'); if (detail) { detail.innerHTML = workflowRelated(); detail.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => workflowSelectPrompt(button.dataset.prompt))); }
  document.querySelectorAll('.workflow-node-action').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.workflowNode === id)));
}
function workflowPreviewState() {
  if (!workflowEditor.diagram) return 'No preview yet';
  if (workflowEditor.diagramFiles !== JSON.stringify(workflowEditor.files)) return 'Preview is stale';
  return workflowDirty() ? 'Preview of draft' : 'Preview of loaded workflow';
}
function workflowUpdateState() {
  const feedback = $('#workflow-feedback');
  if (feedback) { feedback.textContent = workflowDirty() ? 'Unsaved changes' : 'Saved workflow'; feedback.className = 'muted'; }
  const discard = $('#workflow-discard'), activate = $('#workflow-activate'), status = $('#workflow-preview-status');
  if (discard) discard.disabled = !workflowDirty();
  const save = $('#workflow-save'); if (save) save.disabled = !workflowDirty() || workflowEditor.loading;
  if (activate) activate.disabled = workflowDirty() || workflowEditor.active === workflowEditor.name;
  if (status) status.textContent = workflowPreviewState();
}
async function workflowPreview() {
  const button = $('#workflow-preview'), status = $('#workflow-preview-status');
  const files = {...workflowEditor.files}, snapshot = JSON.stringify(files), name = workflowEditor.name, generation = ++workflowPreviewGeneration;
  const current = () => generation === workflowPreviewGeneration && workflowEditor.name === name && button.isConnected;
  button.disabled = true; status.textContent = 'Validating draft…';
  try {
    const result = await api('/api/workflows', {action: 'preview', files});
    if (!current()) return;
    workflowEditor.diagram = result.diagram; workflowEditor.diagramFiles = snapshot;
    await workflowRenderDiagram();
    if (current()) status.textContent = workflowPreviewState();
  } catch (error) { if (current()) status.textContent = workflowPreviewState() + '. Preview unavailable: ' + workflowError(error); }
  finally { if (current()) button.disabled = false; }
}
let workflowDiagramSequence = 0, workflowDiagramObserver, workflowDiagramRemovalObserver, workflowFitMode = true, workflowDiagramScroll = null;
async function workflowRenderDiagram() {
  const target = $('#workflow-diagram'), diagram = workflowEditor.diagram;
  if (!target || !diagram) return;
  const sequence = ++workflowDiagramSequence;
  try {
    const styles = getComputedStyle(target);
    const token = name => styles.getPropertyValue(name).trim();
    const svg = await window.WorkflowTools.renderDiagram('workflow-graph-' + sequence, diagram.mermaid, {primaryColor:token('--paper'), primaryTextColor:token('--ink'), primaryBorderColor:token('--accent'), lineColor:token('--muted'), secondaryColor:token('--accent-wash'), tertiaryColor:token('--paper'), background:token('--ground'), fontFamily:styles.fontFamily});
    if (sequence !== workflowDiagramSequence || !target.isConnected) return;
    target.innerHTML = svg;
    workflowDiagramObserver?.disconnect(); workflowDiagramRemovalObserver?.disconnect();
    if (workflowFitMode) workflowFitDiagram(target); else workflowApplyZoom();
    if (workflowDiagramScroll) { target.scrollLeft = workflowDiagramScroll.left; target.scrollTop = workflowDiagramScroll.top; }
    else target.scrollLeft = Math.max(0, (target.scrollWidth - target.clientWidth) / 2);
    target.addEventListener('scroll', () => { workflowDiagramScroll = {left:target.scrollLeft, top:target.scrollTop}; }, {passive:true});
    const resizeObserver = new ResizeObserver(() => { if (target.isConnected && workflowFitMode) workflowFitDiagram(target); });
    workflowDiagramObserver = resizeObserver; resizeObserver.observe(target);
    const removalObserver = new MutationObserver(() => { if (!target.isConnected) { resizeObserver.disconnect(); removalObserver.disconnect(); } });
    workflowDiagramRemovalObserver = removalObserver; removalObserver.observe(document.getElementById('main'), {childList:true, subtree:true});
    for (const [id, node] of Object.entries(diagram.nodes || {})) {
      const el = Array.from(target.querySelectorAll('g.node')).find(item => item.id === id || item.id.startsWith('flowchart-' + id + '-') || item.id.startsWith('workflow-graph-' + sequence + '-flowchart-' + id + '-'));
      const path = (node.prompt_files || []).find(file => Object.hasOwn(workflowEditor.files, file));
      if (!el) continue;
      el.setAttribute('tabindex', '0'); el.setAttribute('role', 'button'); el.setAttribute('aria-label', `${node.name}: ${path ? 'show details and open primary prompt' : 'show details'}`); el.classList.add('workflow-node-action'); el.dataset.workflowNode = id; el.setAttribute('aria-pressed', String(workflowEditor.node === id));
      const activate = () => { workflowShowNode(id); if (path) { workflowSetView('prompts'); workflowSelectPrompt(path); } };
      el.addEventListener('click', activate); el.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); } });
    }
  } catch (error) { if (sequence === workflowDiagramSequence && target.isConnected) target.textContent = 'Unable to render the workflow: ' + error.message; }
}
let workflowYamlEditor, workflowPromptEditor, workflowEditorStates = {}, workflowZoom = 1;
function workflowCaptureEditorStates() {
  const diagram = $('#workflow-diagram'); if (diagram?.querySelector('svg')) workflowDiagramScroll = {left:diagram.scrollLeft, top:diagram.scrollTop};
  if (workflowYamlEditor) workflowEditorStates['workflow.yaml'] = workflowYamlEditor.getState();
  if (workflowPromptEditor && workflowEditor.prompt) workflowEditorStates[workflowEditor.prompt] = workflowPromptEditor.getState();
}
function workflowResetEditorStates() {
  workflowYamlEditor?.destroy(); workflowPromptEditor?.destroy();
  workflowYamlEditor = workflowPromptEditor = null; workflowEditorStates = {};
}
function workflowApplyZoom() {
  const target = $('#workflow-diagram'), svg = target?.querySelector('svg');
  if (!svg) return;
  const naturalWidth = svg.viewBox?.baseVal?.width || 800;
  svg.style.maxWidth = 'none'; svg.style.width = Math.round(naturalWidth * workflowZoom) + 'px'; svg.style.height = 'auto';
  const label = $('#workflow-zoom-level'); if (label) label.textContent = Math.round(workflowZoom * 100) + '%';
}
function workflowFitDiagram(target) {
  const svg = target?.querySelector('svg'); if (!svg) return;
  const naturalWidth = svg.viewBox?.baseVal?.width || 800;
  workflowZoom = Math.max(.875, Math.min(2, (target.clientWidth - 32) / naturalWidth));
  workflowApplyZoom();
}
function workflowChangeZoom(mode) {
  const target = $('#workflow-diagram'), svg = target?.querySelector('svg'); if (!svg) return;
  workflowFitMode = mode === 'fit';
  if (workflowFitMode) { workflowFitDiagram(target); target.scrollLeft = Math.max(0, (target.scrollWidth - target.clientWidth) / 2); }
  else { workflowZoom = Math.max(.2, Math.min(2, workflowZoom + mode)); workflowApplyZoom(); }
}
function workflowSelectPrompt(path) {
  if (!Object.hasOwn(workflowEditor.files, path)) return;
  if (workflowPromptEditor && workflowEditor.prompt) workflowEditorStates[workflowEditor.prompt] = workflowPromptEditor.getState();
  workflowEditor.prompt = path;
  const select = $('#workflow-prompt-select'); if (select) select.value = path;
  const label = $('#workflow-prompt-path'); if (label) label.textContent = path;
  const guidance = $('#workflow-prompt-guidance'); if (guidance) guidance.textContent = workflowPromptGuidance(path);
  workflowPromptEditor?.destroy();
  workflowPromptEditor = window.WorkflowTools.createEditor($('#workflow-prompt-editor'), {text: workflowEditor.files[path], state: workflowEditorStates[path], language: 'markdown', label: 'Prompt contents', readOnly: workflowEditor.loading, onChange: value => { workflowEditor.files[workflowEditor.prompt] = value; workflowUpdateState(); }});
}
function workflowPromptGuidance(path) {
  return workflowPromptDescription(path) + ' This is an individual file; runtime may combine it with other fragments.';
}
function workflowSetView(view) {
  workflowEditor.view = view;
  const controls = $('#workflow-prompt-controls'); if (controls) controls.hidden = view !== 'prompts';
  const yamlGuidance = $('#workflow-yaml-guidance'); if (yamlGuidance) yamlGuidance.hidden = view !== 'yaml';
  for (const name of ['prompts', 'yaml']) {
    const panel = document.getElementById('workflow-' + name + '-panel'), tab = document.getElementById('workflow-' + name + '-tab');
    if (panel) panel.hidden = name !== view;
    if (tab) { tab.setAttribute('aria-selected', String(name === view)); tab.tabIndex = name === view ? 0 : -1; }
  }
}
function renderWorkflows() {
  if (!workflowEditor.initialized && !workflowEditor.loading) queueMicrotask(workflowList);
  const w = workflowEditor, disabled = w.loading ? 'disabled' : '', loaded = !!w.name;
  const toolMessage = w.tools === 'error' ? 'Editor tools could not load. Your draft is preserved.' : 'Loading editor tools…';
  return `<section class="settings-section workflow-workspace"><div class="workflow-header">${pageHeader('Workflows', 'Inspect and edit the workflow used for research.')}
    <div class="workflow-toolbar"><div class="workflow-identities"><span>Editing: <strong>${esc(w.name || 'None')}</strong></span><span>Active: <strong id="workflow-active">${esc(w.active || 'None selected')}</strong></span></div><div class="workflow-load-controls"><div class="field"><label for="workflow-select">Load saved workflow</label><select id="workflow-select" class="form-control" ${disabled}>${w.names.map(name => `<option value="${esc(name)}" ${name === w.selected ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></div><button id="workflow-load" class="button" ${disabled} ${w.names.length ? '' : 'disabled'}>Load</button></div></div>
    ${!loaded ? `<p id="workflow-feedback" class="${w.error ? 'form-error' : 'muted'}" role="status" aria-live="polite">${esc(w.message || (w.loading ? 'Loading workflows…' : loaded ? (workflowDirty() ? 'Unsaved changes' : 'Saved workflow') : 'Choose a saved workflow and select Load to begin.'))}</p>` : ''}${w.error && !loaded ? `<button id="workflow-retry" class="button" ${disabled}>Try again</button>` : ''}
    ${!loaded ? `</div><div class="empty-state workflow-empty-state"><h2>Load a research workflow</h2><p>The workflow shows the Mermaid agent flow, 12 role-grouped prompt templates, and the stage and debate round limits in workflow.yaml. It shapes how analysts, bull and bear researchers, the trader, and risk debaters run on future research cycles. Loading it does not start a run.</p><div class="button-group"><button id="workflow-empty-load" class="button button-primary" type="button" ${disabled} ${w.names.length ? '' : 'disabled'}>Load ${esc(w.selected || w.active || 'Default')} workflow</button><a class="button" href="#research">Open Research</a></div></div>` : ''}
    ${loaded ? `<div class="workflow-actions"><p id="workflow-feedback" class="${w.error ? 'form-error' : 'muted'}" role="status" aria-live="polite">${esc(w.message || (w.loading ? 'Loading workflows…' : loaded ? (workflowDirty() ? 'Unsaved changes' : 'Saved workflow') : 'Choose a saved workflow and select Load to begin.'))}</p><div class="button-group"><button id="workflow-save" class="button button-primary" ${disabled} ${workflowDirty() ? '' : 'disabled'}>Save</button><button id="workflow-save-as" class="button" ${disabled}>Save as</button><button id="workflow-discard" class="button" ${disabled} ${workflowDirty() ? '' : 'disabled'}>Discard changes</button><button id="workflow-activate" class="button" ${disabled} ${w.active === w.name && !workflowDirty() ? 'disabled' : ''}>Use for new research</button></div><form id="workflow-save-as-form" class="workflow-save-as" ${w.saveAsOpen ? '' : 'hidden'}><label for="workflow-save-as-name">New workflow name</label><input id="workflow-save-as-name" class="form-control" value="${esc(w.saveAsName)}" autocomplete="off"><button class="button" type="submit">Save copy</button><button id="workflow-save-as-cancel" class="button" type="button">Cancel</button><span id="workflow-save-as-error" class="form-error" role="alert">${esc(w.saveAsError)}</span></form></div>
    </div>${w.tools !== 'ready' ? `<div class="workflow-tool-state" role="status">${esc(toolMessage)} ${w.tools === 'error' ? '<button id="workflow-tools-retry" class="button">Try again</button>' : ''}</div>` : `<div class="workflow-pane-toolbars"><div class="workflow-flow-toolbar"><div class="workflow-section-head"><div><h2 id="workflow-flow-title">Workflow flow</h2><p id="workflow-preview-status" class="muted" role="status">${esc(workflowPreviewState())}</p></div><button id="workflow-preview" class="button" ${disabled}>Preview changes</button></div><div class="workflow-flow-controls"><details class="workflow-flow-details"><summary>About this diagram</summary><p>Diamonds summarize debate rounds; runtime checks occur after each turn. Boundary and join nodes are visual summaries. This desktop view shows selected analysts; optional CLI local memory is not active here. Saving or selecting a workflow does not start research.</p></details><div class="workflow-zoom" aria-label="Diagram zoom"><button id="workflow-zoom-out" class="button button-small" type="button" aria-label="Zoom out">−</button><span id="workflow-zoom-level">${Math.round(workflowZoom * 100)}%</span><button id="workflow-zoom-in" class="button button-small" type="button" aria-label="Zoom in">+</button><button id="workflow-zoom-fit" class="button button-small" type="button">Fit width</button></div><button type="button" class="workflow-inspector-jump" id="workflow-inspector-jump">Agent prompts</button></div></div><div class="workflow-inspector-controls"><div class="workflow-tabs" role="tablist" aria-label="Inspector view"><button id="workflow-prompts-tab" type="button" role="tab" aria-controls="workflow-prompts-panel" aria-selected="${w.view === 'prompts'}" tabindex="${w.view === 'prompts' ? '0' : '-1'}">Prompts</button><button id="workflow-yaml-tab" type="button" role="tab" aria-controls="workflow-yaml-panel" aria-selected="${w.view === 'yaml'}" tabindex="${w.view === 'yaml' ? '0' : '-1'}">Workflow YAML</button></div><div id="workflow-prompt-controls" class="workflow-prompt-controls" ${w.view === 'prompts' ? '' : 'hidden'}><div class="workflow-catalog"><div class="field"><label for="workflow-prompt-search">Search prompt files</label><input id="workflow-prompt-search" class="form-control" type="search" value="${esc(w.search)}" placeholder="Search name, path or purpose"></div><div class="field"><label for="workflow-prompt-select">Prompt file (${Object.keys(w.files).filter(path => path !== 'workflow.yaml').length})</label><select id="workflow-prompt-select" class="form-control" ${disabled}>${workflowPromptOptions(w)}</select></div></div><details class="workflow-details"><summary>Details</summary><div class="workflow-disclosure-content"><details class="workflow-node-disclosure"><summary>Related agent files</summary><div id="workflow-node-detail" class="workflow-node-detail" aria-live="polite">${workflowRelated()}</div></details><div class="workflow-guidance"><p id="workflow-prompt-path" class="workflow-path">${esc(w.prompt)}</p><p id="workflow-prompt-guidance" class="workflow-help">${esc(workflowPromptGuidance(w.prompt))} Groups help you browse; they do not describe the assembled runtime prompt. Placeholders in braces may be supplied at runtime.</p></div></div></details></div><details id="workflow-yaml-guidance" class="workflow-yaml-guidance" ${w.view === 'yaml' ? '' : 'hidden'}><summary>Workflow definition details</summary><div class="workflow-disclosure-content"><p>Configure stages, model tiers and round limits in workflow.yaml.</p></div></details></div></div><div class="workflow-studio"><section class="workflow-flow" aria-labelledby="workflow-flow-title"><div id="workflow-diagram" class="workflow-diagram" aria-label="Workflow flow diagram">${w.diagram ? 'Rendering workflow…' : 'Preview the workflow to see its validated flow.'}</div></section>
    <section id="workflow-inspector" class="workflow-inspector" aria-label="Workflow inspector" tabindex="-1"><section id="workflow-prompts-panel" class="workflow-editor-panel" role="tabpanel" aria-labelledby="workflow-prompts-tab" ${w.view === 'prompts' ? '' : 'hidden'}><div id="workflow-prompt-editor" class="workflow-code"></div></section><section id="workflow-yaml-panel" class="workflow-editor-panel" role="tabpanel" aria-labelledby="workflow-yaml-tab" ${w.view === 'yaml' ? '' : 'hidden'}><div id="workflow-yaml-editor" class="workflow-code"></div></section></section></div>`}` : ''}</section>`;
}
function bindWorkflows() {
  if (workflowEditor.tools === 'idle') {
    workflowEditor.tools = 'loading';
    window.ensureWorkflowTools().then(() => { workflowEditor.tools = 'ready'; if (activePage === 'workflows') workflowRefresh(); }).catch(() => { workflowEditor.tools = 'error'; if (activePage === 'workflows') workflowRefresh(); });
  }
  $('#workflow-tools-retry')?.addEventListener('click', () => { workflowEditor.tools = 'idle'; workflowRefresh(); });
  for (const view of ['prompts', 'yaml']) $('#workflow-' + view + '-tab')?.addEventListener('click', () => workflowSetView(view));
  document.querySelectorAll('.workflow-tabs [role=tab]').forEach(tab => tab.addEventListener('keydown', event => { if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); const view = workflowEditor.view === 'prompts' ? 'yaml' : 'prompts'; workflowSetView(view); $('#workflow-' + view + '-tab')?.focus(); } }));
  $('#workflow-prompt-search')?.addEventListener('input', event => { workflowEditor.search = event.target.value; const select = $('#workflow-prompt-select'); select.innerHTML = workflowPromptOptions(workflowEditor); if (Array.from(select.options).some(option => option.value === workflowEditor.prompt)) select.value = workflowEditor.prompt; else select.selectedIndex = -1; });
  $('#workflow-node-detail')?.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => workflowSelectPrompt(button.dataset.prompt)));
  $('#workflow-retry')?.addEventListener('click', workflowList);
  $('#workflow-select')?.addEventListener('change', event => { workflowEditor.selected = event.target.value; });
  $('#workflow-load')?.addEventListener('click', workflowLoad);
  $('#workflow-empty-load')?.addEventListener('click', workflowLoad);
  if ($('#workflow-yaml-editor') && window.WorkflowTools) {
    workflowCaptureEditorStates(); workflowYamlEditor?.destroy(); workflowPromptEditor?.destroy();
    workflowYamlEditor = window.WorkflowTools.createEditor($('#workflow-yaml-editor'), {text: workflowEditor.files['workflow.yaml'] || '', state: workflowEditorStates['workflow.yaml'], language: 'yaml', label: 'Workflow definition YAML', readOnly: workflowEditor.loading, onChange: value => { workflowEditor.files['workflow.yaml'] = value; workflowUpdateState(); }});
    workflowPromptEditor = window.WorkflowTools.createEditor($('#workflow-prompt-editor'), {text: workflowEditor.files[workflowEditor.prompt] || '', state: workflowEditorStates[workflowEditor.prompt], language: 'markdown', label: 'Prompt contents', readOnly: workflowEditor.loading, onChange: value => { workflowEditor.files[workflowEditor.prompt] = value; workflowUpdateState(); }});
    workflowRenderDiagram();
  }
  $('#workflow-prompt-select')?.addEventListener('change', event => workflowSelectPrompt(event.target.value));
  $('#workflow-preview')?.addEventListener('click', workflowPreview);
  $('#workflow-zoom-in')?.addEventListener('click', () => workflowChangeZoom(.2));
  $('#workflow-zoom-out')?.addEventListener('click', () => workflowChangeZoom(-.2));
  $('#workflow-zoom-fit')?.addEventListener('click', () => workflowChangeZoom('fit'));
  $('#workflow-inspector-jump')?.addEventListener('click', () => { const inspector = $('#workflow-inspector'); inspector?.scrollIntoView({block:'start'}); inspector?.focus({preventScroll:true}); });
  $('#workflow-save')?.addEventListener('click', () => workflowAction('save'));
  $('#workflow-save-as')?.addEventListener('click', () => { workflowEditor.saveAsOpen = true; workflowEditor.saveAsName = workflowEditor.name; workflowEditor.saveAsError = ''; $('#workflow-save-as-name').value = workflowEditor.saveAsName; $('#workflow-save-as-error').textContent = ''; $('#workflow-save-as-form').hidden = false; $('#workflow-save-as-name').focus(); $('#workflow-save-as-name').select(); });
  $('#workflow-save-as-name')?.addEventListener('input', event => { workflowEditor.saveAsName = event.target.value; workflowEditor.saveAsError = ''; $('#workflow-save-as-error').textContent = ''; });
  $('#workflow-save-as-form')?.addEventListener('submit', event => { event.preventDefault(); workflowAction('save_as', $('#workflow-save-as-name').value); });
  $('#workflow-save-as-cancel')?.addEventListener('click', () => { workflowEditor.saveAsOpen = false; $('#workflow-save-as-form').hidden = true; $('#workflow-save-as').focus(); });
  $('#workflow-activate')?.addEventListener('click', () => workflowAction('activate'));
  $('#workflow-discard')?.addEventListener('click', () => { if (!workflowCanLeave()) return; workflowEditor.files = {...workflowEditor.saved}; workflowEditor.message = 'Changes discarded.'; workflowEditor.error = false; workflowRefresh(); });
}
