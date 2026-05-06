import { cx } from "../utils";

const iconGlyphs: Record<string, string> = {
  account_circle: "◎",
  account_tree: "◇",
  arrow_back: "←",
  arrow_forward: "→",
  article: "▤",
  auto_awesome: "✦",
  auto_graph: "◈",
  campaign: "📣",
  check_circle: "✓",
  chevron_left: "‹",
  chevron_right: "›",
  close: "×",
  close_fullscreen: "⤢",
  dashboard: "▦",
  database: "●",
  description: "≡",
  download: "↓",
  edit_note: "✎",
  expand_less: "▴",
  expand_more: "▾",
  fact_check: "☑",
  folder_open: "▱",
  forum: "💬",
  fullscreen: "⛶",
  help: "?",
  hub: "●",
  last_page: "»",
  layers: "▥",
  lightbulb: "💡",
  manage_accounts: "⚙",
  menu_book: "▣",
  mic: "🎙",
  more_vert: "⋮",
  notifications: "🔔",
  pan_tool_alt: "✋",
  perm_media: "▧",
  person: "👤",
  picture_as_pdf: "PDF",
  play_arrow: "▶",
  play_circle: "▶",
  quiz: "?",
  school: "🎓",
  science: "⚗",
  search: "⌕",
  schedule: "◷",
  send: "➜",
  settings: "⚙",
  settings_suggest: "⚙",
  share: "⤴",
  skip_next: "⏭",
  slideshow: "▣",
  smart_toy: "🤖",
  star: "★",
  travel_explore: "⌕",
  upload: "↑",
  upload_file: "⇧",
  visibility: "◉",
  volume_up: "🔊",
  zoom_in: "+",
};

export function MaterialIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
  fill?: boolean;
}) {
  return (
    <span className={cx("app-icon", className)} aria-hidden="true" title={name}>
      {iconGlyphs[name] ?? "•"}
    </span>
  );
}
