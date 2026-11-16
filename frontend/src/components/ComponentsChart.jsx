/**
 * ComponentsChart.jsx
 * Data-visualisation panel for the RiskAnalysis page.
 * Uses recharts – no external CSS dependencies.
 */
import React, { useState } from 'react';
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  RadialBarChart, RadialBar,
} from 'recharts';

/* ── colour palette aligned with RiskAnalysis.css ── */
const PALETTE = {
  clear:     '#4a7c59',
  flagged:   '#c47c2a',
  fragrance: '#8a5c00',
  allergen:  '#833333',
  neutral:   '#8b7355',
  good:      '#2d5a3d',
  warn:      '#833333',
};

const FUNCTION_COLORS = [
  '#4a7c59', '#c47c2a', '#5a7a9e', '#8a5c00', '#6b5a8e',
  '#2d5a3d', '#a0522d', '#4a6fa5', '#7c4a4a', '#4a7c7c',
];

/* ── Shared tooltip style ── */
const tooltipStyle = {
  contentStyle: { fontSize: '0.8rem', border: '1px solid #e0d9ce', borderRadius: 3 },
};

/* ─────────────────────────────────────────────────── */
/* Custom legend renderer — wraps long names cleanly  */
/* ─────────────────────────────────────────────────── */
function CustomLegend({ payload }) {
  if (!payload || !payload.length) return null;
  return (
    <ul className="chart-legend">
      {payload.map((entry) => (
        <li key={entry.value} className="chart-legend__item">
          <span className="chart-legend__dot" style={{ background: entry.color }} />
          <span className="chart-legend__label">{entry.value}</span>
        </li>
      ))}
    </ul>
  );
}

/* ─────────────────────────────────────────────────── */
/* Custom Y-axis tick — truncates long ingredient names*/
/* ─────────────────────────────────────────────────── */
const MAX_LABEL = 26; // characters before truncation
function BarYTick({ x, y, payload }) {
  const raw = payload.value || '';
  const label = raw.length > MAX_LABEL ? raw.slice(0, MAX_LABEL - 1) + '…' : raw;
  return (
    <text
      x={x}
      y={y}
      textAnchor="end"
      dominantBaseline="middle"
      fill="#3d3028"
      fontSize={10}
    >
      {label}
    </text>
  );
}

/* ─────────────────────────────────────────────────── */
/* 1. Donut – ingredient status breakdown              */
/* ─────────────────────────────────────────────────── */
function StatusDonut({ ingredients }) {
  const clear     = ingredients.filter(i => !i.is_concern && !i.is_allergen && !i.is_fragrance).length;
  const flagged   = ingredients.filter(i => i.is_concern).length;
  const fragrance = ingredients.filter(i => i.is_fragrance && !i.is_concern).length;
  const allergen  = ingredients.filter(i => i.is_allergen && !i.is_concern && !i.is_fragrance).length;

  const data = [
    { name: 'Clear',     value: clear,     fill: PALETTE.clear },
    { name: 'Flagged',   value: flagged,   fill: PALETTE.flagged },
    { name: 'Fragrance', value: fragrance, fill: PALETTE.fragrance },
    { name: 'Allergen',  value: allergen,  fill: PALETTE.allergen },
  ].filter(d => d.value > 0);

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="chart-card">
      <h3 className="chart-card__title">Ingredient Status Breakdown</h3>
      <p className="chart-card__sub">
        {total} ingredient{total !== 1 ? 's' : ''} classified by flag status
      </p>
      {/* Fixed height: 160 for chart + room for legend below */}
      <ResponsiveContainer width="100%" height={160}>
        <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={48}
            outerRadius={72}
            paddingAngle={2}
            dataKey="value"
            /* No inline labels — tooltip + legend handle it */
            label={false}
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [`${value} ingredient${value !== 1 ? 's' : ''}`, name]}
            {...tooltipStyle}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Legend rendered outside the chart so it never overlaps */}
      <CustomLegend payload={data.map(d => ({ value: d.name, color: d.fill }))} />
    </div>
  );
}

/* ─────────────────────────────────────────────────── */
/* 2. Bar – ingredient review scores                  */
/* ─────────────────────────────────────────────────── */
const BAR_HEIGHT = 34; // px per row — enough breathing room
const BAR_MARGIN = { top: 4, right: 40, left: 4, bottom: 4 };
const YAXIS_WIDTH = 190; // wide enough for truncated labels

function ScoreBar({ ingredients, getScore }) {
  const MAX_SHOWN = 15;
  const [showAll, setShowAll] = useState(false);

  const scored = ingredients
    .map(ing => ({ name: ing.name, score: getScore(ing) }))
    .sort((a, b) => a.score - b.score);

  const displayed = showAll ? scored : scored.slice(0, MAX_SHOWN);
  const chartHeight = displayed.length * BAR_HEIGHT + 24; // +24 for XAxis

  const barColor = (score) =>
    score >= 75 ? PALETTE.good : score >= 50 ? PALETTE.neutral : PALETTE.warn;

  return (
    <div className="chart-card">
      <h3 className="chart-card__title">Ingredient Review Scores</h3>
      <p className="chart-card__sub">Score out of 100 — lower scores indicate flags or limited evidence</p>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={displayed}
          layout="vertical"
          margin={BAR_MARGIN}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e8e2d9" />
          <XAxis
            type="number"
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={{ fontSize: 10, fill: '#7a7066' }}
            tickLine={false}
            axisLine={{ stroke: '#e0d9ce' }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={YAXIS_WIDTH}
            tick={<BarYTick />}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            formatter={(val) => [`${val}/100`, 'Review score']}
            {...tooltipStyle}
            cursor={{ fill: 'rgba(43,61,44,0.05)' }}
          />
          <Bar dataKey="score" radius={[0, 3, 3, 0]} isAnimationActive={false} barSize={18}>
            {displayed.map((entry) => (
              <Cell key={entry.name} fill={barColor(entry.score)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {scored.length > MAX_SHOWN && (
        <button
          className="chart-card__toggle"
          onClick={() => setShowAll(v => !v)}
        >
          {showAll ? 'Show fewer ▲' : `Show all ${scored.length} ingredients ▼`}
        </button>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────── */
/* 3. Radial – formula score gauge                    */
/* ─────────────────────────────────────────────────── */
function FormulaGauge({ score }) {
  if (score == null) return null;

  const fill  = score >= 75 ? PALETTE.good : score >= 50 ? PALETTE.neutral : PALETTE.warn;
  const data  = [{ name: 'Formula review', value: score, fill }];
  const label = score >= 75 ? 'Favourable' : score >= 50 ? 'Review details' : 'Use caution';

  return (
    <div className="chart-card chart-card--gauge">
      <h3 className="chart-card__title">Formula Review Score</h3>
      <p className="chart-card__sub">Average of all ingredient review scores</p>
      <ResponsiveContainer width="100%" height={160}>
        <RadialBarChart
          cx="50%"
          cy="90%"
          innerRadius="65%"
          outerRadius="100%"
          startAngle={180}
          endAngle={0}
          data={data}
        >
          <RadialBar
            background={{ fill: '#f0ede8' }}
            dataKey="value"
            cornerRadius={6}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="gauge-label">
        <span className="gauge-label__num" style={{ color: fill }}>{score}</span>
        <span className="gauge-label__max">/100</span>
        <span className="gauge-label__band" style={{ color: fill }}>{label}</span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────── */
/* 4. Function distribution pie — legend only, no     */
/*    inline slice labels                             */
/* ─────────────────────────────────────────────────── */
function FunctionPie({ ingredients }) {
  const counts = {};
  ingredients.forEach(ing => {
    if (ing.function) {
      const fn = ing.function.trim();
      counts[fn] = (counts[fn] || 0) + 1;
    }
  });

  const data = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, value], i) => ({ name, value, fill: FUNCTION_COLORS[i] }));

  if (data.length === 0) return null;

  return (
    <div className="chart-card">
      <h3 className="chart-card__title">Ingredient Functions</h3>
      <p className="chart-card__sub">Distribution of ingredient roles in the formula</p>
      {/* Pie only — no inline labels; legend sits below */}
      <ResponsiveContainer width="100%" height={180}>
        <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={80}
            dataKey="value"
            label={false}
            labelLine={false}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [`${value} ingredient${value !== 1 ? 's' : ''}`, name]}
            {...tooltipStyle}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Legend outside the SVG — no overlap possible */}
      <CustomLegend payload={data.map(d => ({ value: d.name, color: d.fill }))} />
    </div>
  );
}

/* ─────────────────────────────────────────────────── */
/* Main export                                        */
/* ─────────────────────────────────────────────────── */
export default function ComponentsChart({ ingredients, formulaScore, getScore }) {
  if (!ingredients || ingredients.length === 0) return null;

  return (
    <section className="components-chart-section">
      <h2 className="components-chart-section__title">Components Analysis</h2>
      <div className="components-chart-grid">
        <StatusDonut ingredients={ingredients} />
        <FormulaGauge score={formulaScore} />
        <FunctionPie ingredients={ingredients} />
        <ScoreBar ingredients={ingredients} getScore={getScore} />
      </div>
    </section>
  );
}
