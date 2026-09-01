import { MaterialIcon, cx, useAppShell, type ThemeName } from "../shared";

const themes: ReadonlyArray<{
  id: ThemeName;
  label: string;
  preview: string;
  note: string;
}> = [
  { id: "ocean", label: "海蓝", preview: "from-[#0b5bd3] to-[#8ec5ff]", note: "清晰明快的默认教学风格" },
  { id: "forest", label: "森绿", preview: "from-[#1d6b3f] to-[#9dd8b7]", note: "柔和舒展，适合长时间阅读" },
  { id: "sunset", label: "日落", preview: "from-[#b85a2b] to-[#f6c28b]", note: "温暖醒目，适合内容展示" },
  { id: "dark", label: "暗色", preview: "from-[#0f172a] to-[#475569]", note: "降低眩光，适合低光环境" },
];

export function ThemeAppearanceSettings() {
  const { theme, setTheme } = useAppShell();

  return (
    <section
      className="mt-6 rounded-[30px] border border-(--shell-border) bg-white/92 p-6 shadow-[0_16px_40px_var(--panel-shadow)] sm:p-7"
      aria-labelledby="appearance-settings-title"
    >
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-(--accent-soft) text-(--accent)" aria-hidden="true">
          <MaterialIcon name="palette" className="text-xl" />
        </span>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-(--muted-text)">Appearance</p>
          <h2 id="appearance-settings-title" className="mt-1 text-2xl font-black text-(--accent-strong)">外观设置</h2>
          <p className="mt-1 text-sm leading-6 text-(--muted-text)">选择适合当前环境的界面色调，设置会保存在本设备。</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" role="group" aria-label="界面主题">
        {themes.map((item) => {
          const selected = theme === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected}
              onClick={() => setTheme(item.id)}
              className={cx(
                "cursor-pointer rounded-[20px] border p-4 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2",
                selected
                  ? "border-(--accent-border) bg-(--accent-soft)"
                  : "border-(--shell-border) bg-(--surface-subtle) hover:border-(--accent-border) hover:bg-white",
              )}
            >
              <span className="flex items-start gap-3">
                <span className={`h-10 w-10 shrink-0 rounded-[14px] bg-linear-to-br ${item.preview}`} aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-bold text-(--app-text)">{item.label}</span>
                    {selected ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 text-[10px] font-bold text-(--accent-strong)">
                        <MaterialIcon name="check_circle" className="text-xs" />
                        <span>当前</span>
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-(--muted-text)">{item.note}</span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
