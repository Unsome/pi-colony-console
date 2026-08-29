"use strict";

// 비밀번호는 정적 사이트라 소스에 노출됨 - 장식용 게이트일 뿐 진짜 보안 아님.
const ACCESS_KEY = "soju9512";

const PLANET_COLOR = {
  Lava: "var(--p-lava)", Plasma: "var(--p-plasma)", Barren: "var(--p-barren)",
  Gas: "var(--p-gas)", Oceanic: "var(--p-oceanic)", Ice: "var(--p-ice)",
  Storm: "var(--p-storm)", Temperate: "var(--p-temperate)",
};

const state = { prices: {}, priceMeta: {}, feasible: null };

// ---------- 게이트 ----------
function initGate() {
  const gate = document.getElementById("gate");
  const app = document.getElementById("app");
  const input = document.getElementById("gate-input");
  const btn = document.getElementById("gate-btn");
  const err = document.getElementById("gate-err");

  if (sessionStorage.getItem("pi_ok") === "1") { enter(); return; }

  function enter() {
    gate.classList.add("hidden");
    app.classList.remove("hidden");
    boot();
  }
  function tryEnter() {
    if (input.value === ACCESS_KEY) { sessionStorage.setItem("pi_ok", "1"); enter(); }
    else { err.textContent = "잘못된 키입니다."; input.select(); }
  }
  btn.addEventListener("click", tryEnter);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") tryEnter(); });
  input.focus();
}

// ---------- 데이터 로드 ----------
async function boot() {
  try {
    const [systems, prices] = await Promise.all([
      fetch("data/systems.json").then((r) => r.json()),
      fetch("data/prices.json").then((r) => r.json()),
    ]);
    state.prices = normalizePrices(prices);
    state.priceMeta = prices._meta || {};
    stampPrice();
    const sel = document.getElementById("system-select");
    sel.innerHTML = "";
    systems.systems.forEach((s) => {
      const o = document.createElement("option");
      o.value = s.id; o.textContent = `${s.name} · ${s.region || ""}`.trim();
      sel.appendChild(o);
    });
    sel.addEventListener("change", () => loadSystem(sel.value));
    if (systems.systems.length) loadSystem(systems.systems[0].id);
  } catch (e) {
    document.getElementById("system-head").innerHTML =
      `<p style="color:#e2745f">데이터를 불러오지 못했습니다. GitHub Pages에 data/ 폴더가 배포됐는지 확인하세요.</p>`;
  }
}

function normalizePrices(p) {
  const out = {};
  const src = p.prices || {};
  Object.keys(src).forEach((k) => { out[k] = src[k]; });
  return out;
}

function stampPrice() {
  const m = state.priceMeta;
  const el = document.getElementById("price-stamp");
  const when = m.updated ? m.updated.slice(0, 10) : "?";
  const src = (m.source || "").startsWith("ESI") ? `지타 7일평균 ${when}` : "가격: 플레이스홀더";
  el.textContent = src;
}

async function loadSystem(id) {
  const res = await fetch(`data/feasible/${id}.json`);
  state.feasible = await res.json();
  renderSystemHead();
  renderList();
  clearDetail();
}

// ---------- 렌더: 성계 헤더 ----------
function renderSystemHead() {
  const s = state.feasible.system, c = state.feasible.colony;
  const counts = {};
  s.planets.forEach((t) => (counts[t] = (counts[t] || 0) + 1));
  const chips = Object.keys(counts).map((t) =>
    `<span class="chip"><span class="dot" style="color:${PLANET_COLOR[t] || "#888"}"></span>${t}×${counts[t]}</span>`
  ).join("");
  document.getElementById("system-head").innerHTML = `
    <h1>${s.name}</h1>
    <div class="meta">
      <span>${s.region || ""}</span>
      <span>시큐리티 ${s.security}</span>
      <span>콜로니: 마이너 4 + 생산 1 · ${c.skill} · ${c.lines}라인 ${c.daily_p3}/일</span>
    </div>
    <div class="planet-strip">${chips}</div>`;
}

// ---------- 렌더: P3 리스트 (가격순) ----------
function valueOf(p3) {
  const price = state.prices[String(p3.id)] || 0;
  return { price, daily: p3.daily_units * price };
}
function fmt(n) { return Math.round(n).toLocaleString("en-US"); }

function renderList() {
  const list = document.getElementById("p3-list");
  const items = state.feasible.p3s
    .map((p) => ({ p, ...valueOf(p) }))
    .sort((a, b) => b.daily - a.daily);
  list.innerHTML = "";
  items.forEach((it, i) => {
    const li = document.createElement("li");
    li.className = "p3-row";
    li.dataset.id = it.p.id;
    const flow = it.p.production.p2_split.map((x) => x.p2).join(" + ");
    li.innerHTML = `
      <span class="p3-rank">${i + 1}</span>
      <span>
        <div class="p3-name">${it.p.name}</div>
        <div class="p3-sub">${flow}</div>
      </span>
      <span class="p3-val">
        <div class="isk">${it.daily ? fmt(it.daily) : "—"}<span style="font-size:11px;color:var(--ink-3)"> ISK/일</span></div>
        <div class="unit">${it.p.daily_units}/일 × ${it.price ? fmt(it.price) : "?"}</div>
      </span>`;
    li.addEventListener("click", () => selectP3(it.p.id, li));
    list.appendChild(li);
  });
  // 첫 항목 자동 선택
  const first = list.querySelector(".p3-row");
  if (first) selectP3(Number(first.dataset.id), first);
}

// ---------- 렌더: 콜로니 디테일 ----------
function clearDetail() {
  document.getElementById("detail").classList.add("hidden");
  document.getElementById("detail-empty").classList.remove("hidden");
}

function selectP3(id, row) {
  document.querySelectorAll(".p3-row").forEach((r) => r.classList.remove("active"));
  if (row) row.classList.add("active");
  const p = state.feasible.p3s.find((x) => x.id === id);
  if (!p) return;
  const { price, daily } = valueOf(p);

  const prodType = p.production.planet_type;
  const splitTags = p.production.p2_split
    .map((x) => `<span class="tag">${x.p2} ×${x.aif}</span>`).join("");

  const minerCards = p.miners.map((m) => `
    <div class="pcard" style="border-left-color:${PLANET_COLOR[m.planet_type] || "#888"}">
      <div class="pcard-head">
        <span class="dot" style="color:${PLANET_COLOR[m.planet_type] || "#888"}"></span>
        <span class="pcard-type">${m.planet_type}</span>
        <span class="pcard-role">MINER · P1</span>
      </div>
      <div class="pcard-body">
        <span class="arrow">추출</span> ${m.p0}
        <span class="arrow">→</span> <span class="p1">${m.p1}</span>
      </div>
      ${copyButton(m.template, `${m.p1} 마이너`)}
    </div>`).join("");

  const prodCard = `
    <div class="pcard prod">
      <div class="pcard-head">
        <span class="dot" style="color:${PLANET_COLOR[prodType] || "var(--amber)"}"></span>
        <span class="pcard-type">${prodType}</span>
        <span class="pcard-role">PRODUCTION · P2+P3</span>
      </div>
      <div class="pcard-body">
        2 × <b style="color:var(--ink)">${p.name}</b> (P3)
        <div class="split-line">${splitTags}</div>
      </div>
      ${copyButton(p.production.template, `${p.name} 생산 행성`)}
    </div>`;

  document.getElementById("detail-empty").classList.add("hidden");
  const d = document.getElementById("detail");
  d.classList.remove("hidden");
  d.innerHTML = `
    <div class="detail-title">
      <h3>${p.name}</h3>
      <span class="big">${daily ? fmt(daily) + " ISK/일" : "가격 대기"}</span>
    </div>
    <div class="detail-flow">
      ${p.daily_units}/일 · P1 4종 → <b>${p.production.p2_split.map(x=>x.p2).join(" + ")}</b> → <b>${p.name}</b>
    </div>
    <div class="colony-grid">
      ${minerCards}
      ${prodCard}
    </div>
    <div class="detail-hint">
      각 버튼이 템플릿을 클립보드에 복사합니다. 게임에서 해당 <b>행성 타입</b>에 커맨드 센터(CCU4)를 세우고
      Open Templates → Import &amp; Export → <b>Load from Clipboard</b>. 마이너의 P1을 생산 행성 런치패드로 하울링하면 가동됩니다.
    </div>`;
}

function copyButton(path, label) {
  if (!path) return `<div class="copy-btn err" style="cursor:default">템플릿 없음</div>`;
  return `<button class="copy-btn" data-path="${path}" onclick="copyTemplate(this)">
      <span class="ic">⧉</span> <span class="lbl">${label} 복사</span></button>`;
}

async function copyTemplate(btn) {
  const path = btn.dataset.path;
  const lbl = btn.querySelector(".lbl");
  try {
    const txt = await fetch(path).then((r) => {
      if (!r.ok) throw new Error("not found");
      return r.text();
    });
    await navigator.clipboard.writeText(txt);
    btn.classList.add("done"); btn.classList.remove("err");
    const prev = lbl.textContent;
    lbl.textContent = "클립보드에 복사됨";
    btn.querySelector(".ic").textContent = "✓";
    setTimeout(() => {
      btn.classList.remove("done");
      lbl.textContent = prev;
      btn.querySelector(".ic").textContent = "⧉";
    }, 1800);
  } catch (e) {
    btn.classList.add("err");
    lbl.textContent = "복사 실패 (HTTPS 필요)";
  }
}
window.copyTemplate = copyTemplate;

initGate();
