type BadgeTone = "neutral" | "ok" | "warn" | "accent";

const toneClass: Record<BadgeTone, string> = {
  neutral: "bg-slate-700/70 text-slate-100 border-slate-500/60",
  ok: "bg-emerald-700/50 text-emerald-100 border-emerald-400/70",
  warn: "bg-rose-700/50 text-rose-100 border-rose-300/70",
  accent: "bg-amber-600/40 text-amber-100 border-amber-300/70"
};

export function Badge({
  children,
  tone = "neutral"
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
}) {
  return (
    <span className={`inline-flex rounded-sm border px-2 py-0.5 text-[10px] font-semibold ${toneClass[tone]}`}>
      {children}
    </span>
  );
}
