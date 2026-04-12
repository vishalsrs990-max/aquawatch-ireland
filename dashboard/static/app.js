const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";

const cardsEl = document.getElementById("cards");
const historyBody = document.getElementById("historyBody");
const stationInput = document.getElementById("stationId");
const refreshBtn = document.getElementById("refreshBtn");
const severityPill = document.getElementById("severityPill");
const triggeredPill = document.getElementById("triggeredPill");
const updatedPill = document.getElementById("updatedPill");
const apiPill = document.getElementById("apiPill");
const rowCountEl = document.getElementById("rowCount");

const charts = {};

const SENSOR_META = {
  water_level_m: {
    label: "Water Level",
    short: "Water level",
    unit: "m",
    desc: "River level near the station",
    thresholds: {
      warning: (v) => v >= 2.0,
      critical: (v) => v >= 2.4
    }
  },
  rainfall_mm_h: {
    label: "Rainfall",
    short: "Rainfall",
    unit: "mm/h",
    desc: "Recent rain intensity",
    thresholds: {
      warning: (v) => v >= 10,
      critical: (v) => v >= 18
    }
  },
  water_temp_c: {
    label: "Temperature",
    short: "Temp",
    unit: "°C",
    desc: "Water temperature",
    thresholds: {
      warning: (v) => v < 8 || v > 16,
      critical: (v) => v < 6 || v > 20
    }
  },
  turbidity_ntu: {
    label: "Turbidity",
    short: "Turbidity",
    unit: "NTU",
    desc: "Water clarity / sediment",
    thresholds: {
      warning: (v) => v >= 30,
      critical: (v) => v >= 40
    }
  },
  flow_rate_m3s: {
    label: "Flow Rate",
    short: "Flow",
    unit: "m³/s",
    desc: "Estimated river flow",
    thresholds: {
      warning: (v) => v >= 45,
      critical: (v) => v >= 55
    }
  }
};

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || value === "") return "--";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return Number(num.toFixed(digits)).toString();
}

function formatTimestamp(value) {
  return value || "--";
}

function chartConfig(label) {
  return {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label,
          data: [],
          tension: 0.3,
          pointRadius: 3,
          borderWidth: 2,
          fill: false,
          spanGaps: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          display: true,
          position: "top"
        }
      },
      scales: {
        x: {
          ticks: {
            autoSkip: true,
            maxTicksLimit: 6,
            maxRotation: 0,
            minRotation: 0
          }
        },
        y: {
          beginAtZero: false
        }
      }
    }
  };
}

function createCharts() {
  charts.waterLevel = new Chart(
    document.getElementById("waterLevelChart"),
    chartConfig("Water level")
  );
  charts.rainfall = new Chart(
    document.getElementById("rainfallChart"),
    chartConfig("Rainfall")
  );
  charts.temp = new Chart(
    document.getElementById("tempChart"),
    chartConfig("Water temp")
  );
  charts.turbidity = new Chart(
    document.getElementById("turbidityChart"),
    chartConfig("Turbidity")
  );
  charts.flow = new Chart(
    document.getElementById("flowChart"),
    chartConfig("Flow rate")
  );
}

function classifyMetric(metricKey, rawValue) {
  const meta = SENSOR_META[metricKey];
  const value = Number(rawValue);

  if (!meta || Number.isNaN(value)) {
    return "NORMAL";
  }

  if (meta.thresholds.critical(value)) return "CRITICAL";
  if (meta.thresholds.warning(value)) return "WARNING";
  return "NORMAL";
}

function classifySensors(metrics = {}) {
  const results = {};

  Object.keys(SENSOR_META).forEach((key) => {
    results[key] = classifyMetric(key, metrics[key]);
  });

  return results;
}

function overallSeverity(statuses = {}) {
  const values = Object.values(statuses);
  if (values.includes("CRITICAL")) return "CRITICAL";
  if (values.includes("WARNING")) return "WARNING";
  return "NORMAL";
}

function triggerGroups(statuses = {}) {
  const critical = [];
  const warning = [];

  Object.entries(statuses).forEach(([key, status]) => {
    const name = SENSOR_META[key]?.short || key;
    if (status === "CRITICAL") critical.push(name);
    if (status === "WARNING") warning.push(name);
  });

  return { critical, warning };
}

function triggerText(statuses = {}) {
  const groups = triggerGroups(statuses);
  const parts = [];

  if (groups.critical.length) {
    parts.push(`Critical: ${groups.critical.join(", ")}`);
  }

  if (groups.warning.length) {
    parts.push(`Warning: ${groups.warning.join(", ")}`);
  }

  return parts.length ? parts.join(" | ") : "No sensor threshold breached";
}

function sensorHint(key) {
  const meta = SENSOR_META[key];
  if (!meta) return "";

  if (key === "water_level_m") return "Warning ≥ 2.0, Critical ≥ 2.4";
  if (key === "rainfall_mm_h") return "Warning ≥ 10, Critical ≥ 18";
  if (key === "water_temp_c") return "Warning < 8 or > 16, Critical < 6 or > 20";
  if (key === "turbidity_ntu") return "Warning ≥ 30, Critical ≥ 40";
  if (key === "flow_rate_m3s") return "Warning ≥ 45, Critical ≥ 55";

  return "";
}

function metricCards(metrics = {}, latest = {}) {
  const statuses = classifySensors(metrics);

  const defs = [
    ["water_level_m", "Water Level", `${formatNumber(metrics.water_level_m)} m`, "River level near the station"],
    ["rainfall_mm_h", "Rainfall", `${formatNumber(metrics.rainfall_mm_h)} mm/h`, "Recent rain intensity"],
    ["water_temp_c", "Temperature", `${formatNumber(metrics.water_temp_c)} °C`, "Water temperature"],
    ["turbidity_ntu", "Turbidity", `${formatNumber(metrics.turbidity_ntu)} NTU`, "Water clarity / sediment"],
    ["flow_rate_m3s", "Flow Rate", `${formatNumber(metrics.flow_rate_m3s)} m³/s`, "Estimated river flow"],
    ["windowSize", "Window Size", `${latest.windowSize ?? "--"}`, "Fog aggregation window"]
  ];

  cardsEl.innerHTML = defs.map(([key, label, value, sub]) => {
    if (key === "windowSize") {
      return `
        <div class="card NORMAL">
          <div class="card-head">
            <div class="label">${label}</div>
            <span class="mini-badge NORMAL">INFO</span>
          </div>
          <div class="value">${value}</div>
          <div class="sub">${sub}</div>
          <div class="sensor-hint">Aggregation batch size</div>
        </div>
      `;
    }

    const status = statuses[key] || "NORMAL";

    return `
      <div class="card ${status}">
        <div class="card-head">
          <div class="label">${label}</div>
          <span class="mini-badge ${status}">${status}</span>
        </div>
        <div class="value">${value}</div>
        <div class="sub">${sub}</div>
        <div class="sensor-hint">${sensorHint(key)}</div>
      </div>
    `;
  }).join("");
}

function setStatus(latest = {}) {
  const metrics = latest.metrics || {};
  const statuses = classifySensors(metrics);
  const computedSeverity = overallSeverity(statuses);
  const shownSeverity = latest.severity || metrics.severity || computedSeverity;
  const ts = latest.ts || latest.processedAt || "--";

  severityPill.textContent = `Severity: ${shownSeverity}`;
  triggeredPill.textContent = `Triggered by: ${triggerText(statuses)}`;
  updatedPill.textContent = `Updated: ${formatTimestamp(ts)}`;
  apiPill.textContent = `API: ${API_BASE || "not configured"}`;
}

function badge(severity) {
  const safeSeverity = severity || "NORMAL";
  return `<span class="badge ${safeSeverity}">${safeSeverity}</span>`;
}

function renderHistory(items = []) {
  rowCountEl.textContent = `${items.length} rows`;

  historyBody.innerHTML = items.map((item) => {
    const m = item.metrics || {};
    const statuses = classifySensors(m);
    const calculatedSeverity = overallSeverity(statuses);
    const rowSeverity = item.severity || m.severity || calculatedSeverity;

    return `
      <tr>
        <td>${formatTimestamp(item.ts || item.processedAt)}</td>
        <td>${badge(rowSeverity)}</td>
        <td class="trigger-text">${triggerText(statuses)}</td>
        <td>${formatNumber(m.water_level_m)}</td>
        <td>${formatNumber(m.rainfall_mm_h)}</td>
        <td>${formatNumber(m.water_temp_c)}</td>
        <td>${formatNumber(m.turbidity_ntu)}</td>
        <td>${formatNumber(m.flow_rate_m3s)}</td>
      </tr>
    `;
  }).join("");
}

function updateChart(chart, labels, data) {
  chart.data.labels = labels;
  chart.data.datasets[0].data = data;
  chart.update();
}

function updateCharts(items = []) {
  const ordered = [...items].reverse();

  const labels = ordered.map((x) => {
    const raw = x.ts || x.processedAt;
    if (!raw) return "--";
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? raw : d.toLocaleTimeString();
  });

  updateChart(
    charts.waterLevel,
    labels,
    ordered.map((x) => x.metrics?.water_level_m ?? null)
  );

  updateChart(
    charts.rainfall,
    labels,
    ordered.map((x) => x.metrics?.rainfall_mm_h ?? null)
  );

  updateChart(
    charts.temp,
    labels,
    ordered.map((x) => x.metrics?.water_temp_c ?? null)
  );

  updateChart(
    charts.turbidity,
    labels,
    ordered.map((x) => x.metrics?.turbidity_ntu ?? null)
  );

  updateChart(
    charts.flow,
    labels,
    ordered.map((x) => x.metrics?.flow_rate_m3s ?? null)
  );
}

async function loadOverview() {
  const stationId = stationInput.value.trim();

  if (!API_BASE) {
    alert("DASHBOARD_API_BASE is not configured.");
    return;
  }

  const url = `${API_BASE}/overview?stationId=${encodeURIComponent(stationId)}&limit=30`;
  const res = await fetch(url);

  if (!res.ok) {
    throw new Error(`API call failed: ${res.status}`);
  }

  const data = await res.json();
  const latest = data.latest || {};
  const history = data.history || [];

  metricCards(latest.metrics || {}, latest);
  setStatus(latest);
  renderHistory(history);
  updateCharts(history);
}

refreshBtn.addEventListener("click", () => {
  loadOverview().catch((err) => alert(err.message));
});

createCharts();
loadOverview().catch((err) => console.error(err));
setInterval(() => {
  loadOverview().catch((err) => console.error(err));
}, 10000);