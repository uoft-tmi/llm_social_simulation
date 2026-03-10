"use client";

import { useMemo, useState } from "react";

import { SimulationReplay } from "@/lib/replay/replayTypes";

import { Card } from "@/components/ui/Card";
import { TabItem, Tabs } from "@/components/ui/Tabs";

type Point = { x: number; y: number };

function pathFromSeries(values: number[], width: number, height: number): string {
  if (values.length === 0) return "";

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-9, max - min);

  const points: Point[] = values.map((value, idx) => ({
    x: (idx / Math.max(values.length - 1, 1)) * width,
    y: height - ((value - min) / span) * height
  }));

  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
}

function SparkLine({
  values,
  color,
  label
}: {
  values: number[];
  color: string;
  label: string;
}) {
  const width = 220;
  const height = 64;
  const d = pathFromSeries(values, width, height);
  const latest = values.at(-1) ?? 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px] text-moss-100/80">
        <span>{label}</span>
        <span className="pixel-font text-moss-50">{latest.toFixed(2)}</span>
      </div>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="rounded border border-moss-700/40 bg-slate-900/70">
        <path d={d} stroke={color} strokeWidth="2.2" fill="none" />
      </svg>
    </div>
  );
}

function WealthBars({ replay }: { replay: SimulationReplay }) {
  const lastTick = replay.ticks.at(-1);
  const rows = lastTick ? [...lastTick.agents].sort((a, b) => a.id - b.id) : [];
  const max = Math.max(1, ...rows.map((r) => r.wealth));

  return (
    <div className="space-y-1">
      {rows.map((row) => {
        const w = (row.wealth / max) * 100;
        return (
          <div key={row.id} className="space-y-0.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-moss-100/80">Agent {row.id}</span>
              <span className="pixel-font text-moss-50">{row.wealth.toFixed(1)}</span>
            </div>
            <div className="h-2 rounded bg-slate-900/70">
              <div className="h-2 rounded bg-gradient-to-r from-emerald-400 to-amber-300" style={{ width: `${w}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

const CHART_TABS: TabItem[] = [
  { id: "resource", label: "Resource" },
  { id: "pool", label: "Pool" },
  { id: "wealth", label: "Wealth" }
];

export function MiniChartsPanel({ replay }: { replay: SimulationReplay }) {
  const [tab, setTab] = useState<string>("resource");

  const series = useMemo(() => {
    const resources = replay.ticks.map((tick) => tick.world.resource);
    const pools = replay.ticks.map((tick) => tick.world.pool);
    return { resources, pools };
  }, [replay.ticks]);

  return (
    <Card
      title="Charts"
      rightSlot={<Tabs tabs={CHART_TABS} value={tab} onChange={setTab} />}
      className="space-y-2"
    >
      {tab === "resource" ? <SparkLine values={series.resources} color="#82d173" label="Resource over time" /> : null}
      {tab === "pool" ? <SparkLine values={series.pools} color="#6cc3ff" label="Pool over time" /> : null}
      {tab === "wealth" ? <WealthBars replay={replay} /> : null}
    </Card>
  );
}
