"use strict";
(() => {
  const FACTORS = ["momentum", "liquidity", "foreign", "imbalance"];
  const FLABEL = { momentum: "Động lượng", liquidity: "Thanh khoản", foreign: "Dòng tiền ngoại", imbalance: "Cung–cầu" };
  const FCOLOR = { momentum: "#4C8DFF", liquidity: "#31C2D6", foreign: "#A48BFF", imbalance: "#E58BC8" };
  const FRGB = { momentum: "76, 141, 255", liquidity: "49, 194, 214", foreign: "164, 139, 255", imbalance: "229, 139, 200" };
  const VIEWS = ["rank", "history", "validate", "quality", "method"];
  const RANK_FILTERS = ["all", "top", "rising", "unranked"];
  const MODE = { demo: "Demo", replay: "Phát lại", live: "Trực tiếp" };
  const BAD = new Set(["disconnected", "halt", "invalid"]);
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nf = (d) => new Intl.NumberFormat("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmt = (x, d = 1) => (x == null || Number.isNaN(x) ? "—" : nf(d).format(x));
  const signed = (x, d) => (x == null ? "—" : (x > 0 ? "+" : x < 0 ? "−" : "") + nf(d).format(Math.abs(x)));
  const money = (x) => (x == null ? "—" : x >= 1e9 ? `${fmt(x / 1e9, 1)} tỷ` : `${fmt(x / 1e6, 0)} triệu`);
  const clock = (iso) => (iso && /T(\d\d:\d\d:\d\d)/.exec(iso) || [, "--:--:--"])[1];
  const day = (iso) => { const m = iso && /^(\d{4})-(\d\d)-(\d\d)/.exec(iso); return m ? `${m[3]}/${m[2]}/${m[1]}` : ""; };
  const icon = (name) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  const state = {
    ctx: null, source: null, run: null, point: null, weights: "balanced", foreign: "value", group: "VN30",
    sort: { key: "rank", dir: 1 }, search: "", min: 0, rankFilter: "all", selected: null, view: "rank", compare: "prev",
    runs: [], timeline: [], data: null, timer: null, refresh: 0, requestId: 0,
    chart: "score", heat: null, heatKey: "", valid: null, validKey: "",
  };

  // ---------- URL state ----------
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    for (const [k, key] of [["src", "source"], ["run", "run"], ["pt", "point"], ["g", "group"], ["w", "weights"], ["f", "foreign"], ["sel", "selected"], ["view", "view"], ["cmp", "compare"], ["ch", "chart"], ["rf", "rankFilter"]]) {
      if (p.has(k)) state[key] = p.get(k);
    }
  }
  function writeHash() {
    const p = new URLSearchParams();
    const put = (k, v) => v && p.set(k, v);
    put("src", state.source); put("run", state.run); put("pt", state.point); put("g", state.group);
    put("w", state.weights); put("f", state.foreign); put("sel", state.selected); put("view", state.view); p.set("cmp", state.compare || ""); put("ch", state.chart);
    if (state.rankFilter !== "all") put("rf", state.rankFilter);
    history.replaceState(null, "", "#" + p.toString());
  }

  async function get(path, params) {
    const url = path + (params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== "")) : "");
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    const body = await res.json().catch(() => ({ error: "Phản hồi không đọc được." }));
    if (!res.ok) throw new Error(body.error || `Lỗi ${res.status}`);
    return body;
  }

  // ---------- controls ----------
  function fillSelect(el, items, value, label = (x) => x.label) {
    el.innerHTML = items.map((x) => `<option value="${esc(x.id)}"${x.id === value ? " selected" : ""}>${esc(label(x))}</option>`).join("");
  }
  function segmented(el, items, value, onPick) {
    el.innerHTML = items.map((x) => `<button type="button" data-id="${esc(x.id)}" aria-pressed="${x.id === value}">${esc(x.label)}</button>`).join("");
    el.onclick = (e) => { const b = e.target.closest("button"); if (b) onPick(b.dataset.id); };
  }

  async function init() {
    readHash();
    state.group = "VN30";  // scope is VN30 only; old links may still carry g=HNX30
    if (!VIEWS.includes(state.view)) state.view = "rank";
    if (!["score", "scatter"].includes(state.chart)) state.chart = "score";
    if (!RANK_FILTERS.includes(state.rankFilter)) state.rankFilter = "all";
    try {
      state.ctx = await get("/api/context");
    } catch (err) { return fatal(err); }
    const ctx = state.ctx;
    $("mode-chip").textContent = MODE[ctx.mode] || ctx.mode;
    if (!ctx.sources.length) return fatal(new Error("Chưa có kho dữ liệu cho chế độ này. Chạy collector hoặc đặt APP_MODE=demo."));
    if (!ctx.sources.some((s) => s.id === state.source)) state.source = ctx.sources[0].id;
    fillSelect($("source"), ctx.sources, state.source);
    $("f-source").hidden = ctx.sources.length < 2;
    bindWeights(); bindForeign();
    fillCompare();
    if (ctx.mode === "live") {
      $("f-refresh").hidden = false; $("f-point").hidden = true;
      fillSelect($("refresh"), ctx.refresh.map((s) => ({ id: String(s), label: s ? `Mỗi ${s} giây` : "Tắt" })), "0");
    }
    bindEvents();
    await loadRuns();
  }
  const isDaily = () => state.source === "daily";
  function fillCompare() {
    const all = isDaily() ? [{ id: "prev", label: "Phiên liền trước" }]
      : state.ctx.compare.map((c) => ({ id: c.id, label: c.id === "prev" ? "Mốc liền trước" : c.label }));
    const cmp = [...all, { id: "", label: "Không so sánh" }];
    if (!cmp.some((c) => c.id === state.compare)) state.compare = "prev";
    fillSelect($("compare"), cmp, state.compare);
  }
  const shownFactors = () => (isDaily() ? FACTORS.filter((f) => f !== "imbalance") : FACTORS);
  function bindWeights() {
    const daily = isDaily();
    const items = state.ctx.weights.map((w) => ({ id: w.id, label: w.id === "balanced" ? (daily ? "33/33/33" : "25/25/25/25") : (daily ? "50/25/25" : "40/20/20/20") }));
    const pick = (id) => { state.weights = id; segmented($("weights"), items, id, pick); loadSnapshot(); };
    segmented($("weights"), items, state.weights, pick);
    $("weights").title = daily ? "Động lượng / thanh khoản / khối ngoại (cuối ngày)" : "Động lượng / thanh khoản / khối ngoại / cung–cầu";
  }
  function bindForeign() {
    const pick = (id) => { state.foreign = id; segmented($("foreign"), state.ctx.foreign, id, pick); loadSnapshot(); };
    segmented($("foreign"), state.ctx.foreign, state.foreign, pick);
  }

  function bindEvents() {
    $("source").onchange = (e) => { state.source = e.target.value; state.run = null; state.point = null; state.selected = null; bindWeights(); fillCompare(); loadRuns(); };
    $("run").onchange = (e) => { state.run = e.target.value; state.point = null; loadTimeline(); };
    $("point").onchange = (e) => { state.point = e.target.value; loadSnapshot(); };
    $("compare").onchange = (e) => { state.compare = e.target.value; loadSnapshot(); };
    $("prev").onclick = () => step(-1);
    $("next").onclick = () => step(1);
    $("reload").onclick = () => loadSnapshot();
    $("refresh").onchange = (e) => setRefresh(Number(e.target.value));
    $("search").oninput = (e) => { state.search = e.target.value.trim().toUpperCase(); renderRank(); };
    $("min").oninput = (e) => { state.min = Math.max(0, Math.min(100, Number(e.target.value) || 0)); renderRank(); };
    $("rank-filter").onclick = (e) => {
      const button = e.target.closest("button[data-filter]");
      if (!button) return;
      state.rankFilter = button.dataset.filter;
      renderRank();
    };
    $("summary-unranked").onclick = () => {
      state.view = "rank";
      state.rankFilter = "unranked";
      state.search = "";
      $("search").value = "";
      render();
      $("rank-filter").querySelector('[data-filter="unranked"]').focus();
    };
    $("export").onclick = () => {
      const q = new URLSearchParams({ source: state.source, run: state.run || "", point: state.point || "", weights: state.weights, foreign: state.foreign, group: state.group, compare: state.compare || "" });
      location.href = "/api/export.csv?" + q;
    };
    document.querySelectorAll(".group-tabs button").forEach((b) => (b.onclick = () => { state.group = b.dataset.group; state.selected = null; render(); }));
    document.querySelectorAll(".view-tabs button").forEach((b) => (b.onclick = () => { state.view = b.dataset.view; render(); }));
    $("chart-mode").onclick = (e) => {
      const b = e.target.closest("button");
      if (!b || b.dataset.id === state.chart) return;
      state.chart = b.dataset.id; writeHash(); renderChart();
    };
  }

  function setRefresh(seconds) {
    clearInterval(state.timer);
    state.refresh = seconds;
    if (seconds) state.timer = setInterval(loadSnapshot, seconds * 1000);
  }

  function step(delta) {
    const ids = state.timeline.map((p) => p.id);
    const i = ids.indexOf(state.point);
    const next = ids[Math.max(0, Math.min(ids.length - 1, (i < 0 ? ids.length - 1 : i) + delta))];
    if (next && next !== state.point) { state.point = next; $("point").value = next; loadSnapshot(); }
  }

  async function loadRuns() {
    try {
      state.runs = await get("/api/runs", { source: state.source });
    } catch (err) { return fatal(err); }
    if (!state.runs.some((r) => r.id === state.run)) state.run = state.runs[0] && state.runs[0].id;
    fillSelect($("run"), state.runs, state.run);
    $("f-run").hidden = state.runs.length < 2 && (state.source === "demo-board" || isDaily());
    if (state.ctx.mode === "live") $("f-point").hidden = !isDaily();
    document.querySelector(".legend-keys span:nth-child(4)").hidden = isDaily();
    await loadTimeline();
  }

  async function loadTimeline() {
    if (state.ctx.mode === "live" && !isDaily()) { state.point = null; return loadSnapshot(); }
    try {
      state.timeline = await get("/api/timeline", { source: state.source, run: state.run });
    } catch (err) { return fatal(err); }
    const ids = state.timeline.map((p) => p.id);
    if (!ids.includes(state.point)) {
      const data = state.timeline.filter((p) => p.kind === "data");
      state.point = (data.length ? data[data.length - 1] : state.timeline[state.timeline.length - 1] || {}).id || null;
    }
    fillSelect($("point"), state.timeline.slice().reverse(), state.point,
      (p) => p.kind === "day" ? p.label : `${clock(p.at)} · ${p.label}${/^\d+$/.test(p.id) ? " · #" + p.id : ""}`);
    $("f-point").hidden = !state.timeline.length;
    await loadSnapshot();
  }

  async function loadSnapshot() {
    const id = ++state.requestId;
    document.body.classList.add("loading");
    try {
      const data = await get("/api/snapshot", { source: state.source, run: state.run, point: state.point, weights: state.weights, foreign: state.foreign, compare: state.compare });
      if (id !== state.requestId) return;
      state.data = data;
      render();
    } catch (err) {
      if (id === state.requestId) showError(err);
    } finally {
      if (id === state.requestId) document.body.classList.remove("loading");
    }
  }

  // ---------- rendering ----------
  function groupData() { return state.data && state.data.groups[state.group]; }
  function visibleRows() {
    const g = groupData();
    if (!g) return [];
    let rows = g.rows.filter((r) => !state.search || r.symbol.includes(state.search));
    if (state.rankFilter === "unranked") rows = rows.filter((r) => r.rank == null);
    else if (state.min > 0) rows = rows.filter((r) => r.total != null && r.total >= state.min);
    if (state.rankFilter === "top") rows = rows.filter((r) => r.rank != null && r.rank <= 5);
    if (state.rankFilter === "rising") rows = rows.filter((r) => r.rank_change > 0);
    const { key, dir } = state.sort;
    const val = (r) => key === "rank" ? r.rank : key === "symbol" ? r.symbol : key === "total" ? r.total : r.scores[key];
    return rows.slice().sort((a, b) => {
      if ((a.rank == null) !== (b.rank == null)) return a.rank == null ? 1 : -1;
      const x = val(a), y = val(b);
      if (x == null || y == null) return a.symbol.localeCompare(b.symbol);
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * (key === "rank" || key === "symbol" ? dir : -dir);
    });
  }

  function render() {
    const d = state.data;
    if (!d) return;
    writeHash();
    const conn = d.connection;
    $("conn").innerHTML = `<span class="dot ${esc(conn.severity)}"></span><span>${esc(conn.label)}${conn.epoch ? ` · lần ${conn.epoch}` : ""}</span>`;
    $("clock").textContent = d.method_kind === "daily" ? day(d.as_of) : clock(d.as_of);
    // The app's run mode says nothing about the data: real daily data must not sit beside a "Demo" label.
    $("mode-chip").textContent = d.source_kind === "daily" ? "SSI thật" : (MODE[d.mode] || d.mode);
    $("scope-chip").hidden = !d.scope_note;
    if (d.scope_note) { $("scope-chip").textContent = d.scope_note.label; $("scope-chip").title = d.scope_note.detail; }
    $("synthetic-chip").hidden = !d.synthetic;
    $("unverified-chip").hidden = d.verified;
    for (const name of ["VN30"]) {
      const g = d.groups[name];
      document.querySelector(`[data-count="${name}"]`).textContent = g ? `${g.ranked}/${g.members}` : "";
    }
    document.querySelectorAll(".group-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.group === state.group)));
    document.querySelectorAll(".view-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === state.view)));
    for (const v of VIEWS) $("view-" + v).hidden = state.view !== v;
    $("footer-source").textContent = `Nguồn ${d.source === "synthetic" ? "giả lập" : d.source.toUpperCase()}${d.profile ? " · " + d.profile : ""} · giờ UTC+7`;
    const wl = isDaily() ? (d.weights.id === "balanced" ? "33/33/33" : "50/25/25") : (d.weights.id === "balanced" ? "25/25/25/25" : "40/20/20/20");
    $("controls-summary").textContent = `${isDaily() ? day(d.as_of) : clock(d.as_of)} · ${wl} · ${d.foreign === "value" ? "ngoại theo giá trị" : "ngoại theo khối lượng"}${compareAt() ? " · so với " + compareAt() : ""}`;
    renderPulse(); renderMetrics(); renderNotice(); renderRank(); renderQuality(); renderMethod();
    renderHistory(); renderValidate();
  }

  function renderMetrics() {
    const d = state.data, g = groupData();
    const leader = g && g.rows.find((r) => r.rank === 1);
    renderSummary(g, leader);
    $("m-ranked").textContent = g ? `${g.ranked}/${g.members}` : "–";
    $("m-ranked-note").textContent = g && g.ranked ? `${state.group} · nhóm so sánh ${g.cohort_size} mã` : `${state.group} · chưa đủ điều kiện`;
    $("m-leader").textContent = leader ? leader.symbol : "—";
    $("m-leader-note").textContent = !leader ? "chưa có hạng"
      : `${fmt(leader.total)} điểm` + (leader.rank_change > 0 ? ` · từ hạng ${leader.prev_rank}` : leader.prev_rank === 1 ? " · giữ hạng 1" : "");
    $("m-asof").textContent = d.method_kind === "daily" ? day(d.as_of) : clock(d.as_of);
    $("m-asof-note").textContent = d.method_kind === "daily" ? "cuối phiên" : day(d.as_of);
    if (d.freshness_seconds != null) {
      $("m-fresh").textContent = `${fmt(d.freshness_seconds, 0)} giây`;
      $("m-fresh-note").textContent = `từ bản ghi gần nhất · ngưỡng giá ${fmt(d.policy.max_age_seconds, 0)} giây`;
    } else {
      $("m-fresh").textContent = "—";
      $("m-fresh-note").textContent = d.source_kind === "daily" ? "dữ liệu tổng hợp cuối ngày từ SSI REST"
        : d.source_kind === "demo-board" ? "bảng điểm giả lập, không có thời gian nguồn"
        : "chưa có bản ghi của lần kết nối này";
    }
    $("cohort-note").textContent = g && g.config_id ? `Cấu hình ${String(g.config_id).slice(0, 6)} · tập mã ${String(g.cohort_id).slice(0, 6)}` : "";
  }

  function renderSummary(group, leader) {
    const summary = $("snapshot-summary");
    summary.hidden = !group?.members;
    if (summary.hidden) return;
    const { as_of: at, pulse } = state.data;
    const when = isDaily() ? `Phiên ${day(at)}` : `${clock(at)} · ${day(at)}`;
    const parts = [];
    if (pulse?.priced) {
      const coverage = pulse.priced < pulse.members ? ` (${pulse.priced}/${pulse.members} mã có giá so sánh)` : "";
      parts.push(`${pulse.advancers} tăng, ${pulse.unchanged} đứng, ${pulse.decliners} giảm so với ${pulse.basis}${coverage}`);
    }
    parts.push(`${group.ranked}/${group.members} mã đã xếp hạng`);
    if (leader) {
      const leaders = group.rows.filter((row) => row.rank === 1);
      parts.push(leaders.length > 1 ? `${leaders.length} mã đồng hạng nhất` : `${leader.symbol} dẫn đầu (${fmt(leader.total)} điểm)`);
    }
    $("snapshot-summary-text").textContent = `${when} · ${parts.join(" · ")}`;
    const unranked = group.members - group.ranked;
    const action = $("summary-unranked");
    action.hidden = unranked <= 0;
    action.textContent = `Xem ${unranked} mã chưa xếp hạng`;
  }

  function renderNotice(text) {
    const d = state.data, g = groupData(), el = $("notice");
    let msg = text, sev = "warn";
    if (!msg && ["disconnected", "auth_failed", "adapter_error"].includes(d.connection.state)) {
      msg = "Mất kết nối tại mốc này. Bảng chờ kết nối lại và dữ liệu nền mới trước khi xếp hạng."; sev = "bad";
    } else if (!msg && g && g.members && !g.ranked) {
      const counts = {};
      g.rows.forEach((r) => (counts[r.status.label] = (counts[r.status.label] || 0) + 1));
      const [label, n] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
      const shared = commonDetails();
      msg = `${state.group} chưa được xếp hạng: ${label.toLowerCase()} (${n}/${g.members} mã)`
        + (shared.length ? ` · ${shared.join("; ").toLowerCase()}` : "") + ". Cần tối thiểu 10 mã hợp lệ.";
    } else if (!msg && !d.verified) {
      msg = "Điểm đang khóa: chưa xác minh đơn vị và ngữ nghĩa của dữ liệu SSI thật."; sev = "bad";
    }
    el.hidden = !msg;
    if (msg) el.innerHTML = `<span class="dot ${sev}"></span><span>${esc(msg)}</span>`;
  }

  function compareAt() {
    const c = state.data && state.data.compare;
    if (!c || !c.as_of) return "";
    return state.data.method_kind === "daily" ? "phiên " + day(c.as_of).slice(0, 5) : clock(c.as_of);
  }
  function deltaTag(row) {
    if (!compareAt() || row.rank == null) return "";
    const at = compareAt();
    if (row.new_in_rank) return `<span class="delta new" title="Chưa có hạng lúc ${at}">mới</span>`;
    if (!row.rank_change) return `<span class="sr-only">Giữ hạng so với ${at}</span>`;
    const up = row.rank_change > 0;
    return `<span class="delta ${up ? "up" : "down"}" title="Hạng ${row.prev_rank} lúc ${at}"><svg class="icon" aria-hidden="true"><use href="#i-${up ? "up" : "down"}"/></svg>${Math.abs(row.rank_change)}<span class="sr-only">${up ? " bậc lên" : " bậc xuống"} so với ${at}</span></span>`;
  }

  function commonWarnings() {
    const g = groupData();
    if (!g || !g.rows.length) return [];
    return g.rows[0].warnings.filter((w) => g.rows.every((r) => r.warnings.includes(w)));
  }
  function ownWarnings(row) { const common = commonWarnings(); return row.warnings.filter((w) => !common.includes(w)); }
  function commonDetails() {
    const g = groupData();
    const open = g ? g.rows.filter((r) => r.rank == null) : [];
    if (open.length < 2) return [];
    return open[0].status.details.filter((t) => open.every((r) => r.status.details.includes(t)));
  }
  function ownDetails(row) { const shared = commonDetails(); return row.status.details.filter((t) => !shared.includes(t)); }

  function stackBar(row, cls = "stack") {
    const parts = shownFactors().map((f) => `<i class="c-${f}" data-w="${row.contributions[f] ?? 0}"></i>`).join("");
    return `<span class="${cls}" aria-hidden="true">${parts}</span>`;
  }
  function applyWidths(root) { root.querySelectorAll("[data-w]").forEach((n) => (n.style.width = Math.max(0, Math.min(100, Number(n.dataset.w))) + "%")); }
  // Percentile tint behind each factor score: same hue as the factor, stronger when the score is higher.
  function applyTints(root) {
    root.querySelectorAll("[data-tint]").forEach((n) => {
      const v = Math.max(0, Math.min(100, Number(n.dataset.tint)));
      n.style.backgroundColor = `rgba(${FRGB[n.dataset.f]}, ${(0.2 * Math.pow(v / 100, 2.2)).toFixed(3)})`;
    });
  }

  function statusTag(row) {
    if (row.rank != null) {
      const own = ownWarnings(row);
      const warn = own.length ? `<span class="warn-mark" title="${esc(own.join(" · "))}">${icon("info")}<span class="sr-only">${esc(own.join(" · "))}</span></span>` : "";
      return warn || `<span class="sr-only">Hợp lệ</span>`;
    }
    const sev = BAD.has(row.status.kind) ? "bad" : "warn";
    return `<span class="state-tag ${sev}" title="${esc(row.status.details.join(" · "))}"><span class="dot ${sev}"></span>${esc(row.status.label)}</span>`;
  }

  function renderRank() {
    if (!state.data) return;
    const rows = visibleRows();
    const g = groupData();
    const choices = state.rankFilter === "all" ? g.rows : rows;
    if (!choices.some((r) => r.symbol === state.selected)) {
      state.selected = (choices.find((r) => r.rank === 1) || choices[0])?.symbol ?? null;
    }
    writeHash();
    $("rank-filter").querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.filter === state.rankFilter));
    });
    $("min").disabled = state.rankFilter === "unranked";
    $("min").title = $("min").disabled ? "Mã chưa xếp hạng chưa có điểm tổng" : "";
    $("rank-filter-count").textContent = `${rows.length}/${g.members} mã hiển thị`;
    const anyOpen = g.rows.some((r) => r.rank == null || ownWarnings(r).length);
    const head = [["rank", "#", ""], ["symbol", "Mã", ""], ["total", "Điểm tổng", ""], ...shownFactors().map((f) => [f, FLABEL[f], "n"]), [null, anyOpen ? "Trạng thái" : "", ""]];
    const th = head.map(([key, label, cls]) => {
      if (!key) return `<th scope="col"><span class="sr-only">Trạng thái</span><button type="button" tabindex="-1">${label}</button></th>`;
      const sorted = state.sort.key === key;
      // Rank and symbol read ascending by default; scores read highest first.
      const ascending = (key === "rank" || key === "symbol") ? state.sort.dir > 0 : state.sort.dir < 0;
      const aria = sorted ? ` aria-sort="${ascending ? "ascending" : "descending"}"` : "";
      return `<th scope="col" class="${cls}"${aria}><button type="button" data-sort="${key}">${label}<svg class="icon sort" aria-hidden="true"><use href="#i-${ascending ? "up" : "down"}"/></svg></button></th>`;
    }).join("");
    let body;
    if (!g.rows.length) body = `<tr><td colspan="8"><div class="empty"><strong>Chưa có danh sách mã</strong>Nhóm này chưa có dữ liệu tại mốc đã chọn.</div></td></tr>`;
    else if (!rows.length) {
      const message = state.rankFilter === "rising" && !compareAt()
        ? "Chọn một mốc có dữ liệu đối chiếu để xem mã tăng hạng."
        : state.rankFilter === "unranked" && g.ranked === g.members
          ? "Tất cả mã tại mốc này đã được xếp hạng."
          : "Thử đổi bộ lọc nhanh, ô tìm mã hoặc ngưỡng điểm.";
      body = `<tr><td colspan="${head.length}"><div class="empty"><strong>Không có mã khớp bộ lọc</strong>${message}</div></td></tr>`;
    }
    else body = rows.map((r) => `
      <tr data-symbol="${esc(r.symbol)}" tabindex="0" aria-selected="${r.symbol === state.selected}" class="${r.rank == null ? "unranked" : ""}">
        <td class="rank num"><span class="rank-cell"><b>${r.rank ?? "—"}</b>${deltaTag(r)}</span></td>
        <td class="sym">${esc(r.symbol)}</td>
        <td class="total"><span class="total-cell"><b class="num">${fmt(r.total)}</b>${r.rank != null ? stackBar(r) : ""}</span></td>
        ${shownFactors().map((f) => `<td class="factor"${r.scores[f] != null ? ` data-tint="${r.scores[f]}" data-f="${f}"` : ""}><span class="factor-cell">${r.scores[f] != null ? `<span class="bar"><i class="c-${f}" data-w="${r.scores[f]}"></i></span><span class="num">${fmt(r.scores[f], 0)}</span>` : `<span></span><span class="muted">—</span>`}</span></td>`).join("")}
        <td class="state">${statusTag(r)}</td>
      </tr>`).join("");
    const table = $("rank-table");
    table.innerHTML = `<caption class="sr-only">Xếp hạng ${esc(state.group)}</caption><thead><tr>${th}</tr></thead><tbody>${body}</tbody>`;
    applyWidths(table); applyTints(table);
    table.querySelectorAll("th button[data-sort]").forEach((b) => (b.onclick = () => {
      const key = b.dataset.sort;
      state.sort = { key, dir: state.sort.key === key ? -state.sort.dir : 1 };
      renderRank();
    }));
    table.querySelectorAll("tbody tr[data-symbol]").forEach((tr) => {
      tr.onclick = () => select(tr.dataset.symbol);
      tr.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(tr.dataset.symbol); }
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          const sib = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
          if (sib && sib.dataset.symbol) { sib.focus(); select(sib.dataset.symbol); }
        }
      };
    });
    const common = commonWarnings();
    const cmp = state.data.compare;
    $("legend-note").textContent = (isDaily() ? "Chế độ cuối ngày: 3 yếu tố từ dữ liệu ngày SSI, không có sổ lệnh nên không có cung–cầu, thanh khoản chỉ theo giá trị khớp; không so trực tiếp với bảng trong phiên · " : "")
      + "Thanh điểm tổng chia theo phần đóng góp có trọng số · thanh yếu tố là điểm phân vị 0–100 trong nhóm"
      + (cmp ? (cmp.as_of ? ` · Mũi tên cạnh hạng: thay đổi so với ${compareAt()}` : ` · Không có mốc để so sánh (${cmp.label})`) : "")
      + (common.length ? ` · Áp dụng cho cả nhóm: ${common.join("; ").toLowerCase()}` : "");
    renderDetail(); renderChart();
  }

  function select(symbol) {
    state.selected = symbol;
    document.querySelectorAll("#rank-table tbody tr").forEach((tr) => tr.setAttribute("aria-selected", String(tr.dataset.symbol === symbol)));
    writeHash(); renderDetail(); renderChart(); drawHeatmap();
  }

  function rawLine(f, raw) {
    if (isDaily() && f === "liquidity") return raw.turnover == null ? "" : `Giá trị khớp cả phiên ${money(raw.turnover)}`;
    const need = { momentum: ["closePrice", "openPrice", "momentum"], liquidity: ["turnover", "spread_bps", "depth_vnd"], foreign: ["foreign_ratio"], imbalance: ["imbalance"] }[f];
    if (need.some((k) => raw[k] == null)) return "";
    if (isDaily() && f === "momentum") return `Đóng cửa ${fmt(raw.closePrice, 0)} so với mở cửa ${fmt(raw.openPrice, 0)}: <span class="${raw.momentum > 0 ? "up" : raw.momentum < 0 ? "down" : "ref"}">${signed(raw.momentum, 2)} %</span>`;
    if (f === "momentum") return `Giá ${fmt(raw.closePrice, 0)} so với mở cửa ${fmt(raw.openPrice, 0)}: <span class="${raw.momentum > 0 ? "up" : raw.momentum < 0 ? "down" : "ref"}">${signed(raw.momentum, 2)} %</span>`;
    if (f === "liquidity") return `Giá trị khớp ${money(raw.turnover)} · chênh lệch ${fmt(raw.spread_bps, 0)} bps · độ sâu ${money(raw.depth_vnd)}`;
    if (f === "foreign") return `Ngoại ròng / giá trị khớp ${signed(raw.foreign_ratio, 3)}`;
    return `Mất cân bằng chào mua–bán ba mức ${signed(raw.imbalance, 2)}`;
  }

  function renderDetail() {
    const g = groupData(), el = $("detail");
    const r = g && g.rows.find((x) => x.symbol === state.selected);
    if (!r) {
      el.innerHTML = `<div class="empty"><strong>Chưa chọn mã</strong>Bấm vào một dòng trong bảng.</div>`;
      $("price").replaceChildren();
      state.price = null;
      return;
    }
    const ranked = r.rank != null;
    let explain = "";
    if (ranked) {
      const by = FACTORS.filter((f) => r.scores[f] != null).sort((a, b) => r.scores[b] - r.scores[a]);
      explain = `Mạnh nhất ở <b>${FLABEL[by[0]].toLowerCase()}</b> (${fmt(r.scores[by[0]], 0)}), yếu nhất ở <b>${FLABEL[by[by.length - 1]].toLowerCase()}</b> (${fmt(r.scores[by[by.length - 1]], 0)}).`;
    }
    el.innerHTML = `
      <div class="detail-head"><h3>${esc(r.symbol)}</h3>
        <span class="rankbadge">${ranked ? `Hạng ${r.rank}/${g.ranked} · ${esc(state.group)}` : esc(r.status.label)}</span>
        <span class="score num">${ranked ? `${fmt(r.total)}<small>/ 100</small>` : ""}</span></div>
      ${ranked ? stackBar(r) : ""}
      ${changeLine(r)}
      ${ranked ? `<p class="explain">${explain}</p>` : `<ul class="reasons">${(ownDetails(r).length ? ownDetails(r) : r.status.details.length ? ["Cùng lý do với cả nhóm, xem dòng thông báo phía trên bảng."] : [r.status.label]).map((t) => `<li>${icon("alert")}<span>${esc(t)}</span></li>`).join("")}</ul>`}
      <div class="factors">${shownFactors().map((f) => `
        <div class="frow"><span class="name"><i class="c-${f}"></i>${FLABEL[f]}</span>
          <span class="bar"><i class="c-${f}" data-w="${r.scores[f] ?? 0}"></i></span><b class="num">${fmt(r.scores[f], 0)}</b>
          ${rawLine(f, r.raw) ? `<span class="raw">${rawLine(f, r.raw)}</span>` : ""}</div>`).join("")}</div>
      ${ownWarnings(r).length ? `<ul class="warnings">${ownWarnings(r).map((w) => `<li>${icon("info")}${esc(w)}</li>`).join("")}</ul>` : ""}`;
    applyWidths(el);
    loadPrice(r);
  }

  function changeLine(r) {
    const at = compareAt();
    if (!at || r.rank == null) return "";
    if (r.new_in_rank) return `<p class="change">Lúc <b>${at}</b> mã này chưa được xếp hạng.</p>`;
    const move = r.rank_change > 0 ? `lên ${r.rank_change} bậc` : r.rank_change < 0 ? `xuống ${-r.rank_change} bậc` : "giữ nguyên";
    return `<p class="change">So với <b>${at}</b>: hạng ${r.prev_rank} → ${r.rank} (${move}), điểm ${fmt(r.prev_total)} → ${fmt(r.total)} (${signed(r.total_change, 1)}).</p>`;
  }

  async function loadPrice(row) {
    const el = $("price");
    const symbol = row.symbol;
    const snapshot = state.data;
    if (state.price?.snapshot === snapshot && state.price.symbol === symbol) return;
    const isCurrent = () => state.data === snapshot && state.selected === symbol;
    state.price = null;
    el.replaceChildren();
    try {
      const h = await get("/api/history", { source: state.source, run: state.run, point: state.point, symbol });
      if (!isCurrent()) return;
      state.price = { snapshot, symbol, points: h.points, open: row.raw.openPrice };
      drawPrice();
    } catch (err) {
      if (!isCurrent()) return;
      el.innerHTML = `<h4>Giá khớp đã ghi nhận</h4><p class="muted">${esc(err.message)}</p>`;
    }
  }

  function drawPrice() {
    const el = $("price"), p = state.price;
    if (!p || p.symbol !== state.selected) return;
    el.innerHTML = `<h4>${isDaily() ? "Giá đóng cửa các phiên" : "Giá khớp đã ghi nhận"} · ${esc(p.symbol)}</h4>` + priceChart(p.points, p.open, Math.max(240, el.clientWidth - 32));
  }

  function priceChart(points, open, W) {
    if (points.length < 2) return `<p class="muted">Mới có ${points.length} điểm giá tại mốc này, chưa đủ để vẽ đường.</p>`;
    const H = 72, P = { l: 52, r: 8, t: 6, b: 18 };
    const ys = points.map((p) => p.price).concat(open ? [open] : []);
    let lo = Math.min(...ys), hi = Math.max(...ys);
    if (hi === lo) { hi += 1; lo -= 1; }
    const x = (i) => P.l + (i / (points.length - 1)) * (W - P.l - P.r);
    const y = (v) => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
    const last = points[points.length - 1].price;
    const color = open == null || last === open ? "#F0B90B" : last > open ? "#16C784" : "#FF5C66";
    const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`).join("");
    const ref = open != null ? `<line class="grid" x1="${P.l}" x2="${W - P.r}" y1="${y(open)}" y2="${y(open)}" stroke-dasharray="3 3" stroke="#F0B90B" opacity=".6"/><text x="${P.l - 6}" y="${y(open) + 4}" text-anchor="end">${fmt(open, 0)}</text>` : "";
    return `<svg class="chart" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Diễn biến giá khớp, ${points.length} điểm">
      <line class="grid" x1="${P.l}" x2="${W - P.r}" y1="${H - P.b}" y2="${H - P.b}"/>
      <text x="${P.l - 6}" y="${y(hi) + 4}" text-anchor="end">${fmt(hi, 0)}</text>${ref}
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
      ${points.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(p.price).toFixed(1)}" r="2.5" fill="${color}"/>`).join("")}
      <text x="${P.l}" y="${H - 4}">${points[0].label || clock(points[0].at)}</text><text x="${W - P.r}" y="${H - 4}" text-anchor="end">${points[points.length - 1].label || clock(points[points.length - 1].at)}</text>
    </svg>`;
  }

  function renderChart() {
    document.querySelectorAll("#chart-mode button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === state.chart)));
    if (state.chart === "scatter") return scatterChart();
    const g = groupData(), el = $("score-chart");
    const rows = (g ? g.rows : []).filter((r) => r.rank != null).slice(0, 15);
    $("chart-title").textContent = `Điểm tổng trong nhóm ${state.group} · chia theo đóng góp${compareAt() ? " · vạch trắng: điểm lúc " + compareAt() : ""}`;
    if (!rows.length) { el.innerHTML = `<p class="muted">Chưa có mã được xếp hạng để so sánh.</p>`; return; }
    const W = Math.max(260, el.clientWidth), row = 22, L = 78, R = 40, H = rows.length * row + 6, span = W - L - R;
    const bars = rows.map((r, i) => {
      let x = L, segs = "";
      for (const f of FACTORS) {
        const w = ((r.contributions[f] || 0) / 100) * span;
        segs += `<rect x="${x.toFixed(1)}" y="${i * row + 5}" width="${w.toFixed(1)}" height="12" fill="${FCOLOR[f]}"/>`;
        x += w;
      }
      const sel = r.symbol === state.selected;
      const tick = r.prev_total != null ? `<rect x="${(L + (r.prev_total / 100) * span - 1).toFixed(1)}" y="${i * row + 3}" width="2" height="16" fill="#E7EAF0" opacity=".8"><title>Điểm lúc ${compareAt()}: ${fmt(r.prev_total)}</title></rect>` : "";
      segs += tick;
      return `<g class="hbar" data-symbol="${esc(r.symbol)}"><rect class="track" x="0" y="${i * row}" width="${W}" height="${row}" fill="transparent"/>
        <text x="0" y="${i * row + 15}" ${sel ? 'fill="#E7EAF0" font-weight="700"' : ""}>${esc(r.symbol)}</text><g opacity="${sel ? 1 : 0.45}">${segs}</g>
        <text x="${W}" y="${i * row + 15}" text-anchor="end" ${sel ? 'fill="#E7EAF0" font-weight="700"' : ""}>${fmt(r.total)}</text></g>`;
    }).join("");
    el.innerHTML = `<svg class="chart" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Điểm tổng của ${rows.length} mã đã xếp hạng">${bars}</svg>`;
    el.querySelectorAll(".hbar").forEach((n) => (n.onclick = () => select(n.dataset.symbol)));
  }

  function renderQuality() {
    const d = state.data, g = groupData();
    if (!g) return;
    const limit = d.policy.max_age_seconds;
    const foreignLimit = d.policy.foreign_max_age_seconds ?? limit;
    const age = (v, max = limit) => v == null ? `<span class="muted">—</span>` : `<span class="age${v > max ? " stale" : ""}">${fmt(v, 0)}</span>`;
    $("quality-table").innerHTML = `<thead><tr>${["Mã", "Phiên", "Giá và khớp (giây)", "Sổ lệnh (giây)", "Khối ngoại (giây)", "Trạng thái", "Lý do / cảnh báo"].map((h) => `<th scope="col"><button type="button" tabindex="-1">${h}</button></th>`).join("")}</tr></thead>
      <tbody>${g.rows.map((r) => `<tr><td class="sym">${esc(r.symbol)}</td><td>${esc(r.session || "—")}</td><td>${age(r.ages.trade)}</td><td>${age(r.ages.book)}</td><td>${age(r.ages.foreign, foreignLimit)}</td>
        <td>${statusTag(r)}</td><td class="muted why" title="${esc([...r.status.details, ...r.warnings].join(" · "))}">${esc([...ownDetails(r), ...ownWarnings(r)].join(" · ") || "—")}</td></tr>`).join("")}</tbody>`;
    const gaps = d.gaps.map((x) => `${clock(x.start)}–${clock(x.end)} (${x.kind === "disconnected" ? "mất kết nối" : x.kind})`).join(", ");
    const common = commonWarnings();
    $("quality-note").textContent = `Tuổi (giây) tính từ thời gian nguồn của trường lâu nhất trong mỗi cụm; ngưỡng ${fmt(limit, 0)} giây cho giá và sổ lệnh, ${fmt(foreignLimit, 0)} giây cho khối ngoại.`
      + (common.length ? ` Áp dụng cho cả nhóm: ${common.join("; ").toLowerCase()}.` : "") + (gaps ? ` Khoảng gián đoạn: ${gaps}.` : "");
  }

  function renderMethod() {
    const d = state.data, g = groupData();
    $("method").innerHTML = `
      ${d.method_kind === "daily" ? `<div><h3>Đang xem chế độ cuối ngày</h3><p>Xếp hạng theo dữ liệu tổng hợp từng phiên của SSI (REST securitiesSummary, từng mã). Ba yếu tố: động lượng = % đóng cửa so với mở cửa; thanh khoản = điểm phân vị của giá trị khớp cả phiên; dòng tiền ngoại = (mua − bán của khối ngoại) / giá trị khớp. Trọng số 33/33/33 hoặc 50/25/25. Không có sổ lệnh nên không có cung–cầu, độ sâu và chênh lệch giá. Mã thiếu dữ liệu khối ngoại (SSI trả trống) không được xếp hạng. Đây là phương pháp khác (daily-v1), không so trực tiếp với bảng trong phiên.</p>${d.scope_note ? `<p>${esc(d.scope_note.detail)}</p>` : ""}</div>` : ""}
      <div><h3>Sản phẩm làm gì</h3><p>Xếp hạng tương đối các cổ phiếu trong rổ VN30 tại một mốc của phiên khớp lệnh liên tục, để thu hẹp danh sách cần nghiên cứu tiếp. Không dự báo giá, không đặt lệnh. Phạm vi chỉ gồm VN30: trên dữ liệu SSI 15 phiên, HNX30 có 11/30 mã giao dịch dưới 1 tỷ đồng mỗi phiên và 43% dòng thiếu dữ liệu khối ngoại, nên động lượng và dòng tiền ngoại của nhóm này không đủ tin cậy để xếp hạng.</p></div>
      <div><h3>Bốn yếu tố</h3><ul>
        <li><b>Động lượng</b>: % thay đổi từ giá mở cửa đến giá khớp gần nhất.</li>
        <li><b>Thanh khoản</b>: trung bình điểm phân vị của giá trị khớp, độ sâu ba mức giá mỗi bên và chênh lệch mua–bán (hẹp hơn tốt hơn).</li>
        <li><b>Dòng tiền ngoại</b>: (mua − bán của nhà đầu tư nước ngoài) / tổng giá trị khớp, hoặc theo khối lượng.</li>
        <li><b>Cung–cầu</b>: (khối lượng chào mua − chào bán) / tổng khối lượng chào ở ba mức giá.</li></ul></div>
      <div><h3>Cơ sở tài chính</h3><ul>
        <li><b>Động lượng</b>: lợi suất cổ phiếu có tính tự tương quan, âm ở tháng liền trước và dương ở các độ trễ dài hơn (Jegadeesh, 1990). Các kết quả này ở khung thời gian dài hơn một phiên, nên ở đây động lượng chỉ mô tả diễn biến tại mốc, không dự báo.</li>
        <li><b>Thanh khoản</b>: thanh khoản liên hệ với lợi suất kỳ vọng (Amihud, 2002). Sản phẩm dùng giá trị khớp, độ sâu và chênh lệch giá thay cho thước đo của Amihud, và có thể nghiêng về mã vốn hóa lớn.</li>
        <li><b>Dòng tiền ngoại</b>: dòng vốn của nhà đầu tư nước ngoài có tính bền và theo lợi suất quá khứ (Froot, O'Connell &amp; Seasholes, 2001); ở Việt Nam họ cũng được ghi nhận giao dịch theo xu hướng (Vo, 2017).</li>
        <li><b>Cung–cầu</b>: mất cân bằng lệnh liên hệ với biến động giá ngắn hạn (Chordia, Roll &amp; Subrahmanyam, 2002; Cont, Kukanov &amp; Stoikov, 2014). Các nghiên cứu này đo dòng lệnh; sản phẩm đo khối lượng chào tại một mốc ở ba mức giá, nên đây là thước đo gần đúng.</li></ul></div>
      <div><h3>Cách chấm</h3><p>Mỗi yếu tố đổi thành điểm phân vị 0–100 trong nhóm đủ dữ liệu; điểm tổng là tổng có trọng số. Cần tối thiểu 10 mã hợp lệ; điểm bằng nhau cùng hạng. Không xếp hạng khi thiếu hoặc cũ dữ liệu, ngoài phiên LO, mất kết nối, hoặc nguồn thật chưa xác minh. Không tự bỏ một yếu tố rồi chia lại trọng số.</p></div>
      <div><h3>Giới hạn</h3><p>Trọng số là cấu hình thử nghiệm; thanh khoản có thể nghiêng về mã vốn hóa lớn và các yếu tố có thể tương quan. Sổ lệnh chỉ phản ánh lượng chào tại mốc ghi nhận. Dữ liệu giả lập chỉ dùng kiểm tra phần mềm.</p></div>
      <div><h3>Thông tin lần tính</h3><dl>
        <dt>Nguồn</dt><dd>${esc(d.source)}${d.profile ? " · " + esc(d.profile) : ""}</dd><dt>Lần thu thập</dt><dd>${esc(d.run)}</dd>
        <dt>Mốc</dt><dd>${esc(d.as_of)}</dd><dt>Phương pháp</dt><dd>${esc(g && g.method || "—")}</dd>
        <dt>Cấu hình</dt><dd>${esc(g && g.config_id || "—")}</dd><dt>Tập mã</dt><dd>${esc(g && g.cohort_id || "—")}</dd>
        <dt>Trọng số</dt><dd>${esc(d.weights.label)}</dd><dt>Khối ngoại</dt><dd>${d.foreign === "value" ? "theo giá trị" : "theo khối lượng"}</dd>
        <dt>So sánh với</dt><dd>${d.compare ? (d.compare.as_of ? esc(d.compare.as_of) + " (" + esc(d.compare.label) + ")" : "không có mốc " + esc(d.compare.label)) : "không so sánh"}</dd></dl></div>`;
  }

  // ---------- market pulse ----------
  function renderPulse() {
    const p = state.data.pulse, el = $("pulse");
    el.hidden = !p || !p.members;
    if (el.hidden) return;
    const idx = p.index;
    $("p-index-item").hidden = !idx;
    if (idx) {
      const dir = idx.change_pct > 0 ? "up" : idx.change_pct < 0 ? "down" : "ref";
      $("p-index").textContent = fmt(idx.close, 2);
      const ch = $("p-index-change");
      ch.className = "num move " + dir;
      ch.innerHTML = `${dir === "ref" ? "" : icon(dir)}${signed(idx.change, 2)} (${signed(idx.change_pct, 2)}%)`;
    }
    $("p-breadth-label").textContent = `Tăng / đứng / giảm · so với ${p.basis}`;
    const n = p.priced || 1;
    const [u, f, dn] = $("p-breadth").children;
    u.dataset.w = (100 * p.advancers) / n; f.dataset.w = (100 * p.unchanged) / n; dn.dataset.w = (100 * p.decliners) / n;
    applyWidths($("p-breadth"));
    $("p-breadth-text").innerHTML = `<span class="up">${p.advancers}</span><span class="sep">/</span><span class="ref">${p.unchanged}</span><span class="sep">/</span><span class="down">${p.decliners}</span>`;
    $("p-breadth-text").title = `${p.advancers} mã tăng, ${p.unchanged} đứng, ${p.decliners} giảm (${p.priced}/${p.members} mã có giá)`;
    $("p-value").textContent = money(p.total_value);
    $("p-foreign").textContent = p.foreign_net == null ? "—" : `${signed(p.foreign_net / 1e9, 1)} tỷ`;
    $("p-foreign-note").textContent = p.foreign_net == null ? "nguồn không gửi"
      : (p.foreign_net >= 0 ? "mua ròng" : "bán ròng") + (p.foreign_reported < p.members ? ` · ${p.foreign_reported}/${p.members} mã` : "");
  }

  // ---------- views that need many sessions ----------
  function needsDaily(el, what) {
    const has = state.ctx.sources.some((s) => s.id === "daily");
    el.innerHTML = `<div class="empty"><strong>${what} cần dữ liệu nhiều phiên</strong>Nguồn đang chọn chỉ có một phiên, nên chưa so được giữa các phiên.`
      + (has ? `<span class="empty-action"><button class="btn" type="button" data-go-daily>Mở Cuối ngày · SSI thật</button></span>` : "") + `</div>`;
    const b = el.querySelector("[data-go-daily]");
    if (b) b.onclick = () => { $("source").value = "daily"; $("source").dispatchEvent(new Event("change")); };
  }

  async function renderHistory() {
    if (state.view !== "history") return;
    const el = $("heatmap");
    const note = document.querySelector("#view-history .view-note");
    if (!isDaily()) { note.hidden = true; return needsDaily(el, "Lịch sử hạng"); }
    note.hidden = false;
    const key = `${state.weights}|${state.foreign}`;
    if (state.heatKey !== key) {
      if (!state.heat) el.innerHTML = `<p class="muted loading-line">Đang tính hạng từng phiên…</p>`;
      try {
        const h = await get("/api/heatmap", { source: state.source, weights: state.weights, foreign: state.foreign });
        state.heat = h; state.heatKey = key;
      } catch (err) { el.innerHTML = `<div class="empty"><strong>Không tải được lịch sử hạng</strong>${esc(err.message)}</div>`; return; }
    }
    drawHeatmap();
  }

  function drawHeatmap() {
    const el = $("heatmap"), h = state.heat;
    if (!h || state.view !== "history" || !isDaily() || !h.rows.length) return;
    const days = h.days, n = h.rows.length, L = 58, row = 22;
    const cell = Math.max(28, Math.floor((Math.max(320, el.clientWidth - 32) - L) / days.length));
    const narrow = cell < 40, T = narrow ? 36 : 24;  // narrow cells: month on its own line, day number below
    const W = L + cell * days.length, H = T + row * n + 2;
    const cur = days.findIndex((d) => d.id === (state.data && state.data.as_of));
    const top = Math.max(2, ...h.rows.flatMap((r) => r.ranks.filter((k) => k != null)));
    let svg = days.map((d, j) => {
      const cx = L + j * cell + cell / 2, mark = j === cur ? ' class="cur"' : "";
      if (!narrow) return `<text x="${cx}" y="14" text-anchor="middle"${mark}>${d.label}</text>`;
      const month = j === 0 || d.label.slice(3) !== days[j - 1].label.slice(3) ? `<text class="month" x="${L + j * cell + 2}" y="11">Th${Number(d.label.slice(3))}</text>` : "";
      return `${month}<text x="${cx}" y="27" text-anchor="middle"${mark}>${d.label.slice(0, 2)}</text>`;
    }).join("");
    if (cur >= 0) svg += `<rect class="cur-col" x="${L + cur * cell + 0.5}" y="${T - 3.5}" width="${cell - 1}" height="${row * n + 5}" rx="4"/>`;
    svg += h.rows.map((r, i) => {
      const y = T + i * row, sel = r.symbol === state.selected;
      const cells = r.ranks.map((k, j) => {
        const x = L + j * cell, tip = `${r.symbol} · phiên ${days[j].label}: `;
        if (k == null) return `<g><title>${esc(tip + (r.reasons[j] || "chưa xếp hạng"))}</title><rect class="cell-empty" x="${x + 1}" y="${y + 1}" width="${cell - 2}" height="${row - 2}" rx="3"/><text class="dash" x="${x + cell / 2}" y="${y + 15}" text-anchor="middle">–</text></g>`;
        const a = 0.06 + 0.86 * Math.pow(1 - (k - 1) / (top - 1), 1.6);
        return `<g><title>${esc(tip)}hạng ${k}</title><rect x="${x + 1}" y="${y + 1}" width="${cell - 2}" height="${row - 2}" rx="3" fill="rgba(59, 130, 246, ${a.toFixed(3)})"/><text x="${x + cell / 2}" y="${y + 15}" text-anchor="middle"${a > 0.52 ? ' class="deep"' : ""}>${k}</text></g>`;
      }).join("");
      return `<g class="heat-row${sel ? " sel" : ""}" data-symbol="${esc(r.symbol)}"><rect class="track" x="0" y="${y}" width="${W}" height="${row}"/>`
        + `<text class="sym" x="0" y="${y + 15}">${esc(r.symbol)}</text>${cells}`
        + (sel ? `<rect class="sel-ring" x="${L + 0.5}" y="${y + 0.5}" width="${cell * days.length - 1}" height="${row - 1}" rx="4"/>` : "") + `</g>`;
    }).join("");
    el.innerHTML = `<svg class="chart heat" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Hạng của ${n} mã VN30 qua ${days.length} phiên">${svg}</svg>`;
    el.querySelectorAll(".heat-row").forEach((g) => (g.onclick = () => select(g.dataset.symbol)));
    const steady = h.rows.filter((r) => r.ranks.every((k) => k != null && k <= 10)).map((r) => r.symbol);
    const label = state.data.weights.id === "balanced" ? "33/33/33" : "50/25/25";
    $("history-note").textContent = `Hạng trong rổ VN30 qua ${days.length} phiên, trọng số ${label}, sắp theo hạng phiên mới nhất · khung sáng: phiên đang xem · bấm một hàng để xem chi tiết`
      + (steady.length ? ` · Ở top 10 mọi phiên: ${steady.join(", ")}` : ` · Không mã nào ở top 10 cả ${days.length} phiên`);
    $("heat-key").innerHTML = `<span>Hạng 1</span><i class="ramp"></i><span>Hạng ${top}</span><i class="none"></i><span>Chưa xếp hạng</span>`;
  }

  async function renderValidate() {
    if (state.view !== "validate") return;
    const el = $("validate");
    if (!isDaily()) return needsDaily(el, "Kiểm chứng");
    if (state.validKey !== state.weights) {
      if (!state.valid) el.innerHTML = `<p class="muted loading-line">Đang đối chiếu điểm với lợi suất phiên sau…</p>`;
      try {
        state.valid = await get("/api/validation", { source: state.source, weights: state.weights });
        state.validKey = state.weights;
      } catch (err) { el.innerHTML = `<div class="empty"><strong>Không tải được kiểm chứng</strong>${esc(err.message)}</div>`; return; }
    }
    drawValidate();
  }

  function drawValidate() {
    const v = state.valid, el = $("validate");
    if (!v || state.view !== "validate" || !isDaily()) return;
    const ic = v.summary.ic, sp = v.summary.spread, close = v.summary.ic_close, pw = v.summary.power;
    const stat = (label, value, note) => `<div><dt>${label}</dt><dd><strong class="num">${value}</strong><span>${note}</span></dd></div>`;
    const positive = ic.positive_share == null ? "—" : `${Math.round(ic.positive_share * ic.pairs)}/${ic.pairs}`;
    const tNote = ic.t == null ? "chưa đủ cặp" : `t = ${signed(ic.t, 2)} · ${Math.abs(ic.t) >= 2 ? "|t| ≥ 2, cần xác nhận thêm" : "|t| < 2, chưa khác 0"}`;
    el.innerHTML = `
      <p class="verdict">${esc(v.verdict)}</p>
      <dl class="vstats">
        ${stat("IC trung bình", signed(ic.mean, 3), tNote)}
        ${stat("Cặp phiên có IC > 0", positive, "một nửa là mức ngẫu nhiên")}
        ${stat(`Top ${v.top_n} − bottom ${v.top_n}`, `${signed(sp.mean, 2)} điểm %`, "lợi suất phiên sau, trung bình")}
        ${stat("Mẫu phân biệt được", pw.detectable_ic == null ? "—" : `|IC| ≥ ${fmt(pw.detectable_ic, 2)}`, pw.sessions_for_target ? `IC ${fmt(pw.target_ic, 2)} cần khoảng ${pw.sessions_for_target} phiên` : "chưa đủ cặp")}
      </dl>
      <p class="vcompare">Nếu tính cả chênh lệch qua đêm (từ đóng cửa phiên t, không mua kịp vì điểm có sau khi đóng cửa): IC ${signed(close.mean, 3)}, t = ${signed(close.t, 2)}.</p>
      <h3 class="chart-title">IC từng cặp phiên · lợi suất mở cửa → đóng cửa phiên sau · trọng số ${esc(v.weights_label.replace(/^\D+/, ""))} · đường đứt: trung bình ${signed(ic.mean, 3)}</h3>
      <div id="ic-chart"></div>
      <div class="vgrid">
        <div><h3 class="chart-title">IC của từng yếu tố</h3>
          <table class="ftable"><thead><tr><th scope="col">Yếu tố</th><th scope="col" class="n">IC trung bình</th><th scope="col" class="n">t</th></tr></thead>
          <tbody>${["momentum", "liquidity", "foreign"].map((f) => `<tr><td><i class="sw c-${f}"></i>${FLABEL[f]}</td><td class="num n">${signed(v.factor_ic[f].mean, 3)}</td><td class="num n">${signed(v.factor_ic[f].t, 2)}</td></tr>`).join("")}</tbody></table></div>
        <div><h3 class="chart-title">Cách đo</h3>
          <p class="legend-note">IC là tương quan hạng Spearman giữa điểm phiên t và lợi suất phiên t+1 của các mã được xếp hạng. Không có tham số nào được ước lượng; trọng số chọn trước khi tính phép đo này. "Chưa có bằng chứng" không có nghĩa là đã chứng minh điểm không dự báo được. Có nhiều phép đo trên cùng mẫu, nên một |t| vừa trên 2 chưa đủ để coi là phát hiện. Kết quả không thay đổi cách chấm điểm.</p></div>
      </div>`;
    const box = $("ic-chart");
    box.innerHTML = icChart(v.series, ic.mean, Math.max(280, box.clientWidth));
  }

  function icChart(series, mean, W) {
    const pts = series.filter((p) => p.ic != null);
    if (!pts.length) return `<p class="muted">Chưa có cặp phiên nào tính được IC.</p>`;
    const H = 168, P = { l: 40, r: 10, t: 12, b: 24 };
    const lim = Math.max(0.5, ...pts.map((p) => Math.abs(p.ic) * 1.1));
    const y = (v) => P.t + (1 - (v + lim) / (2 * lim)) * (H - P.t - P.b);
    const step = (W - P.l - P.r) / series.length, bw = Math.max(6, Math.min(26, step * 0.62));
    const every = step < 34 ? 2 : 1;
    let out = [lim, lim / 2, 0, -lim / 2, -lim].map((v) => `<line class="grid${v === 0 ? " zero" : ""}" x1="${P.l}" x2="${W - P.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text x="${P.l - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${signed(v, 2)}</text>`).join("");
    out += series.map((p, i) => {
      const cx = P.l + step * i + step / 2, label = (i % every === 0) ? `<text x="${cx.toFixed(1)}" y="${H - 6}" text-anchor="middle">${p.date.slice(8, 10)}/${p.date.slice(5, 7)}</text>` : "";
      if (p.ic == null) return label;
      const top = y(Math.max(0, p.ic)), h = Math.max(1, Math.abs(y(p.ic) - y(0)));
      return `<g><title>Phiên ${p.date.slice(8, 10)}/${p.date.slice(5, 7)} → ${p.next_date.slice(8, 10)}/${p.next_date.slice(5, 7)}: IC ${signed(p.ic, 3)} · ${p.ranked} mã</title><rect class="${p.ic >= 0 ? "pos" : "neg"}" x="${(cx - bw / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2"/></g>${label}`;
    }).join("");
    if (mean != null) out += `<line class="mean" x1="${P.l}" x2="${W - P.r}" y1="${y(mean).toFixed(1)}" y2="${y(mean).toFixed(1)}"/>`;
    return `<svg class="chart ic" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="IC của ${pts.length} cặp phiên, trung bình ${signed(mean, 3)}">${out}</svg>`;
  }

  // ---------- momentum x foreign flow ----------
  function scatterChart() {
    const g = groupData(), el = $("score-chart");
    const pts = (g ? g.rows : []).filter((r) => r.raw.momentum != null && r.raw.foreign_ratio != null && r.raw.turnover > 0);
    const basis = state.data.foreign === "volume" ? "khối lượng" : "giá trị khớp";
    $("chart-title").textContent = `Động lượng × dòng tiền ngoại · cỡ chấm theo giá trị khớp · ngoại ròng tính trên ${basis}`;
    if (pts.length < 3) { el.innerHTML = `<p class="muted">Cần ít nhất 3 mã có giá, giá trị khớp và số liệu khối ngoại để vẽ.</p>`; return; }
    const W = Math.max(260, el.clientWidth), H = Math.round(Math.min(330, Math.max(230, W * 0.8)));
    const P = { l: 10, r: 10, t: 10, b: 22 };
    const mx = Math.max(0.2, ...pts.map((p) => Math.abs(p.raw.momentum))) * 1.15;
    const my = Math.max(0.005, ...pts.map((p) => Math.abs(p.raw.foreign_ratio))) * 1.15;
    const x = (v) => P.l + ((v + mx) / (2 * mx)) * (W - P.l - P.r);
    const y = (v) => P.t + (1 - (v + my) / (2 * my)) * (H - P.t - P.b);
    const tmax = Math.max(...pts.map((p) => p.raw.turnover));
    const rad = (t) => 3 + 10 * Math.sqrt(t / tmax);
    const big = new Set(pts.slice().sort((a, b) => b.raw.turnover - a.raw.turnover).slice(0, 4).map((p) => p.symbol));
    const q = (tx, ty, anchor, text) => `<text class="quad" x="${tx}" y="${ty}" text-anchor="${anchor}">${text}</text>`;
    let out = `<line class="grid axis" x1="${P.l}" x2="${W - P.r}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}"/><line class="grid axis" x1="${x(0).toFixed(1)}" x2="${x(0).toFixed(1)}" y1="${P.t}" y2="${H - P.b}"/>`
      + q(W - P.r - 2, P.t + 12, "end", "Giá tăng · ngoại mua") + q(P.l + 2, P.t + 12, "start", "Giá giảm · ngoại mua")
      + q(W - P.r - 2, H - P.b - 6, "end", "Giá tăng · ngoại bán") + q(P.l + 2, H - P.b - 6, "start", "Giá giảm · ngoại bán")
      + `<text x="${P.l}" y="${H - 6}">${signed(-mx / 1.15, 1)}%</text><text x="${W - P.r}" y="${H - 6}" text-anchor="end">${signed(mx / 1.15, 1)}%</text><text x="${x(0).toFixed(1)}" y="${H - 6}" text-anchor="middle">động lượng</text>`;
    out += pts.slice().sort((a, b) => b.raw.turnover - a.raw.turnover).map((p) => {
      const sel = p.symbol === state.selected, cx = x(p.raw.momentum), cy = y(p.raw.foreign_ratio), r = rad(p.raw.turnover);
      const tip = `${p.symbol}: động lượng ${signed(p.raw.momentum, 2)}%, ngoại ròng ${signed(100 * p.raw.foreign_ratio, 2)}% ${basis}, giá trị khớp ${money(p.raw.turnover)}${p.rank == null ? " · chưa xếp hạng" : " · hạng " + p.rank}`;
      return `<g class="pt${sel ? " sel" : ""}${p.rank == null ? " open" : ""}" data-symbol="${esc(p.symbol)}"><title>${esc(tip)}</title><circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}"/></g>`;
    }).join("");
    out += pts.filter((p) => p.symbol === state.selected || big.has(p.symbol)).map((p) => {
      const sel = p.symbol === state.selected, cx = x(p.raw.momentum), cy = y(p.raw.foreign_ratio), r = rad(p.raw.turnover);
      const right = cx + r + 3 + 34 < W;
      return `<text class="pt-label${sel ? " sel" : ""}" x="${(right ? cx + r + 3 : cx - r - 3).toFixed(1)}" y="${(cy + 4).toFixed(1)}" text-anchor="${right ? "start" : "end"}">${esc(p.symbol)}</text>`;
    }).join("");
    el.innerHTML = `<svg class="chart scatter" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Động lượng và dòng tiền ngoại của ${pts.length} mã">${out}</svg>`
      + `<p class="chart-note">Trục ngang: % giá so với mở cửa. Trục dọc: (ngoại mua − bán) / ${basis}. Không phải tín hiệu mua bán.</p>`;
    el.querySelectorAll(".pt").forEach((n) => (n.onclick = () => select(n.dataset.symbol)));
  }

  function showError(err) {
    if (!state.data) return fatal(err);
    renderNotice(`Không tải được dữ liệu: ${err.message}`);
  }
  function fatal(err) {
    document.querySelector(".workspace").innerHTML = `<section class="panel error-box"><strong>Không tải được dữ liệu</strong><p>${esc(err.message)}</p><button class="btn primary" type="button" id="retry">${icon("refresh")}Thử lại</button></section>`;
    $("conn").innerHTML = `<span class="dot bad"></span><span>Lỗi</span>`;
    $("retry").onclick = () => location.reload();
  }

  const phone = window.matchMedia("(max-width: 560px)");
  const syncControls = () => { $("controls").open = !phone.matches; };
  phone.addEventListener("change", syncControls);
  syncControls();
  let resizeTimer = null;
  new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (state.data) { renderChart(); drawPrice(); } }, 120);
  }).observe(document.querySelector(".side"));
  let mainTimer = null;
  new ResizeObserver(() => {
    clearTimeout(mainTimer);
    mainTimer = setTimeout(() => { if (state.data) { drawHeatmap(); drawValidate(); } }, 120);
  }).observe(document.querySelector(".workspace > .panel"));

  init();
})();
