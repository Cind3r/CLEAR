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
  reference: "#85C1E2"
};

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
  const body = node.text ? `<br><b>Text:</b> ${escapeHtml(node.text)}` : "";
  const type = node.type || "node";

  return {
    id: node.id,
    label: shorten(title),
    shape: "dot",
    size: 18,
    color: NODE_COLORS[type] || "#7F8C8D",
    title: `<b>${escapeHtml(title)}</b><br><b>ID:</b> ${escapeHtml(node.id)}<br><b>Type:</b> ${escapeHtml(type)}${body}`
  };
}

function normalizeEdge(edge, validNodeIds) {
  if (!edge) return null;

  const from = edge.from || edge.source;
  const to = edge.to || edge.target;
  if (!from || !to) return null;
  if (!validNodeIds.has(from) || !validNodeIds.has(to)) return null;

  const relation = edge.logical_type || edge.type || "RELATED_TO";

  return {
    from,
    to,
    arrows: "to",
    label: relation,
    color: TYPE_COLORS[relation] || "#95A5A6",
    width: 1.6,
    title: `<b>${escapeHtml(relation)}</b>`
  };
}

async function init() {
  const status = document.getElementById("status");
  const container = document.getElementById("mynetwork");
  const graphTitle = document.getElementById("graph-title");

  const jsonPath = inferJsonPath();
  status.textContent = `Loading ${jsonPath}...`;

  let raw;
  try {
    const response = await fetch(jsonPath, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    raw = await response.json();
  } catch (err) {
    status.textContent = `Failed to load ${jsonPath}: ${err.message}`;
    return;
  }

  const rawNodes = Array.isArray(raw.nodes) ? raw.nodes : [];
  const rawEdges = Array.isArray(raw.edges) ? raw.edges : [];
  const nodes = rawNodes.map(normalizeNode).filter(Boolean);
  const validNodeIds = new Set(nodes.map((n) => n.id));
  const edges = rawEdges.map((e) => normalizeEdge(e, validNodeIds)).filter(Boolean);

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
      stabilization: {
        iterations: 220,
        fit: true
      }
    },
    interaction: {
      hover: true,
      tooltipDelay: 140,
      navigationButtons: true,
      keyboard: true
    },
    edges: {
      smooth: {
        type: "dynamic"
      },
      font: {
        size: 10,
        color: "#1f2937",
        strokeWidth: 0
      }
    },
    nodes: {
      font: {
        size: 11,
        color: "#111827"
      },
      borderWidth: 1
    }
  };

  new vis.Network(container, data, options);

  graphTitle.textContent = `Network Graph (${raw.doc_id || jsonPath.replace(/\.json$/i, "")})`;
  status.textContent = `Loaded ${nodes.length} nodes and ${edges.length} edges from ${jsonPath}`;
}

init();