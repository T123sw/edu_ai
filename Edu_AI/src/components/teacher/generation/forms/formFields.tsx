import type { ReactNode } from "react";

export function GenerationField({ label, required, error, children }: { label: string; required?: boolean; error?: string; children: ReactNode }) {
  return <label className={`generation-field${error ? " has-error" : ""}`}><span>{label}{required ? " *" : ""}</span>{children}{error ? <small role="alert">{error}</small> : null}</label>;
}

export function lines(value: string) {
  return value.split(/\r?\n/u).map((item) => item.trim()).filter(Boolean);
}
