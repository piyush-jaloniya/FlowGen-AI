const NS = 'http://www.w3.org/2000/svg';
const NODE_WIDTH = 166;
const NODE_HEIGHT = 50;

const styles = {
  start: ['#30254e', '#b49afc'],
  end: ['#30254e', '#b49afc'],
  decision: ['#362b23', '#e9b572'],
  process: ['#202b46', '#8da6ec'],
  call: ['#22344b', '#8ac7ee'],
  io: ['#193834', '#82d9bf'],
  control: ['#3c2d46', '#d5a9e1'],
  opaque: ['#363447', '#aaa9cb'],
  external: ['#272a3b', '#a4a7bd'],
  module: ['#253047', '#8faff1'],
};

function svgElement(tag, attributes = {}, value) {
  const element = document.createElementNS(NS, tag);
  for (const [key, item] of Object.entries(attributes)) element.setAttribute(key, item);
  if (value !== undefined) element.textContent = value;
  return element;
}

function uniqueEdges(edges) {
  const grouped = new Map();
  for (const edge of edges) {
    const key = [edge.source, edge.target, edge.kind].join(' ');
    if (!grouped.has(key)) grouped.set(key, { ...edge, labels: [] });
    if (edge.label) grouped.get(key).labels.push(edge.label);
  }
  return Array.from(grouped.values(), edge => ({
    ...edge, label: edge.labels.length > 3 ? edge.labels.slice(0, 3).join(', ') + '…' : edge.labels.join(' / '),
  }));
}

function arrange(graph, edges, columns) {
  const positions = new Map();
  const nodes = graph.nodes.map(node => node.id);
  if (graph.mode === 'overview') {
    const gridWidth = Math.min(columns, 5, Math.max(1, Math.ceil(Math.sqrt(nodes.length))));
    nodes.forEach((id, i) => positions.set(id, { x: 139 + (i % gridWidth) * 212, y: 63 + Math.floor(i / gridWidth) * 112 }));
    return { positions, width: 278 + (gridWidth - 1) * 212, height: 128 + Math.floor((nodes.length - 1) / gridWidth) * 112 };
  }
  const outgoing = new Map(nodes.map(id => [id, []]));
  const incoming = new Map(nodes.map(id => [id, 0]));
  const rank = new Map(nodes.map(id => [id, 0]));
  const feedback = new Set();
  const visited = new Set();
  const visiting = new Set();
  for (const edge of edges) outgoing.get(edge.source).push(edge);

  function visit(id) {
    visiting.add(id);
    for (const edge of outgoing.get(id)) {
      if (visiting.has(edge.target)) feedback.add(edge);
      else {
        incoming.set(edge.target, incoming.get(edge.target) + 1);
        if (!visited.has(edge.target)) visit(edge.target);
      }
    }
    visiting.delete(id);
    visited.add(id);
  }
  for (const id of nodes) if (!visited.has(id)) visit(id);
  const rows = [];
  const ready = nodes.filter(id => incoming.get(id) === 0);
  while (ready.length) {
    const id = ready.shift();
    const level = rank.get(id);
    (rows[level] ??= []).push(id);
    for (const edge of outgoing.get(id)) {
      if (feedback.has(edge)) continue;
      const target = edge.target;
      rank.set(target, Math.max(rank.get(target), level + 1));
      incoming.set(target, incoming.get(target) - 1);
      if (incoming.get(target) === 0) ready.push(target);
    }
  }
  const widest = Math.max(1, ...rows.map(row => row.length));
  const width = 316 + (Math.min(columns, widest) - 1) * 200;
  let y = 58;
  for (const row of rows) {
    for (let i = 0; i < row.length; i += columns) {
      const line = row.slice(i, i + columns);
      line.forEach((id, column) => positions.set(id, { x: width / 2 + (column - (line.length - 1) / 2) * 200, y }));
      y += 100;
    }
  }
  return { positions, width, height: y - 7 };
}

function edgePath(from, to, index, fromKind, toKind) {
  const start = from.y + (fromKind === 'decision' ? 35 : NODE_HEIGHT / 2);
  const finish = to.y - (toKind === 'decision' ? 35 : NODE_HEIGHT / 2);
  if (finish > start && to.y - from.y <= 120) {
    const y = (start + finish) / 2;
    return { d: 'M' + from.x + ' ' + start + ' C' + from.x + ' ' + y + ' ' + to.x + ' ' + y + ' ' + to.x + ' ' + finish,
      x: (from.x + to.x) / 2, y: y - 5 };
  }
  const side = to.x < from.x ? -1 : 1;
  const edgeWidth = kind => NODE_WIDTH / 2 + (kind === 'decision' ? 8 : kind === 'io' ? -7 : 0);
  const startX = from.x + side * edgeWidth(fromKind);
  const rail = (side > 0 ? Math.max(from.x, to.x) : Math.min(from.x, to.x)) + side * (99 + (index % 3) * 8);
  if (from.y === to.y) {
    const arcY = from.y - 35 - (index % 3) * 5;
    const fromX = from.x + (from === to ? 28 : 0);
    const toX = to.x - (from === to ? 28 : 0);
    return { d: 'M' + fromX + ' ' + (from.y - 22) + ' C' + fromX + ' ' + (arcY - 25) + ' ' +
      toX + ' ' + (arcY - 25) + ' ' + toX + ' ' + (to.y - 25),
      x: (from.x + to.x) / 2, y: arcY - 9 };
  }
  const endX = to.x + side * edgeWidth(toKind);
  return { d: 'M' + startX + ' ' + from.y + ' H' + rail + ' V' + to.y + ' H' + endX,
    x: rail + side * 6, y: (from.y + to.y) / 2, anchor: side > 0 ? 'start' : 'end' };
}

function shape(node, x, y, attrs) {
  const left = x - NODE_WIDTH / 2;
  const top = y - NODE_HEIGHT / 2;
  const right = x + NODE_WIDTH / 2;
  const bottom = y + NODE_HEIGHT / 2;
  const points = (...values) => values.join(' ');
  if (node.kind === 'decision') return svgElement('polygon', { points: points(x, top - 10, right + 8, y, x, bottom + 10, left - 8, y), ...attrs });
  if (node.kind === 'io') return svgElement('polygon', { points: points(left + 14, top, right, top, right - 14, bottom, left, bottom), ...attrs });
  const r = node.kind === 'start' || node.kind === 'end' ? 25 : 8;
  const rect = svgElement('rect', { x: left, y: top, width: NODE_WIDTH, height: NODE_HEIGHT, rx: r, ...attrs });
  if (node.kind !== 'call') return rect;
  const subroutine = svgElement('g');
  const rule = svgElement('path', { d: 'M' + (left + 10) + ' ' + top + 'v' + NODE_HEIGHT +
    ' M' + (right - 10) + ' ' + top + 'v' + NODE_HEIGHT, stroke: attrs.stroke, fill: 'none' });
  subroutine.append(rect, rule);
  return subroutine;
}

function labelLines(label, length) {
  const lines = [];
  let current = '';
  for (let word of label.split(/\s+/)) {
    if (word.length > length) word = word.slice(0, length - 1) + '…';
    if (!current || current.length + word.length + 1 <= length) current = current ? current + ' ' + word : word;
    else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  if (lines.length > 2) lines[1] = lines[1].slice(0, length - 1) + '…';
  return lines.slice(0, 2);
}

export function drawGraph(graph, selectNode, columns = 6) {
  const edges = uniqueEdges(graph.edges);
  const kinds = new Map(graph.nodes.map(node => [node.id, node.kind]));
  const { positions, width, height } = arrange(graph, edges, columns);
  const svg = svgElement('svg', { width, height, viewBox: '0 0 ' + width + ' ' + height,
    role: 'group', 'aria-label': graph.title, 'font-family': 'Segoe UI, Arial, sans-serif' });
  const direction = svgElement('marker', { id: 'flow-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
    markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' });
  direction.append(svgElement('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: '#a7abc8' }));
  const defs = svgElement('defs');
  defs.append(direction);
  svg.append(defs, svgElement('title', {}, graph.title));

  edges.forEach((edge, index) => {
    const location = edgePath(positions.get(edge.source), positions.get(edge.target), index,
      kinds.get(edge.source), kinds.get(edge.target));
    const path = svgElement('path', { d: location.d, fill: 'none', stroke: '#9298bb', 'stroke-width': 1.3,
      opacity: .9, 'marker-end': 'url(#flow-arrow)' });
    if (edge.kind === 'external' || edge.kind === 'exception') path.setAttribute('stroke-dasharray', '4 4');
    svg.append(path);
    if (edge.label) svg.append(svgElement('text', { x: location.x, y: location.y,
      'text-anchor': location.anchor || 'middle', 'font-size': 10, fill: '#d2d4e7', stroke: '#11131e',
      'stroke-width': 4, 'stroke-linejoin': 'round', 'paint-order': 'stroke' }, edge.label));
  });

  for (const node of graph.nodes) {
    const { x, y } = positions.get(node.id);
    const [fill, stroke] = styles[node.kind] || styles.process;
    const attrs = { fill, stroke, 'stroke-width': 1.4 };
    if (node.kind === 'external' || node.kind === 'opaque') attrs['stroke-dasharray'] = '5 3';
    const group = svgElement('g');
    group.append(svgElement('title', {}, node.label + (node.path ? ' · ' + node.path + ':' + node.line : '')));
    group.append(shape(node, x, y, attrs));
    const lines = labelLines(node.label, node.kind === 'decision' ? 18 : 23);
    lines.forEach((line, i) => group.append(svgElement('text', { x, y: y + 4 + (i - (lines.length - 1) / 2) * 15,
      'text-anchor': 'middle', fill: '#f1effa', 'font-size': 13, 'font-weight': 600 }, line)));
    if (node.path && selectNode) {
      group.setAttribute('tabindex', 0);
      group.setAttribute('role', 'button');
      group.setAttribute('aria-label', node.label + ', ' + node.path + ', line ' + node.line);
      group.addEventListener('click', () => selectNode(node, group));
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectNode(node, group);
        }
      });
    }
    svg.append(group);
  }
  return { svg, width, height };
}

export function mermaidSource(graph) {
  function escaped(value) {
    return value.replace(/[^A-Za-z0-9 _.-]/gu, character => '#' + character.codePointAt(0) + ';');
  }
  const shapes = {
    start: ['(["', '"])'], end: ['(["', '"])'], decision: ['{"', '"}'], io: ['[/"', '"/]'],
    call: ['[["', '"]]'],
  };
  return ['flowchart TD', ...graph.nodes.map(node => {
    const [left, right] = shapes[node.kind] || ['["', '"]'];
    return '    ' + node.id + left + escaped(node.label) + right;
  }), ...graph.edges.map(edge => {
    const arrow = edge.kind === 'external' || edge.kind === 'exception' ? '-.->' : '-->';
    const label = edge.label ? '|' + escaped(edge.label) + '|' : '';
    return '    ' + edge.source + ' ' + arrow + label + ' ' + edge.target;
  }), ''].join('\n');
}

export function svgImage(graph) {
  const { svg, width, height } = drawGraph(graph);
  svg.insertBefore(svgElement('rect', { x: 0, y: 0, width, height, fill: '#11131e' }), svg.firstChild);
  return { content: new XMLSerializer().serializeToString(svg), width, height };
}
