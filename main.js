/* CodeGraph 产品站交互：英雄图谱 + 终端演示 */

(function () {
  "use strict";

  /* ---------- Nav scroll state ---------- */
  const nav = document.querySelector(".nav");
  const onScroll = () => {
    if (!nav) return;
    nav.classList.toggle("is-scrolled", window.scrollY > 8);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- Hero graph ---------- */
  const NODES = [
    { id: "fn_auth", label: "authenticate()", sub: "src/auth.ts:42", x: 120, y: 90, type: "code" },
    { id: "cls_user", label: "class User", sub: "src/models.ts:12", x: 320, y: 70, type: "code" },
    { id: "var_salt", label: "BCRYPT_ROUNDS", sub: "src/config.ts:8", x: 220, y: 190, type: "code" },
    { id: "fn_hash", label: "hashPassword()", sub: "src/crypto.ts:21", x: 400, y: 210, type: "code" },
    { id: "dec_01", label: "Decision #01", sub: "为何用 bcrypt", x: 90, y: 280, type: "decision" },
    { id: "dec_02", label: "Decision #02", sub: "轮数定为 12", x: 300, y: 320, type: "decision" },
    { id: "git_t", label: "2024-11-02", sub: "commit a3f91c", x: 430, y: 100, type: "git" },
  ];

  const EDGES = [
    { from: "fn_auth", to: "cls_user", type: "uses" },
    { from: "fn_auth", to: "var_salt", type: "uses" },
    { from: "fn_hash", to: "var_salt", type: "uses" },
    { from: "fn_auth", to: "fn_hash", type: "uses" },
    { from: "dec_01", to: "fn_hash", type: "decided" },
    { from: "dec_02", to: "var_salt", type: "decided" },
    { from: "git_t", to: "fn_auth", type: "time" },
    { from: "dec_01", to: "dec_02", type: "decided" },
  ];

  const COLORS = {
    code: "#3dffc5",
    decision: "#ffb454",
    git: "#6ba3ff",
  };

  function buildGraph() {
    const edgesG = document.getElementById("graph-edges");
    const nodesG = document.getElementById("graph-nodes");
    if (!edgesG || !nodesG) return;

    const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

    EDGES.forEach((e, i) => {
      const a = byId[e.from];
      const b = byId[e.to];
      if (!a || !b) return;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const midX = (a.x + b.x) / 2;
      const midY = (a.y + b.y) / 2 - 18;
      const d = `M ${a.x} ${a.y} Q ${midX} ${midY} ${b.x} ${b.y}`;
      path.setAttribute("d", d);
      path.setAttribute("class", `graph-edge graph-edge--${e.type}`);
      path.style.strokeDasharray = e.type === "time" ? "2 4" : e.type === "decided" ? "4 3" : "220";
      if (e.type === "uses") {
        path.style.strokeDasharray = "220";
        path.style.strokeDashoffset = "220";
        path.style.animation = `dash-in 1.1s ease ${0.15 * i}s forwards`;
      }
      edgesG.appendChild(path);
    });

    NODES.forEach((n, i) => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("transform", `translate(${n.x}, ${n.y})`);
      g.style.opacity = "0";
      g.style.animation = `node-in 0.55s ease ${0.12 * i}s forwards`;

      const w = n.type === "decision" ? 118 : 112;
      const h = 44;
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", -w / 2);
      rect.setAttribute("y", -h / 2);
      rect.setAttribute("width", w);
      rect.setAttribute("height", h);
      rect.setAttribute("rx", n.type === "decision" ? 8 : 10);
      rect.setAttribute("fill", n.type === "decision" ? "rgba(255,180,84,0.12)" : n.type === "git" ? "rgba(107,163,255,0.12)" : "rgba(61,255,197,0.1)");
      rect.setAttribute("stroke", COLORS[n.type]);
      rect.setAttribute("stroke-width", "1.2");

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", -w / 2 + 12);
      circle.setAttribute("cy", 0);
      circle.setAttribute("r", 3.5);
      circle.setAttribute("fill", COLORS[n.type]);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "graph-node-label");
      label.setAttribute("x", -w / 2 + 22);
      label.setAttribute("y", -4);
      label.textContent = n.label;

      const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
      sub.setAttribute("class", "graph-node-sub");
      sub.setAttribute("x", -w / 2 + 22);
      sub.setAttribute("y", 12);
      sub.textContent = n.sub;

      g.appendChild(rect);
      g.appendChild(circle);
      g.appendChild(label);
      g.appendChild(sub);
      nodesG.appendChild(g);
    });
  }

  // keyframes injected once (SVG attr animation via CSS)
  const style = document.createElement("style");
  style.textContent = `
    @keyframes dash-in { to { stroke-dashoffset: 0; } }
    @keyframes node-in { to { opacity: 1; } }
    @keyframes blink { 50% { opacity: 0; } }
  `;
  document.head.appendChild(style);
  buildGraph();

  /* ---------- Terminal typing demo ---------- */
  const terminalBody = document.getElementById("terminal-body");
  const replayBtn = document.getElementById("replay-btn");

  const script = [
    { kind: "type", html: `<span class="t-prompt">$</span> <span class="t-cmd">codegraph why src/auth.ts:42</span>` },
    { kind: "wait", ms: 350 },
    { kind: "line", html: `<span class="t-muted">查询图谱… 命中 1 条决策链 · 2 个关联讨论</span>` },
    { kind: "wait", ms: 280 },
    {
      kind: "card",
      html: `
        <div class="t-card">
          <div class="t-card__title">DECISION · accepted · 2024-11-02</div>
          <div class="t-card__row"><strong>内容：</strong>密码哈希使用 bcrypt，成本因子固定为 12</div>
          <div class="t-card__row"><strong>原因：</strong>兼容既有 User 表；硬件哈希在当时威胁模型下够用</div>
          <div class="t-card__row"><strong>备选：</strong>Argon2id（否决：迁移成本高）· PBKDF2（否决：库支持弱）</div>
          <div class="t-card__row"><strong>来源：</strong><span class="t-git">PR #48</span> · Issue #31 · ADR-003</div>
          <div class="t-card__row"><strong>依据代码：</strong><span class="t-ok">authenticate()</span> · <span class="t-ok">BCRYPT_ROUNDS</span></div>
          <div class="t-card__row"><strong>状态：</strong>现行有效 · valid_from 2024-11-02</div>
        </div>`,
    },
    { kind: "wait", ms: 400 },
    { kind: "line", html: `<span class="t-muted">下一步：</span><span class="t-git">codegraph decisions --file src/auth.ts --timeline</span>` },
  ];

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async function typeLine(html) {
    const line = document.createElement("div");
    line.className = "t-line";
    terminalBody.appendChild(line);

    // 逐字效果仅对纯文本命令；结构 HTML 用分段淡入更稳
    const temp = document.createElement("div");
    temp.innerHTML = html;
    // 对 command 行做打字机
    if (html.includes("t-cmd")) {
      const prompt = temp.querySelector(".t-prompt");
      const cmd = temp.querySelector(".t-cmd");
      line.appendChild(prompt.cloneNode(true));
      line.appendChild(document.createTextNode(" "));
      const span = document.createElement("span");
      span.className = "t-cmd";
      line.appendChild(span);
      const text = cmd ? cmd.textContent : "";
      for (let i = 0; i < text.length; i++) {
        span.textContent += text[i];
        await sleep(28 + Math.random() * 36);
      }
    } else {
      line.innerHTML = html;
    }
  }

  let runToken = 0;

  async function runTerminal() {
    const token = ++runToken;
    terminalBody.innerHTML = "";
    for (const step of script) {
      if (token !== runToken) return;
      if (step.kind === "wait") {
        await sleep(step.ms);
      } else if (step.kind === "type" || step.kind === "line") {
        await typeLine(step.html);
      } else if (step.kind === "card") {
        const wrap = document.createElement("div");
        wrap.innerHTML = step.html.trim();
        wrap.style.opacity = "0";
        wrap.style.transform = "translateY(8px)";
        wrap.style.transition = "opacity 0.35s ease, transform 0.35s ease";
        terminalBody.appendChild(wrap);
        requestAnimationFrame(() => {
          wrap.style.opacity = "1";
          wrap.style.transform = "none";
        });
      }
      if (token !== runToken) return;
    }
  }

  if (replayBtn) {
    replayBtn.addEventListener("click", () => runTerminal());
  }

  // 进入视口后自动播放
  const term = document.getElementById("cli-terminal");
  if (term && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            runTerminal();
            io.disconnect();
          }
        });
      },
      { threshold: 0.35 }
    );
    io.observe(term);
  } else {
    runTerminal();
  }

  /* ---------- Scroll reveal ---------- */
  const revealTargets = document.querySelectorAll(
    ".pain-card, .arch__node, .why-point, .cmd, .schema-card, .diff, .stack-table, .terminal"
  );
  revealTargets.forEach((el) => el.classList.add("reveal"));

  if ("IntersectionObserver" in window) {
    const revealIo = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealIo.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -24px 0px" }
    );
    revealTargets.forEach((el) => revealIo.observe(el));
  } else {
    revealTargets.forEach((el) => el.classList.add("is-visible"));
  }
})();
