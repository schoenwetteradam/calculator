/**
 * Dodge County Property Price Analyzer — Frontend
 * Loads market data from the Flask API and renders charts + metrics.
 */

/* ============================================================
   State
   ============================================================ */
let priceChart = null;
let scoreChart = null;
let redinChart = null;
let mortgageChart = null;
let allData = null;
let currentRange = 12; // months shown on chart

/* ============================================================
   DOM refs
   ============================================================ */
const countySelect = document.getElementById("county-select");
const loadBtn = document.getElementById("load-btn");
const municipalitySelect = document.getElementById("municipality-select");
const loading = document.getElementById("loading");
const errorBanner = document.getElementById("error-banner");
const sourceNotice = document.getElementById("source-notice");
const compareBtn = document.getElementById("compare-btn");
const compareGrid = document.getElementById("compare-grid");
const wiRankingsBtn = document.getElementById("wi-rankings-btn");
const wiRankingsGrid = document.getElementById("wi-rankings-grid");

/* ============================================================
   Init
   ============================================================ */
document.addEventListener("DOMContentLoaded", async () => {
  await loadMunicipalityOptions();
  toggleMunicipalitySelect("WI");
  loadMarketData("WI", municipalitySelect.value || "all"); // default to Wisconsin on page load
  loadSignals("WI");    // load macro signals in parallel

  loadBtn.addEventListener("click", () => {
    const state = countySelect.value;
    const municipality = state === "WI" ? municipalitySelect.value : "all";
    loadMarketData(state, municipality);
    loadSignals(state);
  });

  countySelect.addEventListener("change", () => {
    toggleMunicipalitySelect(countySelect.value);
  });

  countySelect.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const state = countySelect.value;
      const municipality = state === "WI" ? municipalitySelect.value : "all";
      loadMarketData(state, municipality);
      loadSignals(state);
    }
  });

  compareBtn.addEventListener("click", loadComparison);
  if (wiRankingsBtn) wiRankingsBtn.addEventListener("click", loadWiMunicipalityRankings);

  document.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".toggle-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentRange = parseInt(btn.dataset.range, 10);
      if (allData) updateChart(allData.zhvi_history, allData.trend_detail, currentRange);
    });
  });
});

/* ============================================================
   Data loading
   ============================================================ */


async function loadMunicipalityOptions() {
  try {
    const resp = await fetch("/api/wi-dodge-municipalities");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const options = await resp.json();

    municipalitySelect.innerHTML = options
      .map((opt) => `<option value="${opt.id}">${opt.label} (${opt.kind})</option>`)
      .join("");

    municipalitySelect.value = "all";
  } catch (e) {
    console.warn("Failed to load municipality options:", e.message);
    municipalitySelect.innerHTML = '<option value="all">All of Dodge County</option>';
  }
}

function toggleMunicipalitySelect(state) {
  const isWi = state === "WI";
  municipalitySelect.disabled = !isWi;
  if (!isWi) municipalitySelect.value = "all";
}
async function loadMarketData(state, municipality = "all") {
  showLoading(true);
  hideError();
  hideSections();

  try {
    const resp = await fetch(`/api/market-data?state=${state}&municipality=${encodeURIComponent(municipality)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "Unknown error");

    allData = data;
    renderAll(data);
    showSections();
  } catch (err) {
    showError("Failed to load market data: " + err.message);
  } finally {
    showLoading(false);
  }
}

/* ============================================================
   Render everything
   ============================================================ */
function renderAll(data) {
  const { trend, market_stats, trend_detail, deals, investment_score, zhvi_history, county, data_source } = data;

  // Source notice
  const src = data_source || "";
  sourceNotice.textContent = `📡 Data source: ${src}`;
  sourceNotice.classList.remove("hidden");

  renderHeroMetrics(trend, market_stats, investment_score, trend_detail);
  updateChart(zhvi_history, trend_detail, currentRange);
  renderStatsTable(market_stats);
  renderTargetHomeView(market_stats, county);
  renderScoreGauge(investment_score);
  renderScoreComponents(investment_score);
  renderDeals(deals);
  renderRedfin(data);
}

/* ---- Hero metrics ---- */
function renderHeroMetrics(trend, stats, score, detail) {
  // Current price
  el("metric-price").textContent = fmt$(trend.current_value || stats.current_zhvi);

  // Trend
  const dir = trend.direction;
  const chg6 = trend.change_6mo_pct;
  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "→";
  const cls = dir === "up" ? "trend-up" : dir === "down" ? "trend-down" : "trend-stable";
  el("metric-trend").innerHTML = `<span class="${cls}">${arrow} ${Math.abs(chg6).toFixed(1)}%</span>`;
  el("metric-trend-period").textContent = `${trend.strength} ${dir} · 6-month`;

  // 12-mo change
  const chg12 = trend.change_12mo_pct;
  const cls12 = chg12 >= 0 ? "trend-up" : "trend-down";
  el("metric-12mo").innerHTML = `<span class="${cls12}">${chg12 >= 0 ? "+" : ""}${chg12.toFixed(1)}%</span>`;

  // Yield
  el("metric-yield").textContent = (stats.gross_rental_yield_pct || 0).toFixed(1) + "%";

  // Grade
  const gradeColors = { A: "#10b981", B: "#34d399", C: "#f59e0b", D: "#f87171", F: "#ef4444" };
  el("metric-grade").textContent = score.grade || "—";
  el("metric-grade").style.color = gradeColors[score.grade] || "#e2e8f0";
  el("metric-score").textContent = `Score: ${score.score}`;

  // Phase
  el("metric-phase").textContent = detail.phase || "—";
  el("metric-phase").style.color = detail.phase_color || "#e2e8f0";
  el("metric-momentum").textContent = `Momentum: ${detail.momentum || "—"}`;
}

/* ---- Price history chart ---- */
function updateChart(history, detail, range) {
  if (!history || !history.length) return;

  let slice = range > 0 ? history.slice(-range) : history;
  const labels = slice.map((h) => fmtDate(h.date));
  const prices = slice.map((h) => h.value);

  // Slice moving averages to match
  const total = detail.values ? detail.values.length : history.length;
  const offset = total - slice.length;
  const ma3 = (detail.ma3 || []).slice(offset);
  const ma6 = (detail.ma6 || []).slice(offset);
  const ma12 = (detail.ma12 || []).slice(offset);

  const datasets = [
    {
      label: "ZHVI Price",
      data: prices,
      borderColor: "#6366f1",
      backgroundColor: "rgba(99,102,241,0.08)",
      fill: true,
      tension: 0.35,
      pointRadius: 2,
      borderWidth: 2,
    },
    { label: "3-mo MA", data: ma3, borderColor: "#f59e0b", fill: false, tension: 0.3, pointRadius: 0, borderWidth: 1.5, borderDash: [4,2] },
    { label: "6-mo MA", data: ma6, borderColor: "#10b981", fill: false, tension: 0.3, pointRadius: 0, borderWidth: 1.5, borderDash: [4,2] },
    { label: "12-mo MA", data: ma12, borderColor: "#ef4444", fill: false, tension: 0.3, pointRadius: 0, borderWidth: 1.5, borderDash: [6,3] },
  ];

  const ctx = document.getElementById("priceChart").getContext("2d");
  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1a1d27",
          borderColor: "#2d3348",
          borderWidth: 1,
          titleColor: "#94a3b8",
          bodyColor: "#e2e8f0",
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${fmt$(ctx.raw)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#64748b", maxTicksLimit: 12, font: { size: 11 } },
          grid: { color: "#1e2235" },
        },
        y: {
          ticks: {
            color: "#64748b",
            font: { size: 11 },
            callback: (v) => "$" + (v / 1000).toFixed(0) + "k",
          },
          grid: { color: "#1e2235" },
        },
      },
    },
  });
}

/* ---- Stats table ---- */
function renderStatsTable(stats) {
  const rows = [
    ["Current ZHVI (Zillow)", fmt$(stats.current_zhvi)],
    ["Census Median Home Value", fmt$(stats.median_home_value_census)],
    ["Median Gross Rent", fmt$(stats.median_rent) + "/mo"],
    ["Median Household Income", fmt$(stats.median_income)],
    ["Estimated Monthly PITI (7%)", fmt$(stats.estimated_monthly_piti)],
    ["Affordability Index", stats.affordability_index + "%"],
    ["Price-to-Rent Ratio", stats.price_to_rent_ratio + "x"],
    ["Price-to-Income Ratio", stats.price_to_income_ratio + "x"],
    ["Gross Rental Yield", stats.gross_rental_yield_pct + "%"],
    ["Net Rental Yield (est.)", stats.net_rental_yield_pct + "%"],
    ["Historical High (period)", fmt$(stats.historical_high)],
    ["% from Peak", colorPct(stats.pct_from_high)],
    ["% from Low", "+" + stats.pct_from_low + "%"],
    ["Market Volatility", stats.volatility_pct + "%"],
    ["Total Housing Units", num(stats.total_units)],
    ["Owner Occupied", num(stats.owner_occupied)],
    ["Renter Occupied", num(stats.renter_occupied)],
    ["Population (ACS)", num(stats.population)],
    ["Single-Family Housing Share", (stats.single_family_share_pct || 0) + "%"],
    ["4+ Bedroom Housing Share", (stats.four_plus_bedroom_share_pct || 0) + "%"],
    ["Est. 4+BD/2+BA SFH Price", fmt$(stats.sfh_family_price_estimate)],
    ["Est. 4+BD/2+BA Monthly PITI", fmt$(stats.sfh_family_monthly_piti)],
    ["Income Needed (30% rule)", fmt$(stats.income_needed_for_sfh_family_home)],
    ["Family Payment Burden", (stats.family_payment_burden_pct || 0) + "%"],
    ["Family Affordability Score", (stats.family_affordability_score || 0) + "/100"],
    ["Family Investor-Fit Score", (stats.family_investor_fit_score || 0) + "/100"],
    ["4+BD/2+BA Inventory (est.)", num(stats.target_4bd2ba_units_estimate)],
    ["4+BD/2+BA Affordability Index", (stats.target_4bd2ba_affordability_index || 0) + ""],
    ["4+BD/2+BA Payment Burden", (stats.target_4bd2ba_payment_burden_pct || 0) + "%"],
  ];

  const tbody = document.querySelector("#stats-table tbody");
  tbody.innerHTML = rows
    .map(([label, val]) => `<tr><td>${label}</td><td>${val}</td></tr>`)
    .join("");
}

function renderTargetHomeView(stats, county) {
  const grid = el("target-home-grid");
  if (!grid) return;

  const isWi = county && county.state === "WI";
  const title = isWi ? "Dodge County, WI" : `Dodge County, ${county?.state || ""}`;

  const cards = [
    ["Area", title],
    ["Est. 4+BD/2+BA Inventory", num(stats.target_4bd2ba_units_estimate)],
    ["4+BD/2+BA Share", (stats.target_4bd2ba_share_pct || 0) + "%"],
    ["2+ Bath Proxy Share", (stats.two_plus_bath_proxy_share_pct || 0) + "%"],
    ["Est. Target Price", fmt$(stats.target_4bd2ba_price_estimate)],
    ["Est. Monthly PITI", fmt$(stats.target_4bd2ba_monthly_piti)],
    ["Income Needed (30%)", fmt$(stats.target_4bd2ba_income_needed)],
    ["Affordability Index", (stats.target_4bd2ba_affordability_index || 0).toFixed(1)],
  ];

  grid.innerHTML = cards
    .map(([label, value]) => `<div class="target-kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value || "—"}</div></div>`)
    .join("");

  const rationale = el("rationale-list");
  const notes = stats.analysis_rationales || [];
  rationale.innerHTML = notes.length
    ? notes.map((n) => `<li>${n}</li>`).join("")
    : '<li>No rationale details available for this selection.</li>';
}

/* ---- Score gauge (arc) ---- */
function renderScoreGauge(score) {
  const canvas = document.getElementById("scoreGauge");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const cx = W / 2, cy = H - 10;
  const r = 90;
  const startAngle = Math.PI;
  const endAngle = 2 * Math.PI;
  const pct = (score.score || 0) / 100;

  // Background arc
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.strokeStyle = "#2d3348";
  ctx.lineWidth = 16;
  ctx.lineCap = "round";
  ctx.stroke();

  // Color gradient stops
  const grad = ctx.createLinearGradient(cx - r, 0, cx + r, 0);
  grad.addColorStop(0, "#ef4444");
  grad.addColorStop(0.5, "#f59e0b");
  grad.addColorStop(1, "#10b981");

  // Value arc
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, startAngle + pct * Math.PI);
  ctx.strokeStyle = grad;
  ctx.lineWidth = 16;
  ctx.lineCap = "round";
  ctx.stroke();

  el("gauge-score").textContent = score.score || "—";
  el("gauge-grade").textContent = "Grade " + (score.grade || "—");
}

/* ---- Score components bars ---- */
function renderScoreComponents(score) {
  const comps = score.components || {};
  const labels = {
    price_momentum: "Price Momentum",
    affordability: "Affordability",
    rental_yield: "Rental Yield",
    market_stability: "Market Stability",
    long_term_appreciation: "LT Appreciation",
    family_home_fit: "4+BD Family Home Fit",
  };

  const container = el("score-components");
  container.innerHTML = Object.entries(comps)
    .map(([key, val]) => {
      const color = val >= 75 ? "#10b981" : val >= 55 ? "#f59e0b" : "#ef4444";
      return `
        <div class="score-row">
          <span class="score-row-label">${labels[key] || key}</span>
          <div class="score-bar-wrap">
            <div class="score-bar" style="width:${val}%;background:${color}"></div>
          </div>
          <span class="score-row-val">${val}</span>
        </div>`;
    })
    .join("");

  el("recommendation").textContent = score.recommendation || "";
}

/* ---- Deal cards ---- */
function renderDeals(deals) {
  const grid = el("deals-grid");
  const noDeal = el("no-deals");

  if (!deals || !deals.length) {
    grid.innerHTML = "";
    noDeal.classList.remove("hidden");
    return;
  }

  noDeal.classList.add("hidden");
  grid.innerHTML = deals
    .map((d) => {
      const riskStyle = `background:${d.risk_color}22;color:${d.risk_color};border:1px solid ${d.risk_color}44`;
      return `
        <div class="deal-card">
          <div class="deal-header">
            <div class="deal-title">
              <span class="deal-icon">${d.icon}</span>
              <span>${d.type}</span>
            </div>
            <span class="deal-score">${Math.round(d.opportunity_score)}</span>
          </div>
          <p class="deal-desc">${d.description}</p>
          <div class="deal-action">💡 ${d.action}</div>
          <div class="deal-footer">
            <span class="risk-badge" style="${riskStyle}">Risk: ${d.risk}</span>
            <span style="color:#475569;font-size:0.72rem">Score ${Math.round(d.opportunity_score)}/100</span>
          </div>
          <div class="score-bar-deal">
            <div class="score-fill-deal" style="width:${d.opportunity_score}%"></div>
          </div>
        </div>`;
    })
    .join("");
}

/* ---- Redfin chart (state-level) ---- */
function renderRedfin(data) {
  const rf = (data.trend_detail && data.zhvi_history) ? null : null; // placeholder — use zhvi as proxy
  const rfSection = el("redfin-section");

  // We use the ZHVI data for illustration if Redfin not available
  // A real Redfin chart would show DOM / sale-to-list trends
  // Here we chart price momentum (monthly % change) as a bar chart
  const history = data.zhvi_history || [];
  if (history.length < 4) { rfSection.classList.add("hidden"); return; }

  const recent = history.slice(-18);
  const labels = recent.map((h) => fmtDate(h.date));
  const changes = recent.map((h, i) => {
    if (i === 0) return 0;
    const prev = recent[i - 1].value;
    return prev ? +((h.value - prev) / prev * 100).toFixed(2) : 0;
  });

  const colors = changes.map((v) => (v >= 0 ? "rgba(16,185,129,0.6)" : "rgba(239,68,68,0.6)"));

  const ctx = document.getElementById("redinChart").getContext("2d");
  if (redinChart) redinChart.destroy();

  redinChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Monthly Price Change %",
        data: changes,
        backgroundColor: colors,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (c) => ` ${c.raw > 0 ? "+" : ""}${c.raw}%` },
        },
      },
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 10 }, maxTicksLimit: 9 }, grid: { display: false } },
        y: { ticks: { color: "#64748b", callback: (v) => v + "%" }, grid: { color: "#1e2235" } },
      },
    },
  });

  rfSection.classList.remove("hidden");
  rfSection.querySelector("h2").innerHTML =
    `Monthly Price Change (ZHVI) <span class="badge-src">Zillow</span>`;
}

/* ============================================================
   Real-world signals
   ============================================================ */
async function loadSignals(state) {
  try {
    const resp = await fetch(`/api/signals?state=${state}`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.success) return;
    renderSignals(data);
    document.getElementById("signals-section").classList.remove("hidden");
  } catch (e) {
    console.warn("Signals load failed:", e.message);
  }
}

function renderSignals(data) {
  const score = data.composite_score || 50;
  const fredAvail = data.fred_available;

  // Badge
  el("signals-score-badge").textContent = `Macro Score: ${score.toFixed(0)}/100`;
  if (fredAvail) el("fred-notice").classList.remove("hidden");

  // Needle on gradient bar (0% = left/bearish, 100% = right/bullish)
  el("macro-bar-needle").style.left = score + "%";

  // Signal cards
  const all = { ...data.macro, ...data.local };
  const preferred_order = [
    "mortgage_30yr", "fed_funds", "treasury_10yr",
    "state_unemployment", "cpi_yoy",
    "housing_starts", "building_permits", "existing_homes", "case_shiller",
  ];

  const grid = el("signals-grid");
  grid.innerHTML = preferred_order
    .filter((k) => all[k])
    .map((k) => renderSignalCard(k, all[k]))
    .join("");

  // Mortgage rate chart
  const mData = data.macro?.mortgage_30yr;
  if (mData?.history?.length > 1) {
    renderMortgageChart(mData.history);
  } else {
    el("mortgage-chart-panel").style.display = "none";
  }

  // News
  renderNews(data.news || []);
}

function renderSignalCard(key, s) {
  const trendIcon = s.trend === "rising" ? "▲" : s.trend === "falling" ? "▼" : "→";
  const trendCls = s.trend === "rising" ? "signal-trend-up" : s.trend === "falling" ? "signal-trend-down" : "signal-trend-flat";
  const estimated = s.estimated ? ' <span style="color:#475569;font-size:0.68rem">(est.)</span>' : "";
  const unit = s.unit || "";

  let valueDisplay;
  if (key === "case_shiller") {
    valueDisplay = s.yoy_change_pct != null
      ? `${s.yoy_change_pct >= 0 ? "+" : ""}${s.yoy_change_pct.toFixed(1)}% YoY`
      : s.value?.toFixed(1);
  } else if (unit === "%" || unit === "idx") {
    valueDisplay = typeof s.value === "number" ? s.value.toFixed(2) + (unit === "%" ? "%" : "") : "—";
  } else if (unit === "k") {
    valueDisplay = typeof s.value === "number" ? s.value.toFixed(0) + "k" : "—";
  } else if (unit === "M") {
    valueDisplay = typeof s.value === "number" ? s.value.toFixed(2) + "M" : "—";
  } else {
    valueDisplay = typeof s.value === "number" ? s.value.toFixed(2) : "—";
  }

  const pillLabel = (s.signal || "neutral").replace("_", " ").replace("strong ", "");
  return `
    <div class="signal-card">
      <div class="signal-card-header">
        <div class="signal-icon-title">
          <span>${s.icon || "📊"}</span>
          <span>${s.label || key}</span>
        </div>
        <span class="signal-pill pill-${s.signal || "neutral"}">${pillLabel}</span>
      </div>
      <div class="signal-value">${valueDisplay}${estimated}</div>
      <div class="signal-meta">
        <span>${s.category || ""}</span>
        ${s.change != null && s.change !== 0
          ? `<span class="${trendCls}" style="margin-left:8px">${trendIcon} ${Math.abs(s.change).toFixed(2)}${unit === "%" ? "pp" : ""}</span>`
          : ""}
        ${s.date ? `<span style="margin-left:8px;color:#475569">${s.date}</span>` : ""}
      </div>
      <div class="signal-desc">${s.description || ""}</div>
      ${s.why ? `<div class="signal-why">${s.why}</div>` : ""}
    </div>`;
}

function renderMortgageChart(history) {
  const labels = history.map((h) => fmtDate(h.date));
  const values = history.map((h) => h.value);
  const ctx = document.getElementById("mortgageChart").getContext("2d");
  if (mortgageChart) mortgageChart.destroy();

  const avg = values.reduce((a, b) => a + b, 0) / values.length;

  mortgageChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "30-yr Rate %",
          data: values,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245,158,11,0.08)",
          fill: true,
          tension: 0.3,
          pointRadius: 2,
          borderWidth: 2,
        },
        {
          label: "Average",
          data: values.map(() => avg),
          borderColor: "#475569",
          fill: false,
          pointRadius: 0,
          borderWidth: 1,
          borderDash: [4, 4],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (c) => ` ${c.dataset.label}: ${c.raw.toFixed(2)}%` },
        },
      },
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 10 }, maxTicksLimit: 8 }, grid: { display: false } },
        y: {
          ticks: { color: "#64748b", callback: (v) => v + "%" },
          grid: { color: "#1e2235" },
          min: Math.max(0, Math.min(...values) - 0.5),
        },
      },
    },
  });
}

function renderNews(items) {
  const list = el("news-list");
  if (!items.length) {
    list.innerHTML = '<li class="news-loading">No news feeds available right now.</li>';
    return;
  }
  list.innerHTML = items
    .map(
      (item) => `
      <li>
        <a href="${item.link || "#"}" target="_blank" rel="noopener noreferrer">${item.title}</a>
        <div class="news-meta">${item.source || ""}${item.published ? " · " + item.published.slice(0, 16) : ""}</div>
      </li>`
    )
    .join("");
}



async function loadWiMunicipalityRankings() {
  wiRankingsBtn.textContent = "Loading…";
  wiRankingsBtn.disabled = true;
  wiRankingsGrid.classList.remove("hidden");
  wiRankingsGrid.innerHTML = '<div class="compare-card"><h3>Loading rankings…</h3><p style="color:#94a3b8">Calculating municipality scores and family-home fit metrics.</p></div>';
  try {
    const resp = await fetch("/api/wi-municipality-rankings");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || "Failed to load WI rankings");
    renderWiMunicipalityRankings(data.rankings || []);
  } catch (e) {
    wiRankingsGrid.innerHTML = `<div class="compare-card"><h3>Unable to load WI rankings</h3><p style="color:#ef4444">${e.message}</p></div>`;
    showError("WI municipality rankings failed: " + e.message);
  } finally {
    wiRankingsBtn.textContent = "Reload WI Rankings";
    wiRankingsBtn.disabled = false;
  }
}

function renderWiMunicipalityRankings(rows) {
  wiRankingsGrid.innerHTML = rows
    .map((row, idx) => {
      if (row.error) return `<div class="compare-card"><h3>${row.municipality?.label || "Unknown"}</h3><p style="color:#ef4444">${row.error}</p></div>`;

      const inv = row.investment_score || {};
      const stats = row.market_stats || {};
      const trend = row.trend || {};
      const rank = idx + 1;
      return `
        <div class="compare-card">
          <h3>#${rank} ${row.municipality.label}</h3>
          <table>
            <tr><td>Overall Rank Score</td><td><strong>${row.overall_rank_score}</strong></td></tr>
            <tr><td>Investment Score</td><td>${inv.score || "—"} (${inv.grade || "—"})</td></tr>
            <tr><td>Family Investor-Fit</td><td>${stats.family_investor_fit_score || "—"}/100</td></tr>
            <tr><td>4+BD/2+BA Finder Score</td><td>${row.target_finder_score || "—"}/100</td></tr>
            <tr><td>4+BD/2+BA Share</td><td>${stats.target_4bd2ba_share_pct || "—"}%</td></tr>
            <tr><td>Est. 4+BD/2+BA PITI</td><td>${fmt$(stats.target_4bd2ba_monthly_piti)}</td></tr>
            <tr><td>12-mo Trend (scaled proxy)</td><td>${trend.change_12mo_pct >= 0 ? "+" : ""}${(trend.change_12mo_pct || 0).toFixed(1)}%</td></tr>
          </table>
        </div>`;
    })
    .join("");

  wiRankingsGrid.classList.remove("hidden");
}

/* ============================================================
   County comparison
   ============================================================ */
async function loadComparison() {
  compareBtn.textContent = "Loading…";
  compareBtn.disabled = true;
  try {
    const resp = await fetch("/api/compare");
    const data = await resp.json();
    if (!data.success) throw new Error(data.error);
    renderComparison(data.counties);
  } catch (e) {
    showError("Comparison failed: " + e.message);
  } finally {
    compareBtn.textContent = "Reload Comparison";
    compareBtn.disabled = false;
  }
}

function renderComparison(counties) {
  compareGrid.innerHTML = counties
    .map((c) => {
      if (c.error) {
        return `<div class="compare-card"><h3>${c.county.label}</h3><p style="color:#ef4444">${c.error}</p></div>`;
      }
      const { trend, market_stats: s, investment_score: inv } = c;
      const dir = trend.direction;
      const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "→";
      const cls = dir === "up" ? "trend-up" : dir === "down" ? "trend-down" : "trend-stable";
      const gradeColors = { A: "#10b981", B: "#34d399", C: "#f59e0b", D: "#f87171", F: "#ef4444" };
      return `
        <div class="compare-card">
          <h3>${c.county.label}</h3>
          <table>
            <tr><td>Median Home Value</td><td>${fmt$(trend.current_value)}</td></tr>
            <tr><td>6-mo Trend</td><td><span class="${cls}">${arrow} ${Math.abs(trend.change_6mo_pct).toFixed(1)}%</span></td></tr>
            <tr><td>12-mo Change</td><td>${trend.change_12mo_pct >= 0 ? "+" : ""}${trend.change_12mo_pct}%</td></tr>
            <tr><td>Rental Yield</td><td>${s.gross_rental_yield_pct}%</td></tr>
            <tr><td>Price/Income</td><td>${s.price_to_income_ratio}x</td></tr>
            <tr><td>Invest Grade</td><td style="color:${gradeColors[inv.grade] || '#e2e8f0'};font-size:1.1rem">${inv.grade} (${inv.score})</td></tr>
          </table>
        </div>`;
    })
    .join("");
  compareGrid.classList.remove("hidden");
}

/* ============================================================
   UI helpers
   ============================================================ */
function showLoading(on) {
  loading.classList.toggle("hidden", !on);
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove("hidden");
}

function hideError() {
  errorBanner.classList.add("hidden");
}

function showSections() {
  ["hero-metrics", "chart-section", "stats-section", "target-home-section", "deals-section"].forEach((id) => {
    const s = document.getElementById(id);
    if (s) s.classList.remove("hidden");
  });
}

function hideSections() {
  ["hero-metrics", "chart-section", "stats-section", "target-home-section", "deals-section", "redfin-section", "signals-section", "source-notice"].forEach((id) => {
    const s = document.getElementById(id);
    if (s) s.classList.add("hidden");
  });
}

function el(id) { return document.getElementById(id); }

function fmt$(n) {
  if (!n || isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function num(n) {
  if (!n || isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US").format(n);
}

function colorPct(pct) {
  if (pct === undefined || pct === null || isNaN(pct)) return "—";
  const cls = pct >= 0 ? "trend-up" : "trend-down";
  return `<span class="${cls}">${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%</span>`;
}

function fmtDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}
