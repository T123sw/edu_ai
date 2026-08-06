import type { PropsWithChildren, ReactNode } from "react";

export function GenerationConfigShell({ title, description, step, footer, children }: PropsWithChildren<{
  title: string; description: string; step: number; footer: ReactNode;
}>) {
  return (
    <section className="generation-config-shell" aria-label={title}>
      <header><span>步骤 {step} / 4</span><h2>{title}</h2><p>{description}</p></header>
      <div className="generation-config-shell__body">{children}</div>
      <footer>{footer}</footer>
    </section>
  );
}
