import { TickState } from "@/lib/replay/replayTypes";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-moss-700/30 py-1 text-xs">
      <span className="text-moss-100/80">{label}</span>
      <span className="pixel-font text-moss-50">{value}</span>
    </div>
  );
}

export function SimulationMetricsPanel({ tick }: { tick: TickState | null }) {
  if (!tick) {
    return <Card title="Global Metrics">No tick loaded.</Card>;
  }

  const { world, metrics } = tick;

  return (
    <Card
      title="Global Metrics"
      rightSlot={<Badge tone={world.collapsed ? "warn" : "ok"}>{world.collapsed ? "Collapsed" : "Stable"}</Badge>}
    >
      <div className="space-y-1">
        <StatRow label="Round" value={String(tick.t)} />
        <StatRow label="Resource R" value={world.resource.toFixed(2)} />
        <StatRow label="Pool P" value={world.pool.toFixed(2)} />
        <StatRow label="R / Cap" value={`${(100 * (world.resource / Math.max(world.resourceCap, 1))).toFixed(1)}%`} />
        <StatRow label="Harvest Req" value={metrics.totalHarvestRequested.toFixed(2)} />
        <StatRow label="Harvest Act" value={metrics.totalHarvestActual.toFixed(2)} />
        <StatRow label="Contribution" value={metrics.totalContribution.toFixed(2)} />
        <StatRow label="Reward" value={metrics.totalReward.toFixed(2)} />
      </div>
    </Card>
  );
}
