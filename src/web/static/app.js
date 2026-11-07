"use strict";
(() => {
  const FACTORS = ["momentum", "liquidity", "foreign", "imbalance"];
  const FLABEL = { momentum: "Động lượng", liquidity: "Thanh khoản", foreign: "Dòng tiền ngoại", imbalance: "Cung–cầu" };
  const FCOLOR = { momentum: "#4C8DFF", liquidity: "#31C2D6", foreign: "#A48BFF", imbalance: "#E58BC8" };
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
    sort: { key: "rank", dir: 1 }, search: "", min: 0, selected: null, view: "rank", compare: "prev",
    runs: [], timeline: [], data: null, timer: null, refresh: 0, requestId: 0,
  };

  // ---------- URL state ----------
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    for (const [k, key] of [["src", "source"], ["run", "run"], ["pt", "point"], ["g", "group"], ["w", "weights"], ["f", "foreign"], ["sel", "selected"], ["view", "view"], ["cmp", "compare"]]) {
      if (p.has(k)) state[key] = p.get(k);
    }
  }
  function writeHash() {
    const p = new URLSearchParams();
    const put = (k, v) => v && p.set(k, v);
    put("src", state.source); put("run", state.run); put("pt", state.point); put("g", state.group);
    put("w", state.weights); put("f", state.foreign); put("sel", state.selected); put("view", state.view); p.set("cmp", state.compare || "");
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
    $("export").onclick = () => {
      const q = new URLSearchParams({ source: state.source, run: state.run || "", point: state.point || "", weights: state.weights, foreign: state.foreign, group: state.group, compare: state.compare || "" });
      location.href = "/api/export.csv?" + q;
    };
    document.querySelectorAll(".group-tabs button").forEach((b) => (b.onclick = () => { state.group = b.dataset.group; state.selected = null; render(); }));
    document.querySelectorAll(".view-tabs button").forEach((b) => (b.onclick = () => { state.view = b.dataset.view; render(); }));
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
    if (state.min > 0) rows = rows.filter((r) => r.total != null && r.total >= state.min);
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
    $("synthetic-chip").hidden = !d.synthetic;
    $("unverified-chip").hidden = d.verified;
    for (const name of ["VN30", "HNX30"]) {
      const g = d.groups[name];
      document.querySelector(`[data-count="${name}"]`).textContent = g ? `${g.ranked}/${g.members}` : "";
    }
    document.querySelectorAll(".group-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.group === state.group)));
    document.querySelectorAll(".view-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === state.view)));
    for (const v of ["rank", "quality", "method"]) $("view-" + v).hidden = state.view !== v;
    $("footer-source").textContent = `Nguồn ${d.source === "synthetic" ? "giả lập" : d.source.toUpperCase()}${d.profile ? " · " + d.profile : ""} · giờ UTC+7`;
    $("controls-summary").textContent = `${clock(d.as_of)} · ${d.weights.id === "balanced" ? "25/25/25/25" : "40/20/20/20"} · ${d.foreign === "value" ? "ngoại theo giá trị" : "ngoại theo khối lượng"}${compareAt() ? " · so với " + compareAt() : ""}`;
    renderMetrics(); renderNotice(); renderRank(); renderQuality(); renderMethod();
  }

  function renderMetrics() {
    const d = state.data, g = groupData();
    const leader = g && g.rows.find((r) => r.rank === 1);
    $("m-ranked").textContent = g ? `${g.ranked}/${g.members}` : "–";
    $("m-ranked-note").textContent = g && g.ranked ? `${state.group} · nhóm so sánh ${g.cohort_size} mã` : `${state.group} · chưa đủ điều kiện`;
    $("m-leader").textContent = leader ? leader.symbol : "—";
    $("m-leader-note").textContent = !leader ? "chưa có hạng"
      : `${fmt(leader.total)} điểm` + (leader.rank_change > 0 ? ` · từ hạng ${leader.prev_rank}` : leader.prev_rank === 1 ? " · giữ hạng 1" : "");
    $("m-asof").textContent = d.method_kind === "daily" ? day(d.as_of) : clock(d.as_of);
    $("m-asof-note").textContent = d.method_kind === "daily" ? "cuối phiên" : day(d.as_of);
    if (d.freshness_seconds != null) {
      $("m-fresh").textContent = `${fmt(d.freshness_seconds, 0)} giây`;
      $("m-fresh-note").textContent = `từ bản ghi gần nhất · ngưỡng ${fmt(d.policy.max_age_seconds, 0)} giây`;
    } else {
      $("m-fresh").textContent = "—";
      $("m-fresh-note").textContent = d.source_kind === "daily" ? "dữ liệu tổng hợp cuối ngày từ SSI REST"
        : d.source_kind === "demo-board" ? "bảng điểm giả lập, không có thời gian nguồn"
        : "chưa có bản ghi của lần kết nối này";
    }
    $("cohort-note").textContent = g && g.config_id ? `Cấu hình ${String(g.config_id).slice(0, 6)} · tập mã ${String(g.cohort_id).slice(0, 6)}` : "";
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
    if (!state.selected || !g.rows.some((r) => r.symbol === state.selected)) {
      state.selected = (g.rows.find((r) => r.rank === 1) || g.rows[0] || {}).symbol || null;
      writeHash();  // keep the shared link on the symbol actually shown
    }
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
    else if (!rows.length) body = `<tr><td colspan="8"><div class="empty"><strong>Không có mã khớp bộ lọc</strong>Xóa ô tìm mã hoặc hạ ngưỡng điểm tổng.</div></td></tr>`;
    else body = rows.map((r) => `
      <tr data-symbol="${esc(r.symbol)}" tabindex="0" aria-selected="${r.symbol === state.selected}" class="${r.rank == null ? "unranked" : ""}">
        <td class="rank num"><span class="rank-cell"><b>${r.rank ?? "—"}</b>${deltaTag(r)}</span></td>
        <td class="sym">${esc(r.symbol)}</td>
        <td class="total"><span class="total-cell"><b class="num">${fmt(r.total)}</b>${r.rank != null ? stackBar(r) : ""}</span></td>
        ${shownFactors().map((f) => `<td class="factor"><span class="factor-cell">${r.scores[f] != null ? `<span class="bar"><i class="c-${f}" data-w="${r.scores[f]}"></i></span><span class="num">${fmt(r.scores[f], 0)}</span>` : `<span></span><span class="muted">—</span>`}</span></td>`).join("")}
        <td class="state">${statusTag(r)}</td>
      </tr>`).join("");
    const table = $("rank-table");
    table.innerHTML = `<caption class="sr-only">Xếp hạng ${esc(state.group)}</caption><thead><tr>${th}</tr></thead><tbody>${body}</tbody>`;
    applyWidths(table);
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
    writeHash(); renderDetail(); renderChart();
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
    if (!r) { el.innerHTML = `<div class="empty"><strong>Chưa chọn mã</strong>Bấm vào một dòng trong bảng.</div>`; $("price").innerHTML = ""; return; }
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
    try {
      const h = await get("/api/history", { source: state.source, run: state.run, point: state.point, symbol });
      if (state.selected !== symbol) return;
      state.price = { symbol, points: h.points, open: row.raw.openPrice };
      drawPrice();
    } catch (err) {
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
    const age = (v) => v == null ? `<span class="muted">—</span>` : `<span class="age${v > limit ? " stale" : ""}">${fmt(v, 0)}</span>`;
    $("quality-table").innerHTML = `<thead><tr>${["Mã", "Phiên", "Giá và khớp (giây)", "Sổ lệnh (giây)", "Khối ngoại (giây)", "Trạng thái", "Lý do / cảnh báo"].map((h) => `<th scope="col"><button type="button" tabindex="-1">${h}</button></th>`).join("")}</tr></thead>
      <tbody>${g.rows.map((r) => `<tr><td class="sym">${esc(r.symbol)}</td><td>${esc(r.session || "—")}</td><td>${age(r.ages.trade)}</td><td>${age(r.ages.book)}</td><td>${age(r.ages.foreign)}</td>
        <td>${statusTag(r)}</td><td class="muted why" title="${esc([...r.status.details, ...r.warnings].join(" · "))}">${esc([...ownDetails(r), ...ownWarnings(r)].join(" · ") || "—")}</td></tr>`).join("")}</tbody>`;
    const gaps = d.gaps.map((x) => `${clock(x.start)}–${clock(x.end)} (${x.kind === "disconnected" ? "mất kết nối" : x.kind})`).join(", ");
    const common = commonWarnings();
    $("quality-note").textContent = `Tuổi (giây) tính từ thời gian nguồn của trường lâu nhất trong mỗi cụm; ngưỡng ${fmt(limit, 0)} giây là ngưỡng thử nghiệm, sẽ hiệu chỉnh từ dữ liệu thật.`
      + (common.length ? ` Áp dụng cho cả nhóm: ${common.join("; ").toLowerCase()}.` : "") + (gaps ? ` Khoảng gián đoạn: ${gaps}.` : "");
  }

  function renderMethod() {
    const d = state.data, g = groupData();
    $("method").innerHTML = `
      ${d.method_kind === "daily" ? `<div><h3>Đang xem chế độ cuối ngày</h3><p>Xếp hạng theo dữ liệu tổng hợp từng phiên của SSI (REST securitiesSummary, từng mã). Ba yếu tố: động lượng = % đóng cửa so với mở cửa; thanh khoản = điểm phân vị của giá trị khớp cả phiên; dòng tiền ngoại = (mua − bán của khối ngoại) / giá trị khớp. Trọng số 33/33/33 hoặc 50/25/25. Không có sổ lệnh nên không có cung–cầu, độ sâu và chênh lệch giá. Mã thiếu dữ liệu khối ngoại (SSI trả trống) không được xếp hạng. Đây là phương pháp khác (daily-v1), không so trực tiếp với bảng trong phiên.</p></div>` : ""}
      <div><h3>Sản phẩm làm gì</h3><p>Xếp hạng tương đối các cổ phiếu trong cùng nhóm VN30 hoặc HNX30 tại một mốc của phiên khớp lệnh liên tục, để thu hẹp danh sách cần nghiên cứu tiếp. Không dự báo giá, không đặt lệnh.</p></div>
      <div><h3>Bốn yếu tố</h3><ul>
        <li><b>Động lượng</b>: % thay đổi từ giá mở cửa đến giá khớp gần nhất.</li>
        <li><b>Thanh khoản</b>: trung bình điểm phân vị của giá trị khớp, độ sâu ba mức giá mỗi bên và chênh lệch mua–bán (hẹp hơn tốt hơn).</li>
        <li><b>Dòng tiền ngoại</b>: (mua − bán của nhà đầu tư nước ngoài) / tổng giá trị khớp, hoặc theo khối lượng.</li>
        <li><b>Cung–cầu</b>: (khối lượng chào mua − chào bán) / tổng khối lượng chào ở ba mức giá.</li></ul></div>
      <div><h3>Cách chấm</h3><p>Mỗi yếu tố đổi thành điểm phân vị 0–100 trong nhóm đủ dữ liệu; điểm tổng là tổng có trọng số. Cần tối thiểu 10 mã hợp lệ; điểm bằng nhau cùng hạng. Không xếp hạng khi thiếu hoặc cũ dữ liệu, ngoài phiên LO, mất kết nối, hoặc nguồn thật chưa xác minh. Không tự bỏ một yếu tố rồi chia lại trọng số.</p></div>
      <div><h3>Giới hạn</h3><p>Trọng số là cấu hình thử nghiệm; thanh khoản có thể nghiêng về mã vốn hóa lớn và các yếu tố có thể tương quan. Sổ lệnh chỉ phản ánh lượng chào tại mốc ghi nhận. Dữ liệu giả lập chỉ dùng kiểm tra phần mềm.</p></div>
      <div><h3>Thông tin lần tính</h3><dl>
        <dt>Nguồn</dt><dd>${esc(d.source)}${d.profile ? " · " + esc(d.profile) : ""}</dd><dt>Lần thu thập</dt><dd>${esc(d.run)}</dd>
        <dt>Mốc</dt><dd>${esc(d.as_of)}</dd><dt>Phương pháp</dt><dd>${esc(g && g.method || "—")}</dd>
        <dt>Cấu hình</dt><dd>${esc(g && g.config_id || "—")}</dd><dt>Tập mã</dt><dd>${esc(g && g.cohort_id || "—")}</dd>
        <dt>Trọng số</dt><dd>${esc(d.weights.label)}</dd><dt>Khối ngoại</dt><dd>${d.foreign === "value" ? "theo giá trị" : "theo khối lượng"}</dd>
        <dt>So sánh với</dt><dd>${d.compare ? (d.compare.as_of ? esc(d.compare.as_of) + " (" + esc(d.compare.label) + ")" : "không có mốc " + esc(d.compare.label)) : "không so sánh"}</dd></dl></div>`;
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

  init();
})();
