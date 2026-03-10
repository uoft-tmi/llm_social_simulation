"use client";

import { useEffect, useMemo, useState } from "react";

import { WorldCanvas } from "@/components/pixi/WorldCanvas";
import { loadReplay } from "@/lib/replay/replaySource";
import { SimulationReplay } from "@/lib/replay/replayTypes";
import { useReplayController } from "@/lib/replay/useReplayController";

import { AgentInspector } from "./AgentInspector";
import { CollapseBanner } from "./CollapseBanner";
import { MiniChartsPanel } from "./MiniChartsPanel";
import { SimulationMetricsPanel } from "./SimulationMetricsPanel";
import { SimulationToolbar } from "./SimulationToolbar";

export function SimulationShell() {
  const [replay, setReplay] = useState<SimulationReplay | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [hoveredAgentId, setHoveredAgentId] = useState<number | null>(null);

  useEffect(() => {
    loadReplay({ mode: "mock" }).then(setReplay);
  }, []);

  const fallbackReplay = useMemo<SimulationReplay>(
    () => ({
      meta: { runId: "loading", scenario: "loading", modelLabels: {} },
      ticks: []
    }),
    []
  );
  const resolvedReplay = replay ?? fallbackReplay;

  const replayController = useReplayController(resolvedReplay, 1);
  const currentTick = replayController.currentTick;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-3 p-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="pixel-font text-sm uppercase tracking-widest text-moss-100">
            Open Resources Simulation Viewer
          </h1>
          <p className="text-xs text-moss-100/70">
            Run {resolvedReplay.meta.runId} · {resolvedReplay.meta.scenario}
          </p>
        </div>
      </header>

      <SimulationToolbar
        roundLabel={`Tick ${replayController.currentTickIndex + 1}/${replayController.tickCount}`}
        isPlaying={replayController.isPlaying}
        speed={replayController.speed}
        speedOptions={replayController.speedOptions}
        onTogglePlay={replayController.togglePlay}
        onStepForward={replayController.stepForward}
        onStepBack={replayController.stepBack}
        onReset={() => {
          replayController.reset();
          setSelectedAgentId(null);
        }}
        onSpeedChange={replayController.setSpeed}
      />

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-[240px_minmax(600px,1fr)_340px]">
        <aside className="panel hidden p-3 lg:block">
          <h2 className="pixel-font mb-3 text-xs uppercase text-moss-200">Preset Notes</h2>
          <ul className="space-y-2 text-xs text-moss-50/80">
            <li>Map: top resource zone + lower town hall.</li>
            <li>Agents move toward resource for harvest and town hall for contribution.</li>
            <li>Collapse introduces desaturation and warning banner.</li>
            <li>Replay source is local JSON mock data in <code>lib/mock/sampleReplay.json</code>.</li>
          </ul>
        </aside>

        <section className="flex min-h-[620px] flex-col gap-3">
          <CollapseBanner tick={currentTick} />
          <div className="h-[620px]">
            <WorldCanvas
              replay={resolvedReplay}
              tickIndex={replayController.currentTickIndex}
              selectedAgentId={selectedAgentId}
              onSelectAgent={setSelectedAgentId}
              onHoverAgent={setHoveredAgentId}
              speed={replayController.speed}
            />
          </div>
        </section>

        <aside className="subtle-scrollbar flex max-h-[calc(100vh-180px)] flex-col gap-3 overflow-y-auto pr-1">
          <SimulationMetricsPanel tick={currentTick} />
          <AgentInspector tick={currentTick} selectedAgentId={selectedAgentId} hoveredAgentId={hoveredAgentId} />
          <MiniChartsPanel replay={resolvedReplay} />
        </aside>
      </div>
    </main>
  );
}
