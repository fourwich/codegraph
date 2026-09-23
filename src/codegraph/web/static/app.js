/* CodeGraph web visualizer client */
(function () {
  "use strict";

  const state = {
    nodes: [],
    decisions: [],
    ticks: [],
    backend: "sqlite",
  };

  let cy = null;
  let graphTimer = null;
  let scopeTimer = null;

  function $(id) {
    return document.getElementById(id);
  }

  function selectedKinds() {
    return Array.from(document.querySelectorAll(".kind:checked")).map((el) => el.value);
  }

  function selectedStatus() {
    return Array.from(document.querySelectorAll(".status:checked")).map((el) => el.value);
  }

  function currentDate() {
    const ticks = state.ticks;
    if (!ticks.length) return "";
    const slider = $("time");
    const idx = Math.min(ticks.length - 1, Math.max(0, Math.round((slider.value / 100) * (ticks.length - 1))));
    return ticks[idx];
  }

  function filteredNodes() {
    const kinds = new Set(selectedKinds());
    return state.nodes.filter((n) => kinds.has(n.kind));
  }

  function filteredDecisions() {
    const st = new Set(selectedStatus());
    return state.decisions.filter((d) => st.has(d.status));
  }

  function buildElements() {
    const nodes = filteredNodes().slice(0, 250);
    const decisions = filteredDecisions().slice(0, 40);
    const elements = [];
    nodes.forEach((n) => {
      const size = 28 + Math.min(28, (n.line_end - n.line_start) * 2);
      elements.push({
        data: {
          id: n.uid,
          label: n.name,
          kind: n.kind,
          type: "code",
          size,
          file_path: n.file_path,
          line_start: n.line_start,
          line_end: n.line_end,
          commit_sha: n.commit_sha,
        },
        classes: "code " + n.kind,
      });
    });
    decisions.forEach((d) => {
      elements.push({
        data: {
          id: d.uid,
          label: d.content.slice(0, 28),
          type: "decision",
          status: d.status,
          content: d.content,
          reason: d.reason,
          source_ref: d.source_ref,
          file_path: d.file_path,
          line: d.line,
          confidence: d.confidence,
        },
        classes: "decision " + d.status,
      });
    });
    return elements;
  }

  function ensureCy() {
    if (cy) return cy;
    cy = cytoscape({
      container: $("cy"),
      elements: buildElements(),
      style: [
        {
          selector: "node.code",
          style: {
            label: "data(label)",
            "background-color": "#3dffc5",
            color: "#0a0e12",
            "font-size": 10,
            width: "data(size)",
            height: "data(size)",
            "text-valign": "bottom",
            "text-margin-y": 6,
          },
        },
        {
          selector: "node.class",
          style: { "background-color": "#6ba3ff" },
        },
        {
          selector: "node.variable",
          style: { "background-color": "#8b98a8" },
        },
        {
          selector: "node.decision",
          style: {
            shape: "diamond",
            "background-color": "#ffb454",
            label: "data(label)",
            color: "#0a0e12",
            "font-size": 9,
            width: 36,
            height: 36,
            "text-valign": "bottom",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "#2a3644",
            "curve-style": "bezier",
            opacity: 0.8,
          },
        },
      ],
      layout: { name: "cose", animate: false, padding: 24 },
    });
    cy.on("tap", "node", (evt) => showDetail(evt.target.data()));
    cy.on("tap", (evt) => {
      if (evt.target === cy) clearDetail();
    });
    return cy;
  }

  function refreshGraph() {
    ensureCy();
    cy.elements().remove();
    cy.add(buildElements());
    cy.layout({ name: "cose", animate: false, padding: 24 }).run();
    $("stats").textContent =
      "nodes " + filteredNodes().length +
      " · decisions " + filteredDecisions().length +
      " · " + (state.stats ? "edges " + state.stats.edges : "edges ?");
  }

  async function loadGraph() {
    const at = currentDate();
    const scope = $("scope").value || ".";
    const url = "/api/graph?at=" + encodeURIComponent(at) + "&scope=" + encodeURIComponent(scope) + "&backend=" + state.backend;
    const res = await fetch(url);
    const data = await res.json();
    state.nodes = data.nodes || [];
    state.decisions = data.decisions || [];
    state.stats = data.stats || {};
    refreshGraph();
  }

  function showDetail(data) {
    const body = $("detail-body");
    if (data.type === "code") {
      body.innerHTML =
        "<div class='card'><strong>CodeNode</strong><br/>" +
        escapeHtml(data.label) + " (" + escapeHtml(data.kind) + ")<br/>" +
        escapeHtml(data.file_path) + ":" + data.line_start + "-" + data.line_end + "<br/>" +
        "commit " + escapeHtml((data.commit_sha || "").slice(0, 12)) +
        "</div>";
      loadWhy(data.file_path, data.line_start);
      return;
    }
    body.innerHTML =
      "<div class='card'><strong>Decision</strong><br/>" +
      escapeHtml(data.content || data.label) + "<br/>" +
      escapeHtml(data.reason || "") + "<br/>" +
      escapeHtml(data.source_ref || "") + " · " + escapeHtml(data.status || "") +
      "</div>";
  }

  async function loadWhy(file, line) {
    const url = "/api/why?file=" + encodeURIComponent(file) + "&line=" + encodeURIComponent(line) + "&backend=" + state.backend;
    const res = await fetch(url);
    const data = await res.json();
    const body = $("detail-body");
    let html = body.innerHTML;
    (data.decisions || []).slice(0, 3).forEach((d) => {
      html +=
        "<div class='card'><strong>Decision</strong><br/>" +
        escapeHtml(d.content) + "<br/>" +
        escapeHtml(d.reason || "") + "<br/>" +
        escapeHtml(d.source_ref || "") + " · " + escapeHtml(d.status) +
        "</div>";
    });
    if (!(data.decisions || []).length) {
      html += "<p class='muted'>No decision record found</p>";
    }
    body.innerHTML = html;
  }

  function clearDetail() {
    $("detail-body").innerHTML = "<div class='muted'>Select a node to view decisions.</div>";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function scheduleGraph() {
    clearTimeout(graphTimer);
    graphTimer = setTimeout(loadGraph, 300);
  }

  function scheduleScope() {
    clearTimeout(scopeTimer);
    scopeTimer = setTimeout(loadGraph, 500);
  }

  async function init() {
    const res = await fetch("/api/timeline?scope=src");
    const data = await res.json();
    state.ticks = data.ticks && data.ticks.length ? data.ticks : [""];
    $("time").max = String(Math.max(0, state.ticks.length - 1));
    $("time").value = String(state.ticks.length - 1);
    $("time-label").textContent = currentDate() || "now";
    await loadGraph();

    $("time").addEventListener("input", () => {
      $("time-label").textContent = currentDate() || "now";
      scheduleGraph();
    });
    $("scope").addEventListener("input", scheduleScope);
    document.querySelectorAll(".kind, .status").forEach((el) => {
      el.addEventListener("change", refreshGraph);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "r" || e.key === "R") {
        if (cy) cy.layout({ name: "cose", animate: false }).run();
      }
      if (e.key === "f" || e.key === "F") {
        document.documentElement.requestFullscreen?.();
      }
      if (e.key === "Escape") clearDetail();
    });
  }

  init().catch((err) => {
    $("detail-body").textContent = "Failed to load graph: " + err;
  });
})();
