const TYPE_COLORS = {
  SUPPORTS: "#27AE60",
  RESOLVED_BY: "#F39C12",
  MONITORED_BY: "#1ABC9C",
  JUSTIFIED_BY: "#9B59B6",
  IDENTIFIES: "#3498DB",
  FOLLOWS: "#16A085",
  PRECEDES: "#7F8C8D",
  CONTRADICTS: "#E74C3C",
  NO_EDGE: "#95A5A6"
};

const NODE_COLORS = {
  global_section: "#FF6B6B",
  condition: "#BDC3C7",
  subsection: "#4ECDC4",
  assessment_goal_item: "#45B7D1",
  mtp_item: "#FFA07A",
  rec_item: "#98D8C8",
  monitor_item: "#F7DC6F",
  rationale_item: "#BB8FCE",
  reference: "#85C1E2",
  reference_item: "#85C1E2"
};

const TOOLTIP_CHAR_LIMIT = 160;
const rawNodeMap = new Map();
const rawEdgeMap = new Map();
const tooltipState = { pinned: false, type: null, id: null, expanded: false };
let tooltipEl = null;

function shorten(text, maxLen = 26) {
  if (!text) return "(untitled)";
  return text.length <= maxLen ? text : `${text.slice(0, maxLen - 3)}...`;
}

function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function inferJsonPath() {
  const fromQuery = new URLSearchParams(window.location.search).get("json");
  if (fromQuery) {
    return fromQuery.endsWith(".json") ? fromQuery : `${fromQuery}.json`;
  }

  const fileName = window.location.pathname.split("/").pop() || "";
  const match = fileName.match(/^graph_(.+)\.html$/i);
  if (match) {
    return `${match[1]}_scored.json`;
  }

  return "102983_scored.json";
}

function normalizeNode(node) {
  if (!node || !node.id) return null;
  const title = node.title || node.id;
  const type = node.type || "node";
  return {
    id: node.id,
    label: shorten(title),
    shape: "dot",
    size: 18,
    color: NODE_COLORS[type] || "#7F8C8D"
  };
}

function normalizeEdge(edge, validNodeIds) {
  if (!edge) return null;
  const from = edge.from || edge.source || edge.src;
  const to = edge.to || edge.target || edge.dst;
  if (!from || !to) return null;
  if (!validNodeIds.has(from) || !validNodeIds.has(to)) return null;
  const relation = edge.logical_type || edge.final_type || edge.type || "RELATED_TO";
  return {
    from,
    to,
    arrows: "to",
    label: relation,
    color: TYPE_COLORS[relation] || TYPE_COLORS[edge.type] || "#95A5A6",
    width: 1.6
  };
}

// ── Custom tooltip ─────────────────────────────────────────────────────────────

function createTooltipEl() {
  const el = document.createElement("div");
  el.id = "vis-custom-tooltip";
  Object.assign(el.style, {
    position: "fixed",
    display: "none",
    background: "#ffffff",
    border: "1px solid #d1d5db",
    borderRadius: "7px",
    padding: "10px 14px",
    width: "300px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.15)",
    fontSize: "13px",
    lineHeight: "1.55",
    zIndex: "9999",
    pointerEvents: "auto",
    boxSizing: "border-box",
    wordBreak: "break-word",
    color: "#1f2937"
  });
  document.body.appendChild(el);
  return el;
}

function buildNodeTooltipHtml(nodeId, expanded) {
  const raw = rawNodeMap.get(nodeId);
  if (!raw) return "<i>No data</i>";
  const title = raw.title || raw.id;
  const type = raw.type || "node";
  const fullText = String(raw.text || "").replace(/\s+/g, " ").trim();
  const truncated = fullText.length > TOOLTIP_CHAR_LIMIT;
  const displayText = (expanded || !truncated)
    ? fullText
    : fullText.slice(0, TOOLTIP_CHAR_LIMIT) + "\u2026";

  let html = `<div style="font-weight:700;margin-bottom:5px;padding-bottom:5px;border-bottom:1px solid #e5e7eb">${escapeHtml(title)}</div>`;
  html += `<div><b>ID:</b> ${escapeHtml(nodeId)}</div>`;
  html += `<div><b>Type:</b> ${escapeHtml(type)}</div>`;
  if (fullText) {
    html += `<div style="margin-top:7px;font-weight:600;color:#374151">Contained Text:</div>`;
    html += `<div style="margin-top:3px;color:#4b5563">${escapeHtml(displayText)}</div>`;
    if (truncated && !expanded) {
      html += `<div style="text-align:center;margin-top:7px"><a href="#" data-tt-action="expand" style="color:#2563eb;font-size:12px;text-decoration:none">Read more...</a></div>`;
    } else if (truncated) {
      html += `<div style="text-align:center;margin-top:7px"><a href="#" data-tt-action="collapse" style="color:#2563eb;font-size:12px;text-decoration:none">Show less</a></div>`;
    }
  }
  return html;
}

function buildEdgeTooltipHtml(edgeId) {
  const raw = rawEdgeMap.get(edgeId);
  if (!raw) return "<i>No data</i>";
  const relation = raw.logical_type || raw.final_type || raw.type || "RELATED_TO";
  const from = raw.src || raw.from || raw.source || "n/a";
  const to = raw.dst || raw.to || raw.target || "n/a";
  const schemaType = raw.schema_type || "n/a";
  const scoreText = typeof raw.score === "number" ? raw.score.toFixed(3) : "n/a";
  const strength = raw.strength || "n/a";

  let html = `<div style="font-weight:700;margin-bottom:5px;padding-bottom:5px;border-bottom:1px solid #e5e7eb">${escapeHtml(relation)}</div>`;
  html += `<div><b>Source:</b> ${escapeHtml(from)}</div>`;
  html += `<div><b>Target:</b> ${escapeHtml(to)}</div>`;
  html += `<div><b>Schema Type:</b> ${escapeHtml(schemaType)}</div>`;
  html += `<div><b>Score:</b> ${escapeHtml(scoreText)}</div>`;
  html += `<div><b>Strength:</b> ${escapeHtml(strength)}</div>`;
  return html;
}

function renderTooltip() {
  if (!tooltipEl || !tooltipState.type) return;
  const { type, id, expanded } = tooltipState;
  tooltipEl.innerHTML = type === "node"
    ? buildNodeTooltipHtml(id, expanded)
    : buildEdgeTooltipHtml(id);
}

function getClientCoords(visEvent, container) {
  if (visEvent.event && visEvent.event.clientX != null) {
    return { x: visEvent.event.clientX, y: visEvent.event.clientY };
  }
  const rect = container.getBoundingClientRect();
  return {
    x: rect.left + (visEvent.pointer?.DOM?.x || 0),
    y: rect.top + (visEvent.pointer?.DOM?.y || 0)
  };
}

function positionTooltip(clientX, clientY) {
  const margin = 14;
  tooltipEl.style.left = (clientX + margin) + "px";
  tooltipEl.style.top = (clientY + margin) + "px";
  tooltipEl.style.display = "block";

  const rect = tooltipEl.getBoundingClientRect();
  if (rect.right > window.innerWidth - 10) {
    tooltipEl.style.left = Math.max(0, clientX - rect.width - margin) + "px";
  }
  if (rect.bottom > window.innerHeight - 10) {
    tooltipEl.style.top = Math.max(0, clientY - rect.height - margin) + "px";
  }
}

function showTooltip(clientX, clientY) {
  renderTooltip();
  positionTooltip(clientX, clientY);
}

function hideTooltip() {
  if (!tooltipEl) return;
  tooltipEl.style.display = "none";
  tooltipState.pinned = false;
  tooltipState.type = null;
  tooltipState.id = null;
  tooltipState.expanded = false;
}

// ── Init ───────────────────────────────────────────────────────────────────────

async function init() {
  const status = document.getElementById("status");
  const container = document.getElementById("mynetwork");
  const graphTitle = document.getElementById("graph-title");

  tooltipEl = createTooltipEl();

  // Expand / collapse via event delegation so re-renders don't need re-binding
  tooltipEl.addEventListener("click", e => {
    const anchor = e.target.closest("[data-tt-action]");
    if (!anchor) return;
    e.preventDefault();
    e.stopPropagation();
    tooltipState.expanded = (anchor.dataset.ttAction === "expand");
    renderTooltip();
  });

  const jsonPath = inferJsonPath();
  status.textContent = `Loading ${jsonPath}...`;

  let raw;
  try {
    const response = await fetch(jsonPath, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    raw = await response.json();
  } catch (err) {
    status.textContent = `Failed to load ${jsonPath}: ${err.message}`;
    return;
  }

  const rawNodes = Array.isArray(raw.nodes) ? raw.nodes : [];
  const rawEdges = Array.isArray(raw.edges) ? raw.edges : [];

  rawNodes.forEach(n => { if (n && n.id) rawNodeMap.set(n.id, n); });
  const nodes = rawNodes.map(normalizeNode).filter(Boolean);
  const validNodeIds = new Set(nodes.map(n => n.id));

  // Assign stable integer IDs to edges so hoverEdge can look them up
  const edges = [];
  rawEdges.forEach((e, i) => {
    const normalized = normalizeEdge(e, validNodeIds);
    if (normalized) {
      normalized.id = i;
      rawEdgeMap.set(i, e);
      edges.push(normalized);
    }
  });

  if (!nodes.length) {
    status.textContent = `No valid nodes found in ${jsonPath}.`;
    return;
  }

  const data = {
    nodes: new vis.DataSet(nodes),
    edges: new vis.DataSet(edges)
  };

  const options = {
    physics: {
      enabled: true,
      barnesHut: {
        gravitationalConstant: -18000,
        centralGravity: 0.25,
        springLength: 185,
        springConstant: 0.045
      },
      stabilization: { iterations: 220, fit: true }
    },
    interaction: {
      hover: true,
      tooltipDelay: 99999, // built-in tooltip disabled (no title on nodes/edges)
      navigationButtons: true,
      keyboard: true
    },
    edges: {
      smooth: { type: "dynamic" },
      font: { size: 10, color: "#1f2937", strokeWidth: 0 }
    },
    nodes: {
      font: { size: 11, color: "#111827" },
      borderWidth: 1
    }
  };

  const network = new vis.Network(container, data, options);

  // ── Hover: show non-pinned tooltip ────────────────────────────────────────
  network.on("hoverNode", event => {
    if (tooltipState.pinned) return;
    tooltipState.type = "node";
    tooltipState.id = event.node;
    tooltipState.expanded = false;
    const { x, y } = getClientCoords(event, container);
    showTooltip(x, y);
  });

  network.on("blurNode", () => {
    if (!tooltipState.pinned) hideTooltip();
  });

  network.on("hoverEdge", event => {
    if (tooltipState.pinned) return;
    tooltipState.type = "edge";
    tooltipState.id = event.edge;
    tooltipState.expanded = false;
    const { x, y } = getClientCoords(event, container);
    showTooltip(x, y);
  });

  network.on("blurEdge", () => {
    if (!tooltipState.pinned) hideTooltip();
  });

  // ── Click: pin tooltip to node/edge; empty canvas dismisses ──────────────
  network.on("click", event => {
    if (event.nodes.length > 0) {
      tooltipState.pinned = true;
      tooltipState.type = "node";
      tooltipState.id = event.nodes[0];
      tooltipState.expanded = false;
      const { x, y } = getClientCoords(event, container);
      showTooltip(x, y);
    } else if (event.edges.length > 0) {
      tooltipState.pinned = true;
      tooltipState.type = "edge";
      tooltipState.id = event.edges[0];
      tooltipState.expanded = false;
      const { x, y } = getClientCoords(event, container);
      showTooltip(x, y);
    } else {
      hideTooltip();
    }
  });

  // Dismiss pinned tooltip when clicking anywhere outside the panel and canvas
  document.addEventListener("click", e => {
    if (!tooltipState.pinned) return;
    if (tooltipEl.contains(e.target)) return;
    if (container.contains(e.target)) return; // vis-network click event handles this
    hideTooltip();
  });

  graphTitle.textContent = `Network Graph (${raw.doc_id || jsonPath.replace(/\.json$/i, "")})`;
  status.textContent = `Loaded ${nodes.length} nodes and ${edges.length} linked edges (${rawEdges.length} raw edges) from ${jsonPath}`;
}

init();