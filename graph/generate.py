#!/usr/bin/env python3
"""Generate a self-contained graph.html from graph.json.

graph.json stays the single source of truth. This script embeds its data
directly into graph.html so the file renders anywhere it is opened —
file://, an online HTML viewer, htmlpreview, or GitHub Pages — with NO
separate fetch (the old fetch('graph.json') silently failed standalone).

Run after any distill:  python3 graph/generate.py
"""
import json, os, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "derrick-ships/distill-it"      # for absolute doc links
BRANCH = "main"

# Stable, readable palette for known domains. Unknown domains get a
# deterministic color derived from their name (so new distills never go grey).
DOMAIN_COLORS = {
    "adaptive-parsing": "#76e4f7", "document-conversion": "#4299e1",
    "plugin-architecture": "#9f7aea", "file-detection": "#f6ad55",
    "media-processing": "#68d391", "web-extraction": "#fc8181",
    "ai-integration": "#f687b3", "agent-architecture": "#f6e05e",
    "research-automation": "#63b3ed", "content-synthesis": "#b794f4",
    "credential-management": "#fbb6ce", "structured-extraction": "#4fd1c5",
    "content-preprocessing": "#ed8936", "code-generation": "#48bb78",
    "ai-automation": "#ecc94b", "inbox-cleanup": "#0bc5ea",
    "email-platform": "#a0aec0", "diagnostics": "#f56565",
    "agent-distribution": "#ed64a6", "canvas-interaction": "#38bdf8",
    "graph-editing": "#facc15", "graph-rendering": "#34d399",
    "state-management": "#c084fc", "rendering": "#38b2ac",
    "realtime-collab": "#7f9cf5", "data-structures": "#f6ad55",
    "lead-scoring": "#fb7185", "lead-ingestion": "#2dd4bf",
    "analytics": "#a3e635", "data-portability": "#fcd34d",
    "activity-tracking": "#818cf8", "messaging": "#22d3ee",
    "ai-workflow": "#c4b5fd", "codegen": "#86efac", "infrastructure": "#94a3b8",
    "design-systems": "#f0abfc", "tts": "#fda4af", "realtime": "#7dd3fc",
    "schema-migrations": "#fbbf24", "reactivity": "#a78bfa",
}

def color_for(domain):
    if domain in DOMAIN_COLORS:
        return DOMAIN_COLORS[domain]
    h = int(hashlib.md5(domain.encode()).hexdigest(), 16)
    return f"hsl({h % 360}, 65%, 62%)"

def main():
    with open(os.path.join(HERE, "graph.json"), encoding="utf-8") as f:
        data = json.load(f)

    # ensure every present domain has a color
    colors = dict(DOMAIN_COLORS)
    for n in data["nodes"]:
        colors.setdefault(n["domain"], color_for(n["domain"]))

    html = TEMPLATE.replace("__GRAPH_DATA__", json.dumps(data, ensure_ascii=False)) \
                   .replace("__DOMAIN_COLORS__", json.dumps(colors, ensure_ascii=False)) \
                   .replace("__REPO__", REPO).replace("__BRANCH__", BRANCH)

    with open(os.path.join(HERE, "graph.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote graph.html · {len(data['nodes'])} nodes · {len(data['edges'])} edges")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>repo-brain knowledge graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden; -webkit-tap-highlight-color: transparent; }
  #graph-container { position: fixed; inset: 0; }
  svg { width: 100%; height: 100%; display: block; touch-action: none; }

  #search-box { position: absolute; top: 14px; left: 14px; z-index: 10; }
  #search-box input { background: #161b22ee; border: 1px solid #30363d; color: #e6edf3; padding: 9px 12px; border-radius: 8px; width: min(260px, 60vw); font-size: 14px; outline: none; }
  #search-box input:focus { border-color: #58a6ff; }

  #stats { position: absolute; top: 14px; right: 14px; background: #161b22cc; border: 1px solid #30363d; border-radius: 8px; padding: 6px 12px; font-size: 12px; color: #8b949e; z-index: 10; }
  #fit-btn { position: absolute; top: 52px; right: 14px; z-index: 10; background: #161b22cc; border: 1px solid #30363d; border-radius: 8px; color: #c9d1d9; padding: 6px 12px; font-size: 12px; cursor: pointer; }
  #fit-btn:hover { background: #21262d; }

  .node circle { cursor: pointer; stroke-width: 2; transition: stroke .15s; }
  .node circle:hover { stroke: #fff; stroke-width: 2.5; }
  .node text { font-size: 11px; fill: #e6edf3; pointer-events: none; text-anchor: middle; paint-order: stroke; stroke: #0d1117; stroke-width: 3px; stroke-linejoin: round; }
  .link { stroke: #30363d; stroke-opacity: .7; }
  .link.depends-on { stroke: #58a6ff; stroke-opacity: .5; }
  .link.same-repo { stroke: #3fb950; stroke-opacity: .4; }
  .link.alternative-to { stroke: #f78166; stroke-opacity: .4; stroke-dasharray: 4; }
  .link.same-domain { stroke: #d2a8ff; stroke-opacity: .4; stroke-dasharray: 2; }
  .link.similar-pattern { stroke: #56d364; stroke-opacity: .35; stroke-dasharray: 1 3; }
  .node.dimmed circle, .node.dimmed text { opacity: .12; }
  .link.dimmed { opacity: .04; }

  h2 { font-size: 16px; font-weight: 600; line-height: 1.4; padding-right: 24px; }
  .domain-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; }
  .repo-label { font-size: 12px; color: #8b949e; }
  .summary-text { font-size: 13px; color: #c9d1d9; line-height: 1.6; }
  .btn { display: block; padding: 9px 12px; border-radius: 6px; font-size: 13px; text-decoration: none; text-align: center; margin-top: 4px; border: 1px solid #30363d; color: #e6edf3; background: #21262d; cursor: pointer; transition: background .15s; }
  .btn:hover { background: #30363d; }
  .btn.primary { background: #1f6feb; border-color: #1f6feb; }
  .btn.primary:hover { background: #388bfd; }

  #panel { position: absolute; top: 0; right: 0; height: 100%; width: 340px; background: #161b22; border-left: 1px solid #30363d; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; z-index: 20; transform: translateX(100%); transition: transform .18s ease; }
  #panel.open { transform: translateX(0); }
  #close-panel { position: absolute; top: 12px; right: 12px; background: none; border: none; color: #8b949e; cursor: pointer; font-size: 20px; line-height: 1; }

  #legend { position: absolute; bottom: 14px; left: 14px; background: #161b22cc; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; font-size: 12px; max-height: 42vh; overflow-y: auto; z-index: 10; }
  #legend h4 { color: #8b949e; margin-bottom: 8px; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }
  #legend.collapsed .legend-body { display: none; }
  #legend-toggle { cursor: pointer; user-select: none; }
  .legend-cols { columns: 2; column-gap: 16px; }
  .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; break-inside: avoid; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .legend-line { width: 20px; height: 2px; flex-shrink: 0; }

  /* ---- responsive: phones / narrow ---- */
  @media (max-width: 720px) {
    #panel { width: 100%; height: 62%; top: auto; bottom: 0; border-left: none; border-top: 1px solid #30363d; border-radius: 14px 14px 0 0; transform: translateY(100%); }
    #panel.open { transform: translateY(0); }
    #legend { font-size: 11px; max-height: 30vh; bottom: 10px; }
    .legend-cols { columns: 1; }
    #search-box input { width: 56vw; }
    #stats { font-size: 11px; }
  }
</style>
</head>
<body>
<div id="graph-container">
  <div id="search-box"><input type="text" id="search" placeholder="Search nodes…" autocomplete="off"></div>
  <div id="stats"></div>
  <button id="fit-btn" title="Fit graph to screen">Fit ⤢</button>
  <div id="legend">
    <h4 id="legend-toggle">Legend ▾</h4>
    <div class="legend-body">
      <div class="legend-cols" id="domain-legend"></div>
      <h4 style="margin-top:10px">Edges</h4>
      <div class="legend-item"><div class="legend-line" style="background:#58a6ff"></div><span>depends-on</span></div>
      <div class="legend-item"><div class="legend-line" style="background:#3fb950"></div><span>same-repo</span></div>
      <div class="legend-item"><div class="legend-line" style="border-top:2px dashed #f78166;height:0"></div><span>alternative-to</span></div>
      <div class="legend-item"><div class="legend-line" style="border-top:2px dashed #d2a8ff;height:0"></div><span>same-domain</span></div>
      <div class="legend-item"><div class="legend-line" style="border-top:2px dotted #56d364;height:0"></div><span>similar-pattern</span></div>
    </div>
  </div>
  <svg id="svg"></svg>
</div>
<div id="panel">
  <button id="close-panel">✕</button>
  <div id="panel-content"></div>
</div>
<script>
const GRAPH_DATA = __GRAPH_DATA__;
const DOMAIN_COLORS = __DOMAIN_COLORS__;
const REPO = "__REPO__", BRANCH = "__BRANCH__";
const docURL = p => `https://github.com/${REPO}/blob/${BRANCH}/${p}`;
const colorOf = d => DOMAIN_COLORS[d] || '#aaa';

init(GRAPH_DATA);

function init(data) {
  const nodes = data.nodes.map(n => ({ ...n }));
  const nodeIds = new Set(nodes.map(n => n.id));
  const edges = data.edges
    .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
    .map(e => ({ source: e.from, target: e.to, type: e.type }));

  // legend
  const dl = document.getElementById('domain-legend');
  [...new Set(nodes.map(n => n.domain))].sort().forEach(d => {
    const it = document.createElement('div');
    it.className = 'legend-item';
    it.innerHTML = `<div class="legend-dot" style="background:${colorOf(d)}"></div><span>${d}</span>`;
    dl.appendChild(it);
  });
  document.getElementById('stats').textContent = `${nodes.length} nodes · ${edges.length} edges`;
  const lg = document.getElementById('legend');
  document.getElementById('legend-toggle').onclick = () => lg.classList.toggle('collapsed');
  if (window.innerWidth <= 720) lg.classList.add('collapsed');

  // edge counts → node size
  const ec = {}; nodes.forEach(n => ec[n.id] = 0);
  edges.forEach(e => { ec[e.source]++; ec[e.target]++; });
  const radius = d => 8 + Math.sqrt(ec[d.id] || 0) * 3;

  const svgEl = document.getElementById('svg');
  const svg = d3.select(svgEl);
  let width = svgEl.clientWidth, height = svgEl.clientHeight;

  const g = svg.append('g');
  const zoom = d3.zoom().scaleExtent([0.15, 4]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoom);

  const link = g.append('g').selectAll('line')
    .data(edges).join('line').attr('class', d => `link ${d.type}`);

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(110).strength(0.35))
    .force('charge', d3.forceManyBody().strength(-340))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
    .force('collision', d3.forceCollide().radius(d => radius(d) + 18));

  const node = g.append('g').selectAll('g')
    .data(nodes).join('g').attr('class', 'node')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }))
    .on('click', (e, d) => { e.stopPropagation(); showPanel(d); highlight(d); });

  svg.on('click', () => { clearHighlight(); hidePanel(); });

  node.append('circle').attr('r', radius)
    .attr('fill', d => colorOf(d.domain)).attr('stroke', '#0d1117').attr('stroke-width', 2);
  node.append('text').attr('dy', d => radius(d) + 13)
    .text(d => d.label.length > 28 ? d.label.slice(0, 27) + '…' : d.label);

  sim.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  function highlight(sel) {
    const keep = new Set([sel.id]);
    edges.forEach(e => { if (e.source.id === sel.id || e.target.id === sel.id) { keep.add(e.source.id); keep.add(e.target.id); } });
    node.classed('dimmed', d => !keep.has(d.id));
    link.classed('dimmed', e => e.source.id !== sel.id && e.target.id !== sel.id);
  }
  function clearHighlight() { node.classed('dimmed', false); link.classed('dimmed', false); }
  window._clearHighlight = clearHighlight;

  // search
  document.getElementById('search').addEventListener('input', function () {
    const q = this.value.toLowerCase().trim();
    if (!q) { clearHighlight(); return; }
    node.classed('dimmed', d =>
      !d.label.toLowerCase().includes(q) && !d.domain.toLowerCase().includes(q) && !d.repo.toLowerCase().includes(q));
    link.classed('dimmed', true);
  });

  // fit-to-view
  function fit(ms = 500) {
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
    if (!xs.length) return;
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const w = (maxX - minX) || 1, h = (maxY - minY) || 1;
    const pad = 60;
    const k = Math.min(4, Math.max(0.15, Math.min((width - pad * 2) / w, (height - pad * 2) / h)));
    const tx = width / 2 - k * (minX + maxX) / 2;
    const ty = height / 2 - k * (minY + maxY) / 2;
    svg.transition().duration(ms).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  }
  document.getElementById('fit-btn').onclick = () => fit();
  sim.on('end', () => fit(0));
  setTimeout(() => fit(600), 900);   // auto-fit once layout settles

  // responsive resize
  function onResize() {
    width = svgEl.clientWidth; height = svgEl.clientHeight;
    sim.force('center', d3.forceCenter(width / 2, height / 2))
       .force('x', d3.forceX(width / 2).strength(0.04))
       .force('y', d3.forceY(height / 2).strength(0.04));
    sim.alpha(0.3).restart();
    setTimeout(() => fit(300), 400);
  }
  window.addEventListener('resize', onResize);
  window.addEventListener('orientationchange', onResize);

  document.getElementById('close-panel').onclick = () => { clearHighlight(); hidePanel(); };
}

function showPanel(d) {
  const panel = document.getElementById('panel');
  const c = colorOf(d.domain);
  let b = '';
  if (d.study) b += `<a class="btn" href="${docURL(d.study)}" target="_blank" rel="noopener">📖 Study doc</a>`;
  if (d.build) b += `<a class="btn primary" href="${docURL(d.build)}" target="_blank" rel="noopener">🔧 Build spec</a>`;
  if (d.source) b += `<a class="btn" href="${d.source}" target="_blank" rel="noopener">🔗 Origin repo</a>`;
  if (d.notebooklm) b += `<a class="btn" href="${d.notebooklm}" target="_blank" rel="noopener">🎧 NotebookLM</a>`;
  document.getElementById('panel-content').innerHTML = `
    <h2>${d.label}</h2>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px">
      <span class="domain-badge" style="background:${c}22;color:${c};border:1px solid ${c}44">${d.domain}</span>
      <span class="repo-label">from ${d.repo}</span>
    </div>
    <p class="summary-text" style="margin-top:12px">${d.summary || ''}</p>
    <div style="margin-top:8px;display:flex;flex-direction:column;gap:6px">${b}</div>`;
  panel.classList.add('open');
}
function hidePanel() { document.getElementById('panel').classList.remove('open'); }
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
