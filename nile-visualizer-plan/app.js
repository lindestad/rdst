const lensData = {
  flow: {
    metrics: [
      {
        label: "Core signal",
        value: "Daily throughflow",
        copy: "Animate water movement by edge thickness, node fill rate, and downstream arrival."
      },
      {
        label: "Decision moment",
        value: "Release timing",
        copy: "Reservoir controls should visibly reshape the pulse seen at Khartoum, Aswan, and the Delta."
      }
    ]
  },
  loss: {
    metrics: [
      {
        label: "Core signal",
        value: "Cumulative loss",
        copy: "Edges shift to warm colors and label both configured loss fraction and absolute water lost."
      },
      {
        label: "Decision moment",
        value: "Loss hot spots",
        copy: "Operators should immediately see where a policy is sending scarce water through expensive routes."
      }
    ]
  },
  food: {
    metrics: [
      {
        label: "Core signal",
        value: "Crop output",
        copy: "Translate irrigation delivery into food produced so agriculture is not hidden behind raw flow numbers."
      },
      {
        label: "Decision moment",
        value: "Regional sensitivity",
        copy: "Highlight which irrigation nodes lose the most output when releases are tightened upstream."
      }
    ]
  },
  power: {
    metrics: [
      {
        label: "Core signal",
        value: "MWh generated",
        copy: "Reservoir nodes should glow with turbine utilization, minimum energy thresholds, and missed targets."
      },
      {
        label: "Decision moment",
        value: "Power-water tradeoff",
        copy: "Make it obvious when extra hydropower comes at the cost of lower storage or downstream deliveries."
      }
    ]
  },
  drinking: {
    metrics: [
      {
        label: "Core signal",
        value: "Reliability",
        copy: "Show minimum delivery attainment for Khartoum, Aswan, and the Nile Delta with alert states."
      },
      {
        label: "Decision moment",
        value: "Service risk",
        copy: "Surface shortfall streaks so drinking water failures stand out before aggregate charts bury them."
      }
    ]
  }
};

const nodeData = {
  white_nile_headwaters: {
    title: "White Nile Headwaters",
    summary: "Source nodes should communicate raw water availability and seasonal shape before control infrastructure changes it.",
    stats: [
      ["Monthly inflow", "280 / 255 / 235"],
      ["Node role", "Source"],
      ["Loss exposure", "2% to Khartoum"],
      ["Primary need", "Clean seasonality read"]
    ]
  },
  blue_nile_headwaters: {
    title: "Blue Nile Headwaters",
    summary: "This node is the upstream feeder to GERD, so it should visually anchor incoming volume before storage and power conversion.",
    stats: [
      ["Monthly inflow", "220 / 260 / 210"],
      ["Node role", "Source"],
      ["Loss exposure", "1% to GERD"],
      ["Primary need", "Inflow pulse visibility"]
    ]
  },
  gerd: {
    title: "GERD",
    summary: "Reservoir nodes should show storage, target release, turbine limits, and how release policy changes both downstream reliability and energy output.",
    stats: [
      ["Storage", "500 / 950"],
      ["Min storage", "250"],
      ["Target release", "230 / 240 / 220"],
      ["Energy factor", "0.68 per unit"]
    ]
  },
  khartoum: {
    title: "Khartoum Confluence",
    summary: "Confluence nodes need a split view: incoming tributary mix on one side, drinking and irrigation delivery performance on the other.",
    stats: [
      ["Local inflow", "20"],
      ["Drinking target", "25"],
      ["Irrigation target", "55"],
      ["Food per water", "2.1"]
    ]
  },
  aswan: {
    title: "High Aswan",
    summary: "Aswan should expose the tension between storage preservation, hydropower output, and steady downstream service to the Delta.",
    stats: [
      ["Storage", "900 / 1600"],
      ["Min storage", "500"],
      ["Target release", "330 / 315 / 300"],
      ["Energy factor", "0.59 per unit"]
    ]
  },
  nile_delta: {
    title: "Nile Delta",
    summary: "Demand nodes should make end-user consequences explicit: drinking water attainment, irrigation coverage, and food production outcomes.",
    stats: [
      ["Drinking target", "48"],
      ["Irrigation target", "120"],
      ["Food per water", "1.8"],
      ["Upstream loss", "3% from Aswan"]
    ]
  }
};

const edgeClassByLens = {
  flow: "edge-flow-mode",
  loss: "edge-loss-mode",
  food: "edge-food-mode",
  power: "edge-power-mode",
  drinking: "edge-drink-mode"
};

const lensButtons = Array.from(document.querySelectorAll(".lens"));
const metricStack = document.querySelector("#metric-stack");
const detailPanel = document.querySelector("#detail-panel");
const detailGrid = document.querySelector("#detail-grid");
const nodeElements = Array.from(document.querySelectorAll(".node"));
const networkStage = document.querySelector(".network-stage");

function renderMetrics(lens) {
  const cards = lensData[lens].metrics.map((metric) => {
    return `
      <article class="metric-card">
        <p class="card-kicker">${metric.label}</p>
        <strong>${metric.value}</strong>
        <p>${metric.copy}</p>
      </article>
    `;
  }).join("");

  metricStack.innerHTML = cards;
}

function renderNode(nodeId) {
  const node = nodeData[nodeId];
  detailPanel.querySelector("h3").textContent = node.title;
  detailPanel.querySelector(".detail-summary").textContent = node.summary;
  detailGrid.innerHTML = node.stats.map(([label, value]) => {
    return `
      <div class="detail-stat">
        <span>${label}</span>
        <strong>${value}</strong>
      </div>
    `;
  }).join("");
}

function setLens(nextLens) {
  lensButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.lens === nextLens);
  });

  Object.values(edgeClassByLens).forEach((className) => {
    networkStage.classList.remove(className);
  });

  networkStage.classList.add(edgeClassByLens[nextLens]);
  renderMetrics(nextLens);
}

lensButtons.forEach((button) => {
  button.addEventListener("click", () => setLens(button.dataset.lens));
});

nodeElements.forEach((node) => {
  node.addEventListener("click", () => {
    nodeElements.forEach((item) => item.classList.remove("active"));
    node.classList.add("active");
    renderNode(node.dataset.node);
  });
});

setLens("flow");
const defaultNode = document.querySelector('[data-node="gerd"]');
defaultNode.classList.add("active");
renderNode("gerd");
