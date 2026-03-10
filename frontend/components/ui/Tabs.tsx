export type TabItem = {
  id: string;
  label: string;
};

export function Tabs({
  tabs,
  value,
  onChange
}: {
  tabs: TabItem[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="inline-flex rounded-sm border border-moss-300/40 bg-slate-900/70 p-1">
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`pixel-font rounded-sm px-2 py-1 text-[10px] uppercase transition ${
              active
                ? "bg-moss-500 text-slate-950"
                : "text-moss-200 hover:bg-moss-800/70 hover:text-moss-50"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
