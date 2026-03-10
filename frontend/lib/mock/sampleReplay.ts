import { SimulationReplay } from "@/lib/replay/replayTypes";

const AGENTS = [
  { id: 0, type: "llm", modelLabel: "GPT-4o-mini" },
  { id: 1, type: "llm", modelLabel: "Gemini Flash" },
  { id: 2, type: "rule", modelLabel: "Greedy" },
  { id: 3, type: "rule", modelLabel: "Coop" },
  { id: 4, type: "rule", modelLabel: "Adaptive" },
  { id: 5, type: "llm", modelLabel: "DeepSeek-V3" }
] as const;

function lerp(a: number, b: number, k: number) {
  return a + (b - a) * k;
}

function homePosition(id: number): { x: number; y: number } {
  const cx = 10;
  const cy = 10.5;
  const r = 4.5;
  const angle = (Math.PI * 2 * id) / AGENTS.length;
  return {
    x: cx + Math.cos(angle) * r,
    y: cy + Math.sin(angle) * r
  };
}

function behaviorTarget(
  id: number,
  tickIdx: number,
  harvest: number,
  contribute: number
): { x: number; y: number } {
  const home = homePosition(id);
  const resourceAnchor = { x: 10, y: 4.5 };
  const poolAnchor = { x: 10, y: 12 };

  const harvestBias = Math.min(1, harvest / 4);
  const contributeBias = Math.min(1, contribute / 2.2);

  const pulse = 0.3 + 0.2 * Math.sin((tickIdx + id) * 0.5);
  const towardResource = {
    x: lerp(home.x, resourceAnchor.x, 0.35 + harvestBias * 0.45),
    y: lerp(home.y, resourceAnchor.y, 0.35 + harvestBias * 0.45)
  };
  const towardPool = {
    x: lerp(home.x, poolAnchor.x, 0.35 + contributeBias * 0.5),
    y: lerp(home.y, poolAnchor.y, 0.35 + contributeBias * 0.5)
  };

  if (contribute > 0.35) {
    return {
      x: lerp(home.x, towardPool.x, 0.7 + pulse * 0.2),
      y: lerp(home.y, towardPool.y, 0.7 + pulse * 0.2)
    };
  }
  if (harvest > 0.2) {
    return {
      x: lerp(home.x, towardResource.x, 0.65 + pulse * 0.2),
      y: lerp(home.y, towardResource.y, 0.65 + pulse * 0.2)
    };
  }
  return {
    x: home.x + Math.sin((tickIdx + id) * 0.45) * 0.15,
    y: home.y + Math.cos((tickIdx + id) * 0.38) * 0.15
  };
}

export const sampleReplay: SimulationReplay = {
  meta: {
    runId: "demo-2026-03-10",
    scenario: "open-resources-baseline-demo",
    modelLabels: {
      "0": "GPT-4o-mini",
      "1": "Gemini Flash",
      "2": "Greedy",
      "3": "Coop",
      "4": "Adaptive",
      "5": "DeepSeek-V3"
    }
  },
  ticks: Array.from({ length: 72 }, (_, t) => {
    const resourceCap = 100;
    const collapseStart = 58;
    const collapse = t >= collapseStart;

    const regenWave = 8 * Math.sin(t / 7);
    const baselineDrop = t * 1.08;
    const postCollapseDrop = collapse ? (t - collapseStart) * 2.7 : 0;
    const resource = Math.max(0, Math.min(resourceCap, 92 - baselineDrop + regenWave - postCollapseDrop));

    const pool = Math.max(0, 4 + Math.sin(t / 4) * 3 + (collapse ? 2 : 8));

    const agents = AGENTS.map((agent) => {
      const phase = (t + agent.id * 2) % 12;
      const riskFactor = 1 - resource / resourceCap;
      const isGreedy = agent.modelLabel === "Greedy";
      const isCoop = agent.modelLabel === "Coop";

      const harvestRequested = Math.max(
        0,
        (isGreedy ? 3.8 : isCoop ? 1.4 : 2.4) + 0.35 * Math.sin((t + agent.id) / 2) + riskFactor * 1.2
      );
      const harvestActual = Math.max(0, harvestRequested * (resource > 5 ? 1 : resource / 5));

      const contribute = Math.max(
        0,
        (isGreedy ? 0.05 : isCoop ? 1.2 : 0.55) + (phase > 8 ? 0.22 : 0) - (collapse ? 0.2 : 0)
      );
      const reward = contribute > 0.6 ? 0.25 + 0.1 * Math.sin(t / 3) : 0;

      const wealth =
        10 +
        t * (isGreedy ? 1.9 : isCoop ? 1.25 : 1.55) +
        (collapse ? -(t - collapseStart) * 0.75 : 0) +
        agent.id * 1.8;

      const reason =
        contribute > 0.9
          ? "Contribute now to keep regeneration stable next rounds."
          : harvestActual > 2.6
            ? "Resource still viable, harvesting before expected competition spike."
            : "Small move to preserve stock while monitoring pool return.";

      const pos = behaviorTarget(agent.id, t, harvestActual, contribute);

      return {
        id: agent.id,
        type: agent.type,
        modelLabel: agent.modelLabel,
        x: pos.x,
        y: pos.y,
        wealth: Math.max(0, wealth),
        action: {
          harvestRequested,
          harvestActual,
          contribute,
          reward
        },
        reason,
        clamped: {
          harvest: harvestRequested - harvestActual > 0.35,
          contribute: contribute > Math.max(0.2 * wealth, 0)
        }
      };
    });

    const totalHarvestRequested = agents.reduce((sum, a) => sum + a.action.harvestRequested, 0);
    const totalHarvestActual = agents.reduce((sum, a) => sum + a.action.harvestActual, 0);
    const totalContribution = agents.reduce((sum, a) => sum + a.action.contribute, 0);
    const totalReward = agents.reduce((sum, a) => sum + a.action.reward, 0);

    return {
      t,
      world: {
        resource,
        resourceCap,
        pool,
        collapsed: collapse || resource <= 1
      },
      agents,
      metrics: {
        totalHarvestRequested,
        totalHarvestActual,
        totalContribution,
        totalReward
      }
    };
  })
};
