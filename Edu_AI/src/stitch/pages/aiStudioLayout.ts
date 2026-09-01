export type AiStudioLayoutMode = "wide" | "compact" | "drawer";

export type AiStudioPanelState = {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
};

export type AiStudioGridOptions = AiStudioPanelState & {
  mode: AiStudioLayoutMode;
  leftPreviewOpen?: boolean;
  rightPreviewOpen?: boolean;
};

const COLLAPSED_WIDTH = "72px";
const EXPANDED_WIDTH = "clamp(320px, 24vw, 520px)";
const PREVIEW_WIDTH = "clamp(420px, 32vw, 720px)";

export function getAiStudioLayoutMode(contentWidth: number): AiStudioLayoutMode {
  if (contentWidth >= 1540) return "wide";
  if (contentWidth >= 1200) return "compact";
  return "drawer";
}

export function resolveCompactPanelState(
  state: AiStudioPanelState,
): AiStudioPanelState {
  if (!state.leftCollapsed && !state.rightCollapsed) {
    return { leftCollapsed: true, rightCollapsed: false };
  }
  return state;
}

export function getAiStudioGridTemplate(options: AiStudioGridOptions): string {
  if (options.mode === "drawer") {
    return "minmax(0, 1fr)";
  }

  const state =
    options.mode === "compact"
      ? resolveCompactPanelState(options)
      : options;

  if (options.mode === "compact") {
    const leftColumn = state.leftCollapsed
      ? COLLAPSED_WIDTH
      : "minmax(320px, 420px)";
    const rightColumn = state.rightCollapsed
      ? COLLAPSED_WIDTH
      : "minmax(320px, 420px)";
    return `${leftColumn} minmax(0, 1fr) ${rightColumn}`;
  }

  const leftColumn = state.leftCollapsed
    ? COLLAPSED_WIDTH
    : options.leftPreviewOpen
      ? PREVIEW_WIDTH
      : EXPANDED_WIDTH;
  const rightColumn = state.rightCollapsed
    ? COLLAPSED_WIDTH
    : options.rightPreviewOpen
      ? PREVIEW_WIDTH
      : EXPANDED_WIDTH;

  return `${leftColumn} minmax(0, 1fr) ${rightColumn}`;
}
