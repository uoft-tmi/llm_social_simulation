import { PropsWithChildren } from "react";

type CardProps = PropsWithChildren<{
  title?: string;
  rightSlot?: React.ReactNode;
  className?: string;
}>;

export function Card({ title, rightSlot, className = "", children }: CardProps) {
  return (
    <section className={`panel p-3 ${className}`.trim()}>
      {(title || rightSlot) && (
        <div className="mb-2 flex items-center justify-between">
          {title ? <h3 className="pixel-font text-xs uppercase tracking-wider text-moss-200">{title}</h3> : <span />}
          {rightSlot}
        </div>
      )}
      {children}
    </section>
  );
}
