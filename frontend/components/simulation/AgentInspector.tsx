import { AgentState, TickState } from "@/lib/replay/replayTypes";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

function findAgent(tick: TickState | null, id: number | null): AgentState | null {
  if (!tick || id == null) return null;
  return tick.agents.find((agent) => agent.id === id) ?? null;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-0.5 text-xs">
      <span className="text-moss-100/75">{label}</span>
      <span className="pixel-font text-moss-50">{value}</span>
    </div>
  );
}

export function AgentInspector({
  tick,
  selectedAgentId,
  hoveredAgentId
}: {
  tick: TickState | null;
  selectedAgentId: number | null;
  hoveredAgentId: number | null;
}) {
  const chosenId = selectedAgentId ?? hoveredAgentId;
  const agent = findAgent(tick, chosenId);

  return (
    <Card
      title="Agent Inspector"
      rightSlot={agent ? <Badge tone="accent">ID {agent.id}</Badge> : <Badge tone="neutral">No selection</Badge>}
    >
      {!agent ? (
        <p className="text-xs text-moss-100/70">Click an agent sprite in the world to inspect actions and reasoning.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge tone="neutral">{agent.type}</Badge>
            {agent.modelLabel ? <Badge tone="ok">{agent.modelLabel}</Badge> : null}
            {agent.clamped?.harvest || agent.clamped?.contribute ? <Badge tone="warn">Clamp</Badge> : null}
          </div>

          <div className="space-y-1 border-b border-moss-700/30 pb-2">
            <Row label="Wealth" value={agent.wealth.toFixed(2)} />
            <Row label="Harvest req" value={agent.action.harvestRequested.toFixed(2)} />
            <Row label="Harvest act" value={agent.action.harvestActual.toFixed(2)} />
            <Row label="Contribution" value={agent.action.contribute.toFixed(2)} />
            <Row label="Reward" value={agent.action.reward.toFixed(2)} />
            <Row label="Clamp harvest" value={String(Boolean(agent.clamped?.harvest))} />
            <Row label="Clamp contribute" value={String(Boolean(agent.clamped?.contribute))} />
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-moss-200">Last reason</div>
            <p className="rounded border border-moss-700/50 bg-slate-900/55 p-2 text-xs leading-relaxed text-moss-50/90">
              {agent.reason ?? "No reason text available."}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
