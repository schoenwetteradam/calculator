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
let allData = null;
let currentRange = 12; // months shown on chart

/* ============================================================
   DOM refs
   ============================================================ */
const countySelect = document.getElementById("county-select");
const loadBtn = document.getElementById("load-btn");
const loading = document.getElementById("loading");
const errorBanner = document.getElementById("error-banner");
const sourceNotice = document.getElementById("source-notice");
const compareBtn = document.getElementById("compare-btn");
const compareGrid = document.getElementById("compare-grid");

/* ============================================================
   Init
   ============================================================ */
document.addEventListener("DOMContentLoaded", () => {
  loadMarketData("WI"); // default to Wisconsin on page load

  loadBtn.addEventListener("click", () => {
    loadMarketData(countySelect.value);
  });

  countySelect.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadMarketData(countySelect.value);
  });

  compareBtn.addEventListener("click", loadComparison);

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
async function loadMarketData(state) {
  showLoading(true);
  hideError();
  hideSections();

  try {
    const resp = await fetch(`/api/market-data?state=${state}`);
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
  ];

  const tbody = document.querySelector("#stats-table tbody");
  tbody.innerHTML = rows
    .map(([label, val]) => `<tr><td>${label}</td><td>${val}</td></tr>`)
    .join("");
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
  ["hero-metrics", "chart-section", "stats-section", "deals-section"].forEach((id) => {
    const s = document.getElementById(id);
    if (s) s.classList.remove("hidden");
  });
}

function hideSections() {
  ["hero-metrics", "chart-section", "stats-section", "deals-section", "redfin-section", "source-notice"].forEach((id) => {
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
