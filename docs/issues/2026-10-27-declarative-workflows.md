# Declarative workflows and runtime prompt editor implementation plan

Status: Implementation, source review and development UI acceptance complete. Production replacement is not authorized.
Requested: 27 October 2026.
Primary product checkout: C:/src/TradingAgents.

## Goal

Move the existing research workflow into YAML and its application-authored prompts into editable files. Add a Workflows workspace directly above Settings. Users can select and load a workflow with its associated prompts, edit the files, save them, and choose the workflow used for new research.

Preserve current behaviour in the supplied default workflow. This is an extraction and editor change, not a redesign of the trading strategy.

## Scope

### Workflow definition

Each workflow is a folder containing workflow.yaml and its referenced prompt files. YAML defines enabled agents, Fast or Deep assignments, execution connections, parallel analyst branches and their join, bounded research and risk debates, tool-round limits, and prompt references.

Keep LangGraph as the runtime. A small loader builds its graph from the definition using registered existing handlers, tools and routers. The definition must control the connections; moving only labels and numeric settings into YAML does not satisfy this requirement.

Use data-only YAML parsing and the existing validation stack. Reject unknown handlers, invalid connections, missing files and unsupported template variables with useful errors. Keep references within the workflow folder. Preserve raw edited YAML rather than rewriting away comments on save.

### Prompt files

Extract the instructions for all 12 research agents. Include shared wrappers, evidence instructions, memory guidance, stock and ETF branches, fundamentals verification, tool-budget wrap-up, desk execution wording, and the separate joint portfolio allocator.

Include application-authored instruction text in structured-output field descriptions where it is presented to the model. Keep schema types, enums, validation logic and provider-generated protocol syntax in code.

Use simple named template variables. Keep runtime evidence separate from instructions and render each template once. Preserve current wording, conditions, input bindings and output contracts in the default bundle. Missing files or variables must produce explicit errors rather than silently using hidden Python prompts.

### Workflow and prompt editors with a diagram

The operator requested this extension after seeing the initial editor.
Use separate CodeMirror editors for workflow YAML and prompts, plus a local
Mermaid renderer for an explanatory diagram generated from the same validated
definition. Keep the application runtime and existing research behaviour unchanged.

The diagram shows selected analyst branches, their join, both bounded debates,
the trader, final manager and decision. Show model tiers and configured round
limits. Group routine per-turn router checks into a clear round summary, with a
caption explaining the distinction. Synthetic joins, checks and boundaries are
visual elements rather than additional agents. The desktop does not run the
optional CLI local-memory branch.

Selecting an agent can open its associated prompt. Shared instructions,
conditional variants, schema descriptions and the separate portfolio prompt
remain available. Label agent prompt links as navigation aids, not a complete
assembled runtime prompt.

Preview the loaded bundle automatically and unsaved YAML on explicit request.
Identify stale diagrams when the draft changes; a late preview cannot overwrite
a subsequently loaded bundle. Preview must not save, activate or execute a run.

Bundle the editor and renderer locally with pinned dependencies and license
notices. Preserve separate file buffers, accessible controls, draft retention,
save conflicts and active-workflow selection. No external CDN is required.

### Runtime and storage

Bundle the default workflow and prompts with the Python package and installed desktop application. Seed editable files once into a workflows directory under the selected app profile. Keep development and production directories separate. Installer updates must not overwrite authored files.

On first use, retain the existing saved analyst selection, debate rounds and tool limits in the seeded workflow. Do not silently revert these choices to package defaults.

At research creation, load and validate the selected YAML and all referenced prompts together. Hold the complete bundle in memory for that run, including queued stocks. Later saves and selection changes apply to new runs only. Apply the same loading rule to a new joint portfolio call.

Save the selected workflow so it survives app restart. Graph structure, model-tier assignment and graph-specific limits have one source of truth in YAML. Move their existing Settings controls to Workflows or replace them with a link there. Provider endpoints, model names, token settings, stock concurrency and CPU/GPU selection stay in Settings.

### Workflows workspace

Add the navigation item and hash route immediately above Settings. Reuse the current UI styles and design tokens.

The workspace provides:

- A saved-workflow selector, Load action, and clear active-workflow label.
- A file list for workflow.yaml and all referenced prompt files.
- Separate CodeMirror editors for workflow YAML and selected prompts.
- Save, Save as, and Discard changes.
- Use for new research, separate from loading an editor draft.
- Useful validation and save feedback, with filename and line where available.
- An unsaved-change check before replacing or leaving a draft.

Loading a workflow loads its associated files together. Editing or saving does not start research. Use for new research selects the saved bundle; it does not launch it.

Keep editor drafts stable while normal app polling updates other state. Validate the complete edited bundle before saving. Do not report a successful save after a partial file write. Concurrent browser edits must receive a conflict instead of silently overwriting another save; this requires no revision-history UI.

Use the existing local API, session and CSRF protections. Expose workflow file operations through that API rather than arbitrary filesystem access.

## Implementation sequence

1. Capture the current topology, prompt branches, settings ownership and state/output contracts as the preservation baseline.
2. Add bundled YAML and prompt files, validation, profile storage, and the loader that builds LangGraph.
3. Connect the current handlers and separate portfolio allocator to the loaded files. Remove their replaced hardcoded prompt definitions.
4. Add workflow API operations and the Workflows editor. Consolidate the graph-specific Settings controls.
5. Update package resources, dependency locks where required, README and the app usage guide.
6. Complete the batch, review the changed contracts, then perform one affected UI verification cycle.

## What done looks like

Every item below must be satisfied before declaring this implementation complete.

- [ ] Workflows appears directly above Settings and opens through its own route.
- [ ] The supplied default YAML builds the current graph, including analyst tool loops, parallel join, both bounded debates and current Fast/Deep assignments.
- [ ] Current instruction wording and stock/ETF branches are preserved in files; source comparison accounts for every extracted prompt section.
- [ ] No replaced instruction remains as an undisclosed Python fallback.
- [ ] Loading a saved workflow displays its YAML and all referenced prompt files.
- [ ] Users can edit YAML and prompts, Save, Save as, Discard, and select the saved workflow for new research.
- [ ] Invalid YAML, missing references, unknown variables and invalid graphs produce useful errors and preserve the draft and prior saved bundle.
- [ ] Saved files and the active selection survive app restart; production and development remain isolated.
- [ ] Updates preserve authored workflow files.
- [ ] Runtime loading uses the selected saved files. No rebuild or reinstall is required for subsequent prompt or workflow edits.
- [ ] A run uses one coherent in-memory bundle from creation through all its queued and active stocks.
- [ ] Provider settings, token limits, scheduling, cancellation, evidence receipts and completion checks retain their current contracts.
- [ ] Existing risk checks, order preparation, approval and separate broker submission retain their current contracts.
- [ ] Graph-specific settings are not controlled by conflicting YAML and Settings values.
- [ ] The affected UI is checked once after the batch, including load, edit, save, invalid-input feedback, active selection, navigation and persistence.
- [ ] Documentation describes file locations, placeholders, loading, saving and when changes take effect.

- [x] Separate CodeMirror YAML and prompt editors are available, with independent file buffers and no cross-file undo. (source reviewed; development UI observed where applicable)
- [x] The Mermaid diagram is derived from validated workflow files and explains selected branches, tiers, joins, debate loops and final output. (source reviewed; development UI observed where applicable)
- [x] Synthetic visual nodes, round summaries and omitted desktop-inactive CLI memory are explained visibly. (source reviewed; development UI observed where applicable)
- [x] Agent selection opens related prompts while shared, conditional, schema and allocator files remain accessible. (source reviewed; development UI observed where applicable)
- [x] Draft edits mark the diagram stale; preview refreshes explicitly without saving or executing. (source reviewed; development UI observed where applicable)
- [x] Editor/renderer assets and license notices are served locally and included in packaged installs. (source reviewed; development UI observed where applicable)

Preserving behaviour means preserving graph, instruction and service contracts. It does not mean identical answers from non-deterministic models. Source comparison and an editor check do not prove live research equivalence. Report that acceptance boundary accurately.

## Acceptance evidence — 27 October 2026

In the built-in browser against the development app on port 8099, the workflow view rendered a Mermaid diagram with 18 nodes and two round checks, alongside two CodeMirror editors. Per-prompt drafts and undo history survived switching prompts. Invalid YAML produced a line 203 error and preserved the draft; preview validated the draft. Save kept the graph visible. Inline Save as created “Research desk” while Default remained active; activating the copy kept the graph visible, and a page reload retained the copy as active. After correcting the renderer node ID prefix, mouse and keyboard node selection opened the correct primary prompts. A shared prompt was accessible, and Default was restored as active.

The same development UI journey confirmed dark syntax and gutters, two independently scrolling editor panels bounded to 466 px, and a centered diagram with the application font and clean label strokes. Final targeted fixes and packaging inclusion were source reviewed. Screenshots: `workflow-editors-final.png` and `workflow-diagram-final.png` in the task's visualization directory.

This exercise did not establish persistence across an app restart, cover every validation branch, exercise an installed update, or establish live research equivalence.

## Studio refinement evidence - 27 October 2026

Source and UI review found all six scoped refinement findings resolved. The
diagram-first studio distinguishes Editing, Active and the workflow selected
for Load; Prompt and YAML inspector tabs and searchable file purposes support
navigation. Related agent, shared and schema files are navigation aids, not an
assembled prompt. Save as provides conflict guidance, and the two debate checks
have distinct labels. The locally bundled toolkit loads on entering Workflows.

In the development browser, the studio was inspected at 390, 768, 1280 and
2392 px. Read-only loading, mouse and keyboard node selection, purpose search,
and preservation and restoration of an invalid YAML draft were observed.
Selecting a different workflow for Load did not change Editing. The toolkit
script count was zero on the initial Dashboard and one in Workflows; controls
measured 44 px, and Fit ranged from a minimum 88% to 134% on the wide view.
Screenshots are workflow-studio-final-{1280,768,390,2392}.png in the task
visualization directory. One detector pass reported zero primary findings and
two old status-color advisories; the colors were subsequently replaced with
existing tokens and source checked, without another detector pass.

The long graph scrolls, the graph begins near the bottom of the narrow first
viewport, and a selected node can clip after wide Fit. This review does not establish universal
pixel-perfect layout, screen-reader behavior or live research equivalence.
No tests, research runs, production replacement or release build were performed
for this refinement.

## Explicitly out of scope

- Git integration, commits or pushes for workflow edits.
- Workflow or prompt version-history features, audit ledgers, persisted run snapshots, replay, resume or LangGraph checkpoints.
- A draggable node canvas, visual graph editing, or a new frontend framework. The read-only Mermaid diagram is in scope.
- Replacing LangGraph or adopting Maenifold, LangConfig or another application's execution runtime.
- New agents, tools, data providers, trading strategies, performance optimisation or prompt tuning.
- Fixing the aggressive analyst's role conflict or rewriting caution language during extraction.
- Creating a new investment mandate, choosing risk preferences, passing saved risk policy into research, or changing allocation logic.
- Research-history retention changes, universe changes or unrelated UI cleanup.
- Automated tests, mocks, benchmarks or research reruns.
- Broker orders, approvals, submissions, cancellations or replacements.
- Building or installing a release, replacing production, restarting the live app, or changing settings during this documentation task.

Any proposed useful extra outside this scope must be raised separately. It must not be added to the implementation or made a condition of completion.

## Source map

- tradingagents/graph/setup.py and conditional_logic.py: topology, tool loops, joins and debate routing.
- tradingagents/graph/trading_graph.py and analyst_execution.py: graph creation, state and tool assembly.
- tradingagents/agents/analysts, researchers, managers, risk_mgmt and trader: agent instructions and conditional branches.
- tradingagents/agents/context.py, prompt_evidence.py, structured.py and schemas.py: shared instructions, evidence boundaries and output contracts.
- tradingagents/web/portfolio_model.py: separate joint portfolio prompt.
- tradingagents/web/service.py, server.py and config.py: run creation, configuration and API.
- tradingagents/web/static/app.js and existing UI styles: workspace routing, navigation and editor integration.
- tradingagents/web/static/workflows.js, ui-workflows.css and vendor/workflow-tools/workflow-tools.js: workflow editors and locally bundled renderer.
- tradingagents/web/workflow_diagram.py: read-only projection of the validated workflow.
- pyproject.toml and packaging: bundled resources and desktop dependencies.


## Production release 0.6.13 - 27 October 2026

Built, signed and installed in the canonical Windows production directory. The app now uses persistent production-profile runtimes/desk and runtimes/native, with replaceable application code in payload/app. Existing CUDA dependencies were preserved; app updates do not replace those runtimes.

Observed on port8098: connected and reconciled paper account, Laya ready on CUDA without fallback, and the new Workflows layout with94 prompts and a47px single-row document header. Installed UI asset hashes match source. Saved workspace, latest research, investor and journal payloads match the pre-upgrade backup. Startup command-record changes were limited to account_versions and native_epoch.

Installer SHA256: efdb03d8b773d71dc3280c2f49bc08c36a549566bda84c08d97bf2827ee23935. Cutover evidence is in packaging/build/release-before-0613.json and release-after-0613.json; screenshot workflows-production-0613.png is in the task visualization directory. No tests, research reruns or broker actions. macOS runtime acceptance was not performed.
