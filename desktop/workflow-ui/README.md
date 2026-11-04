# Workflow browser toolkit

Run `npm ci` in `desktop`, then `npm run build:workflow-tools`. The script bundles CodeMirror and Mermaid as one local IIFE and generates third-party license notices alongside it. The browser exposes `window.WorkflowTools`.

`createEditor(parent, {text, language, label, readOnly, onChange})` accepts `yaml`, `markdown`, or `plain` and returns `getValue`, `getState`, `setValue`, `setReadOnly`, `focus`, and `destroy`. Pass the opaque `getState()` snapshot as `state` when reopening the same file to retain its undo history, selection, and scroll position. Current options replace the previous callback, language, label, and read-only configuration. Programmatic `setValue` does not invoke `onChange`. `renderDiagram(id, source, themeVariables)` resolves to an SVG string. Mermaid runs with strict security and HTML labels disabled.
