import { drawGraph, mermaidSource, svgImage } from './graph.js';
import { exampleCode, exampleProject } from './examples.js';
import { highlight } from './highlight.js';

const get = id => document.getElementById(id);
const form = get('analyze-form');
const code = get('code');
const codeHighlight = get('highlight');
const language = get('language');
const graphArea = get('graph');
const viewport = get('viewport');
const compact = window.matchMedia('(max-width: 510px)');
const details = get('details');
const select = get('scope');
const messages = get('messages');
const exportMenu = get('export-menu');
const exportToggle = get('export-toggle');
const diagramPanel = get('diagram-panel');
const viewButtons = [...document.querySelectorAll('[data-view]')];
const extensions = { python: 'py', javascript: 'js', typescript: 'ts', java: 'java', c: 'c', cpp: 'cpp' };
const allowed = /\.(py|pyw|js|mjs|cjs|jsx|tsx?|mts|cts|java|c|h|cc|cpp|cxx|hpp|hh|hxx|zip)$/i;
const tsconfig = /(?:^|\/)tsconfig(?:\.[\w.-]+)?\.json$/;
const vendor = /(?:^|\/)(?:\.git|\.venv|\.idea|node_modules|vendor|__pycache__|__MACOSX|dist|build|target|venv|coverage)\//;
const state = { input: 'code', view: 'flowchart', files: [], report: null, graph: null, drawing: null,
  controller: null, generating: false, selection: null, zoom: 1, fitMode: 'width', scopeByView: {} };

function inputMode(mode) {
  state.input = mode;
  get('mode-code').setAttribute('aria-pressed', mode === 'code');
  get('mode-files').setAttribute('aria-pressed', mode === 'files');
  get('code-input').hidden = mode !== 'code';
  get('files-input').hidden = mode !== 'files';
}

function showMessages(items) {
  messages.replaceChildren();
  for (const item of items) {
    const line = document.createElement('p');
    if (typeof item === 'string') line.textContent = item;
    else line.textContent = (item.path ? item.path + (item.line ? ':' + item.line : '') + ' · ' : '') + item.message;
    messages.append(line);
  }
  messages.hidden = items.length === 0;
}

function updateCode() {
  get('filename').textContent = 'snippet.' + extensions[language.value];
  const count = Math.min(20000, code.value.split('\n').length);
  get('line-numbers').textContent = Array.from({ length: count }, (_, i) => i + 1).join('\n');
  highlight(codeHighlight, code.value, language.value);
  syncEditorScroll();
}

function syncEditorScroll() {
  get('line-numbers').scrollTop = code.scrollTop;
  codeHighlight.scrollTop = code.scrollTop;
  codeHighlight.scrollLeft = code.scrollLeft;
}

function filePath(file) {
  return file.webkitRelativePath || file.name;
}

function setFiles(files) {
  state.files = [...files].filter(file => {
    const path = filePath(file);
    if (file.webkitRelativePath && /\.zip$/i.test(path)) return false;
    return (allowed.test(path) || tsconfig.test(path)) && !vendor.test(path);
  });
  const summary = get('upload-summary');
  const list = get('file-list');
  const skipped = files.length - state.files.length;
  summary.textContent = state.files.length ? state.files.length + ' selected' + (skipped ? ' · ' + skipped + ' skipped' : '')
    : files.length ? 'No supported source files selected.' : 'Python, JavaScript, TypeScript, Java, C, and C++';
  list.replaceChildren(...state.files.slice(0, 25).map(file => {
    const item = document.createElement('li');
    item.textContent = filePath(file);
    return item;
  }));
  if (state.files.length > 25) {
    const remainder = document.createElement('li');
    remainder.textContent = 'And ' + (state.files.length - 25) + ' more';
    list.append(remainder);
  }
  list.hidden = !state.files.length;
}

function busy(value) {
  get('analyze-button').disabled = value;
  get('analyze-label').textContent = value ? 'Analyzing…' : 'Generate diagram';
  diagramPanel.setAttribute('aria-busy', value);
}

async function request(path, payload, accept) {
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  busy(true);
  showMessages([]);
  try {
    const options = { method: 'POST', signal: controller.signal };
    if (payload instanceof FormData) options.body = payload;
    else {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) {
      const reason = typeof data.detail === 'string' ? data.detail : 'Check the input and try again.';
      throw Error(reason);
    }
    if (controller === state.controller) accept(data);
  } catch (error) {
    if (error.name !== 'AbortError' && state.controller === controller) {
      showMessages([error.message || 'Analysis failed. Check the source and try again.']);
    }
  } finally {
    if (controller === state.controller) {
      state.controller = null;
      busy(false);
    }
  }
}

function setView(view) {
  state.view = view;
  for (const button of viewButtons) button.setAttribute('aria-pressed', button.dataset.view === view);
}

function updateScope(symbolId) {
  const symbols = state.report?.symbols || [];
  const previous = symbolId || state.scopeByView[state.view];
  select.replaceChildren(...symbols.map(symbol => {
    const option = document.createElement('option');
    option.value = symbol.id;
    const prefix = state.view === 'workflow' && symbol.entry ? symbol.entry + ' · ' : '';
    option.textContent = (symbol.entry === symbol.label ? '' : prefix) + symbol.label + ' · ' + symbol.path + ':' + symbol.line;
    return option;
  }));
  if (symbols.some(symbol => symbol.id === previous)) select.value = previous;
  get('scope-label').hidden = state.view === 'overview' || !symbols.length;
}

function acceptReport(report, view) {
  setView(view);
  state.report = report;
  state.scopeByView = {};
  updateScope(report.graph?.symbolId);
  render(report.graph);
}

async function generateReport(path, payload, view) {
  const controls = [...viewButtons, select, get('open-flow'), get('load-example'), get('load-project')];
  state.generating = true;
  for (const control of controls) control.disabled = true;
  try {
    await request(path, payload, report => acceptReport(report, view));
  } finally {
    state.generating = false;
    for (const control of controls) control.disabled = false;
  }
}

async function generate(event) {
  event?.preventDefault();
  if (state.generating) return;
  if (state.input === 'code') {
    if (!code.value.trim()) {
      showMessages(['Enter source code to generate a diagram.']);
      code.focus();
      return;
    }
    await generateReport('/api/analyze', { mode: 'flowchart', files: [
      { path: get('filename').textContent, language: language.value, content: code.value },
    ] }, 'flowchart');
  } else {
    if (!state.files.length) {
      showMessages(['Choose source files, a folder, or a ZIP archive.']);
      return;
    }
    const data = new FormData();
    for (const file of state.files) data.append('files', file, filePath(file));
    const single = state.files.length === 1 && !state.files[0].webkitRelativePath &&
      !/\.zip$/i.test(state.files[0].name);
    const view = single ? 'flowchart' : 'workflow';
    await generateReport('/api/upload?mode=' + view, data, view);
  }
}

function showLoadExample() {
  inputMode('code');
  code.value = exampleCode[language.value];
  updateCode();
  return generate();
}

async function loadProject() {
  inputMode('files');
  setFiles(exampleProject.map(item => new File([item.content], item.path, { type: 'text/plain' })));
  await generate();
}

function redraw(view, symbolId) {
  if (state.generating) return;
  setView(view);
  if (!state.report?.symbols.length) {
    updateScope();
    return;
  }
  const chosen = symbolId || state.scopeByView[view];
  updateScope(chosen);
  return request('/api/analyze', { files: state.report.files, mode: view, symbolId: view === 'overview' ? null : chosen },
    data => {
      updateScope(data.graph?.symbolId);
      render(data.graph);
    });
}

function closeDetails(returnFocus = false) {
  state.selection?.element.removeAttribute('data-selected');
  if (returnFocus) state.selection?.element.focus();
  state.selection = null;
  details.hidden = true;
}

function openDetails(node, element) {
  closeDetails();
  state.selection = { node, element };
  element.setAttribute('data-selected', 'true');
  details.hidden = false;
  get('step-title').textContent = node.label;
  get('step-location').textContent = node.path + ':' + node.line + (node.endLine > node.line ? '–' + node.endLine : '');
  get('step-detail').hidden = !node.detail;
  get('step-detail').textContent = node.detail || '';
  const file = state.report.files.find(item => item.path === node.path);
  const lines = file?.content.split(/\r?\n/) || [];
  const end = Math.min(node.endLine || node.line, node.line + 11);
  const preview = lines.slice(node.line - 1, end).map((line, i) => (node.line + i) + '  ' + line);
  if (end < node.endLine) preview.push('…');
  get('source-preview').textContent = preview.join('\n');
  get('open-flow').hidden = !node.symbolId;
  details.scrollIntoView({ block: 'nearest' });
}

function zoom(value, manual = true) {
  if (!state.drawing) return;
  if (manual) state.fitMode = null;
  state.zoom = Math.max(.15, Math.min(value, 2));
  state.drawing.svg.setAttribute('width', Math.round(state.drawing.width * state.zoom));
  state.drawing.svg.setAttribute('height', Math.round(state.drawing.height * state.zoom));
}

function fit(full = true) {
  if (!state.drawing) return;
  state.fitMode = full ? 'full' : 'width';
  const width = (viewport.clientWidth - 16) / state.drawing.width;
  const height = (viewport.clientHeight - 45) / state.drawing.height;
  zoom(Math.min(1.15, width, full ? height : Math.max(.82, height)), false);
  viewport.scrollTo(0, 0);
}

function render(graph) {
  closeDetails();
  graphArea.replaceChildren();
  state.graph = graph;
  state.drawing = graph?.nodes.length ? drawGraph(graph, openDetails, compact.matches ? 2 : 6) : null;
  if (state.drawing) {
    graphArea.append(state.drawing.svg);
    fit(false);
  }
  if (graph?.symbolId) state.scopeByView[state.view] = graph.symbolId;
  get('empty').hidden = !!state.drawing;
  get('empty').textContent = state.report?.diagnostics.length
    ? 'Resolve the source errors above to generate a diagram.' : 'Generate a diagram to explore your code.';
  exportToggle.disabled = !state.drawing;
  for (const id of ['zoom-out', 'fit', 'zoom-in', 'expand']) get(id).disabled = !state.drawing;
  const count = get('graph-count');
  count.textContent = graph ? graph.nodes.length + ' ' + (graph.mode === 'overview' ? 'modules' : 'nodes')
    + ' · ' + graph.edges.length + ' connections' : 'No diagram yet';
  const keys = graph?.mode === 'overview' ? [] : graph?.mode === 'workflow'
    ? [['entry', 'Entry point'], ['call', 'Call'], ['external', 'Unresolved']]
    : [['entry', 'Start / end'], ['decision', 'Decision'], ['process', 'Process']];
  if (graph?.mode === 'flowchart' && graph.nodes.some(node => node.kind === 'io')) keys.push(['io', 'Input / output']);
  if (graph?.mode === 'flowchart' && graph.nodes.some(node => node.kind === 'call')) keys.push(['call', 'Call']);
  get('legend').replaceChildren(...(graph ? keys.map(([kind, label]) => {
    const item = document.createElement('span');
    const mark = document.createElement('i');
    item.className = kind;
    mark.setAttribute('aria-hidden', 'true');
    item.append(mark, label);
    return item;
  }) : []));
  showMessages([...(state.report?.diagnostics || []), ...(graph?.warnings || [])]);
}

function expand(value) {
  get('expand').setAttribute('aria-pressed', value);
  diagramPanel.classList.toggle('expanded', value);
  if (value) diagramPanel.scrollTop = 0;
  fit(false);
}

function setExport(open) {
  exportMenu.hidden = !open;
  exportToggle.setAttribute('aria-expanded', open);
}

function download(blob, format, title) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = (title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'flowgen') + '.' + format;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function pngBlob(content, width, height) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([content], { type: 'image/svg+xml;charset=utf-8' }));
    const image = new Image();
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(Error('Unable to generate a PNG image.'));
    };
    image.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(2, 8192 / Math.max(width, height), Math.sqrt(17000000 / (width * height)));
      const canvas = document.createElement('canvas');
      canvas.width = Math.ceil(width * scale);
      canvas.height = Math.ceil(height * scale);
      const context = canvas.getContext('2d');
      if (!context) {
        reject(Error('Unable to create an export canvas.'));
        return;
      }
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => blob ? resolve(blob) : reject(Error('Unable to generate a PNG image.')), 'image/png');
    };
    image.src = url;
  });
}

async function exportGraph(format) {
  const graph = state.graph;
  if (!graph) return;
  setExport(false);
  exportToggle.focus();
  try {
    let blob;
    if (format === 'json') blob = new Blob([JSON.stringify(graph, null, 2)], { type: 'application/json' });
    else if (format === 'mmd') blob = new Blob([mermaidSource(graph)], { type: 'text/plain' });
    else {
      const { content, width, height } = svgImage(graph);
      blob = format === 'png' ? await pngBlob(content, width, height)
        : new Blob([content], { type: 'image/svg+xml;charset=utf-8' });
    }
    download(blob, format, graph.title);
  } catch (error) {
    showMessages([error.message]);
  }
}

get('mode-code').addEventListener('click', () => inputMode('code'));
get('mode-files').addEventListener('click', () => inputMode('files'));
get('load-example').addEventListener('click', showLoadExample);
get('load-project').addEventListener('click', loadProject);
get('choose-files').addEventListener('click', () => get('file-input').click());
get('choose-folder').addEventListener('click', () => get('folder-input').click());
for (const id of ['file-input', 'folder-input']) {
  get(id).addEventListener('change', event => {
    setFiles(event.target.files);
    event.target.value = '';
  });
}
const drop = get('drop-zone');
drop.addEventListener('dragover', event => {
  event.preventDefault();
  drop.classList.add('dragging');
});
drop.addEventListener('dragleave', () => drop.classList.remove('dragging'));
drop.addEventListener('drop', event => {
  event.preventDefault();
  drop.classList.remove('dragging');
  setFiles(event.dataTransfer.files);
});
form.addEventListener('submit', generate);
language.addEventListener('change', updateCode);
code.addEventListener('input', updateCode);
code.addEventListener('scroll', syncEditorScroll);
code.addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) generate(event);
});
for (const button of viewButtons) button.addEventListener('click', () => redraw(button.dataset.view));
select.addEventListener('change', () => redraw(state.view, select.value));
get('close-details').addEventListener('click', () => closeDetails(true));
get('open-flow').addEventListener('click', () => {
  const id = state.selection?.node.symbolId;
  if (id) redraw('flowchart', id);
});
get('zoom-out').addEventListener('click', () => zoom(state.zoom / 1.2));
get('zoom-in').addEventListener('click', () => zoom(state.zoom * 1.2));
get('fit').addEventListener('click', () => fit());
get('expand').addEventListener('click', () => expand(!diagramPanel.classList.contains('expanded')));
new ResizeObserver(() => {
  if (state.fitMode) fit(state.fitMode === 'full');
}).observe(viewport);
compact.addEventListener('change', () => {
  if (state.graph) render(state.graph);
});
exportToggle.addEventListener('click', () => setExport(exportMenu.hidden));
exportMenu.addEventListener('click', event => {
  const { format } = event.target.dataset;
  if (format) exportGraph(format);
});
document.addEventListener('click', event => {
  if (!exportMenu.hidden && event.target !== exportToggle && !exportToggle.contains(event.target) && !exportMenu.contains(event.target)) setExport(false);
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (!exportMenu.hidden) {
    setExport(false);
    exportToggle.focus();
  } else if (diagramPanel.classList.contains('expanded')) expand(false);
  else if (!details.hidden) closeDetails(true);
});

showLoadExample();
