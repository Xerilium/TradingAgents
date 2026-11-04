import { basicSetup } from "codemirror";
import { EditorState, Compartment } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { yaml } from "@codemirror/lang-yaml";
import { markdown } from "@codemirror/lang-markdown";
import mermaid from "mermaid";

const workflowTheme = EditorView.theme({
  "&": {color: "var(--ink)", backgroundColor: "var(--paper)"},
  ".cm-content": {caretColor: "var(--accent)"},
  ".cm-cursor, .cm-dropCursor": {borderLeftColor: "var(--accent)"},
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {backgroundColor: "var(--accent-wash)"},
  ".cm-activeLine": {backgroundColor: "var(--navy)"},
  ".cm-gutters": {color: "var(--muted)", backgroundColor: "var(--ground)", borderRight: "1px solid var(--line)"},
  ".cm-activeLineGutter": {color: "var(--ink)", backgroundColor: "var(--navy)"},
  ".cm-tooltip": {color: "var(--ink)", backgroundColor: "var(--paper)", border: "1px solid var(--line)"}
}, {dark: true});
const workflowHighlight = syntaxHighlighting(HighlightStyle.define([
  {tag: [tags.propertyName, tags.heading, tags.keyword], color: "var(--accent)"},
  {tag: [tags.string, tags.special(tags.string)], color: "var(--warning)"},
  {tag: [tags.number, tags.bool, tags.null, tags.atom], color: "var(--universe-focus)"},
  {tag: [tags.comment, tags.meta], color: "var(--muted)"},
  {tag: [tags.punctuation, tags.operator], color: "var(--ink)"},
  {tag: tags.link, color: "var(--universe-focus)", textDecoration: "underline"},
  {tag: tags.strong, fontWeight: "bold"},
  {tag: tags.emphasis, fontStyle: "italic"}
]));

export function createEditor(parent, options = {}) {
  const saved = options.state;
  const compartments = saved?.compartments || {
    editable: new Compartment(), language: new Compartment(),
    label: new Compartment(), listener: new Compartment()
  };
  const language = options.language === "yaml" ? yaml() : options.language === "markdown" ? markdown() : [];
  let settingValue = false;
  const editable = value => [EditorState.readOnly.of(Boolean(value)), EditorView.editable.of(!value)];
  const label = EditorView.contentAttributes.of({"aria-label": options.label || "Editor"});
  const listener = EditorView.updateListener.of(update => {
    if (update.docChanged && !settingValue && options.onChange) options.onChange(update.state.doc.toString());
  });
  let state;
  if (saved?.state) {
    state = saved.state.update({effects: [
      compartments.editable.reconfigure(editable(options.readOnly)),
      compartments.language.reconfigure(language),
      compartments.label.reconfigure(label),
      compartments.listener.reconfigure(listener)
    ]}).state;
  } else {
    state = EditorState.create({doc: String(options.text ?? ""), extensions: [
      basicSetup, workflowTheme, workflowHighlight, EditorView.lineWrapping,
      compartments.language.of(language), compartments.label.of(label),
      compartments.editable.of(editable(options.readOnly)), compartments.listener.of(listener)
    ]});
  }
  const view = new EditorView({parent, state});
  if (saved?.scroll) {
    view.scrollDOM.scrollTop = saved.scroll.top;
    view.scrollDOM.scrollLeft = saved.scroll.left;
  }
  return {
    getValue: () => view.state.doc.toString(),
    getState: () => ({state: view.state, compartments, scroll: {top: view.scrollDOM.scrollTop, left: view.scrollDOM.scrollLeft}}),
    setValue(value) {
      value = String(value ?? "");
      if (value === view.state.doc.toString()) return;
      settingValue = true;
      try { view.dispatch({changes: {from: 0, to: view.state.doc.length, insert: value}}); }
      finally { settingValue = false; }
    },
    setReadOnly(value) { view.dispatch({effects: compartments.editable.reconfigure(editable(value))}); },
    focus: () => view.focus(),
    destroy: () => view.destroy()
  };
}

// Mermaid's configuration is global; serialize calls to avoid theme races.
let pending = Promise.resolve();
export function renderDiagram(id, source, themeVars = {}) {
  const run = async () => {
    mermaid.initialize({startOnLoad: false, securityLevel: "strict", theme: "base", themeVariables: themeVars, flowchart: {htmlLabels: false}});
    const result = await mermaid.render(id, source);
    return result.svg;
  };
  const result = pending.then(run, run);
  pending = result.catch(() => {});
  return result;
}
