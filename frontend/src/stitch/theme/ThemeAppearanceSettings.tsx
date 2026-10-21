import { CheckOutlined, DesktopOutlined } from "@ant-design/icons";
import { useAppearance, type ThemeName } from "./appearance";
import "./themeAppearanceSettings.css";

const themes: ReadonlyArray<{ id: ThemeName; label: string }> = [
  { id: "forest", label: "纸间绿" },
  { id: "ocean", label: "雾海蓝" },
  { id: "sunset", label: "暖杏" },
  { id: "dark", label: "石墨夜" },
  { id: "system", label: "跟随系统" },
];

export function ThemeAppearanceSettings({ onSelect }: { onSelect?: () => void } = {}) {
  const [theme, setTheme] = useAppearance();
  return (
    <section className="profile-appearance" aria-labelledby="appearance-settings-title">
      <div className="profile-section-heading">
        <h2 id="appearance-settings-title">页面配色</h2><p>立即生效，保存在本设备</p>
      </div>
      <div className="profile-theme-options" role="group" aria-label="界面主题">
        {themes.map((item) => {
          const selected = theme === item.id;
          return (
            <button key={item.id} type="button" aria-pressed={selected} onClick={() => { setTheme(item.id); onSelect?.(); }} className={`profile-theme-option${selected ? " is-selected" : ""}`}>
              <span className={`profile-theme-preview theme-preview-${item.id}`} aria-hidden="true">
                {item.id === "system" ? <DesktopOutlined /> : <><i className="theme-mini-nav" /><i className="theme-mini-title" /><i className="theme-mini-card" /><i className="theme-mini-line" /></>}
                {selected && <span className="profile-theme-check"><CheckOutlined /></span>}
              </span>
              <span className="profile-theme-label">{item.label}</span>
              {selected && <span className="sr-only">当前</span>}
            </button>
          );
        })}
      </div>
    </section>
  );
}
