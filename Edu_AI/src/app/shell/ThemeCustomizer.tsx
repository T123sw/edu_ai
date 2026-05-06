import { useState } from "react";
import { useAppShell } from "../providers";
import type { ThemeName } from "../routing";
import { MaterialIcon } from "../../shared/ui";
import { cx } from "../../shared/utils";

export function ThemeCustomizer() {
  const { theme, setTheme } = useAppShell();
  const [open, setOpen] = useState(false);
  const themes: Array<{ id: ThemeName; label: string; preview: string; note: string }> = [
    { id: "ocean", label: "海蓝", preview: "from-[#0b5bd3] to-[#8ec5ff]", note: "默认教学风格" },
    { id: "forest", label: "森绿", preview: "from-[#1d6b3f] to-[#9dd8b7]", note: "适合长时间阅读" },
    { id: "sunset", label: "日落", preview: "from-[#b85a2b] to-[#f6c28b]", note: "更暖的展示氛围" },
    { id: "dark", label: "暗色", preview: "from-[#0f172a] to-[#475569]", note: "降低眩光" },
  ];

  return (
    <div className="fixed bottom-5 right-5 z-[120]">
      {open ? (
        <div className="w-72 rounded-[24px] border border-[#bfdbfe] bg-gradient-to-br from-[#f8fbff] via-[#eef6ff] to-[#e0f2fe] p-4 shadow-[0_24px_60px_rgba(37,99,235,0.22)] backdrop-blur-xl">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-bold text-[#1d4ed8]">个人账号设置</div>
              <div className="text-xs text-[#64748b]">修改界面色调与显示偏好</div>
            </div>
            <button
              className="flex h-8 w-8 items-center justify-center rounded-full border border-[#bfdbfe] bg-white/70 text-[#64748b] transition hover:border-[#60a5fa] hover:bg-[#dbeafe] hover:text-[#1d4ed8]"
              onClick={() => setOpen(false)}
              type="button"
            >
              <MaterialIcon name="close" className="text-base" />
            </button>
          </div>
          <div className="space-y-2">
            {themes.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTheme(item.id)}
                className={cx(
                  "flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition duration-200",
                  theme === item.id
                    ? "border-[#60a5fa] bg-white shadow-[0_10px_24px_rgba(59,130,246,0.18)]"
                    : "border-[#dbeafe] bg-white/65 hover:border-[#93c5fd] hover:bg-white/90",
                )}
              >
                <span className={`h-9 w-9 rounded-full bg-gradient-to-br ${item.preview}`} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-[#0f172a]">{item.label}</span>
                  <span className="block text-xs text-[#64748b]">{item.note}</span>
                </span>
                {theme === item.id ? (
                  <span className="rounded-full bg-[#dbeafe] px-2 py-1 text-[10px] font-semibold text-[#1d4ed8]">
                    当前
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="ml-auto mt-3 flex h-12 w-12 items-center justify-center rounded-full border border-[#93c5fd] bg-gradient-to-br from-[#2563eb] to-[#0ea5e9] text-white shadow-[0_18px_36px_rgba(37,99,235,0.35)] transition hover:from-[#1d4ed8] hover:to-[#0284c7]"
      >
        <MaterialIcon name="manage_accounts" className="text-xl" />
      </button>
    </div>
  );
}
