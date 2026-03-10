"use client";

import { Application } from "pixi.js";
import { useEffect, useRef, useState } from "react";

import { SimulationReplay } from "@/lib/replay/replayTypes";

import { WORLD_CONFIG, WorldScene } from "./WorldScene";

type WorldCanvasProps = {
  replay: SimulationReplay;
  tickIndex: number;
  selectedAgentId: number | null;
  onSelectAgent: (id: number) => void;
  onHoverAgent: (id: number | null) => void;
  speed: number;
};

export function WorldCanvas({
  replay,
  tickIndex,
  selectedAgentId,
  onSelectAgent,
  onHoverAgent,
  speed
}: WorldCanvasProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const appRef = useRef<Application | null>(null);
  const sceneRef = useRef<WorldScene | null>(null);
  const prevTickIndexRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const [ready, setReady] = useState(false);
  const hoveredAgentIdRef = useRef<number | null>(null);
  const selectHandlerRef = useRef(onSelectAgent);
  const hoverHandlerRef = useRef(onHoverAgent);

  useEffect(() => {
    selectHandlerRef.current = onSelectAgent;
  }, [onSelectAgent]);

  useEffect(() => {
    hoverHandlerRef.current = onHoverAgent;
  }, [onHoverAgent]);

  useEffect(() => {
    let disposed = false;
    const host = hostRef.current;
    if (!host) return;

    const app = new Application();

    const mount = async () => {
      await app.init({
        width: host.clientWidth,
        height: host.clientHeight,
        backgroundAlpha: 0,
        antialias: false,
        preference: "webgl"
      });
      if (disposed) {
        app.destroy(true);
        return;
      }

      host.appendChild(app.canvas);
      appRef.current = app;

      const scene = new WorldScene(app, {
        onSelectAgent: (id) => selectHandlerRef.current(id),
        onHoverAgent: (id) => {
          hoveredAgentIdRef.current = id;
          hoverHandlerRef.current(id);
        }
      });

      sceneRef.current = scene;
      app.stage.addChild(scene.root);
      scene.resize(host.clientWidth, host.clientHeight);
      setReady(true);

      const observer = new ResizeObserver(() => {
        if (!hostRef.current || !appRef.current || !sceneRef.current) return;
        appRef.current.renderer.resize(hostRef.current.clientWidth, hostRef.current.clientHeight);
        sceneRef.current.resize(hostRef.current.clientWidth, hostRef.current.clientHeight);
      });
      observer.observe(host);

      return () => observer.disconnect();
    };

    const cleanupPromise = mount();

    return () => {
      disposed = true;
      setReady(false);
      if (rafRef.current != null) {
        window.cancelAnimationFrame(rafRef.current);
      }
      cleanupPromise.then((cleanup) => cleanup?.());
      sceneRef.current?.destroy();
      sceneRef.current = null;
      appRef.current?.destroy(true);
      appRef.current = null;
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || replay.ticks.length === 0 || !ready) return;

    const prevTick = replay.ticks[Math.max(0, Math.min(prevTickIndexRef.current, replay.ticks.length - 1))]!;
    const nextTick = replay.ticks[Math.max(0, Math.min(tickIndex, replay.ticks.length - 1))]!;

    if (rafRef.current != null) {
      window.cancelAnimationFrame(rafRef.current);
    }

    const duration = Math.max(140, 520 / Math.max(1, speed));
    const started = performance.now();

    const renderFrame = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      scene.renderTransition(prevTick, nextTick, progress, selectedAgentId, hoveredAgentIdRef.current);
      if (progress < 1) {
        rafRef.current = window.requestAnimationFrame(renderFrame);
      }
    };

    rafRef.current = window.requestAnimationFrame(renderFrame);
    prevTickIndexRef.current = tickIndex;
  }, [tickIndex, replay.ticks, ready, selectedAgentId, speed]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || replay.ticks.length === 0 || !ready) return;

    const tick = replay.ticks[Math.max(0, Math.min(tickIndex, replay.ticks.length - 1))]!;
    scene.renderTransition(tick, tick, 1, selectedAgentId, hoveredAgentIdRef.current);
  }, [selectedAgentId, replay.ticks, tickIndex, ready]);

  return (
    <div className="panel relative h-full w-full overflow-hidden">
      <div ref={hostRef} className="h-full w-full" />
      <div className="pointer-events-none absolute left-2 top-2 rounded bg-slate-950/65 px-2 py-1 pixel-font text-[10px] text-moss-100">
        Map {WORLD_CONFIG.widthTiles}x{WORLD_CONFIG.heightTiles}
      </div>
    </div>
  );
}
