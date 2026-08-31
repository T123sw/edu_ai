import type { CourseKnowledgeBuildConfig } from "../../api/types";
import {
  applyCourseKnowledgePreset,
  estimateCourseKnowledgeBuild,
  validateCourseKnowledgeConfig,
} from "./courseKnowledgeBuildState";

type Props = {
  config: CourseKnowledgeBuildConfig;
  saving: boolean;
  onChange: (config: CourseKnowledgeBuildConfig) => void;
  onContinue: () => void;
};

const PRESET_COPY = {
  small: ["小型", "约 3 个模块 · 9 个知识点"],
  standard: ["标准", "约 4 个模块 · 16 个知识点"],
  large: ["大型", "约 6 个模块 · 36 个知识点"],
} as const;

export function CourseKnowledgeBuildConfigStep({ config, saving, onChange, onContinue }: Props) {
  const estimate = estimateCourseKnowledgeBuild(config);
  const errors = validateCourseKnowledgeConfig(config);

  function updateNumber(field: keyof CourseKnowledgeBuildConfig, value: string) {
    onChange({ ...config, preset: "custom", [field]: Number(value) });
  }

  return (
    <section className="course-kb-wizard__step" aria-labelledby="kb-config-title">
      <div className="course-kb-wizard__step-heading">
        <div><span>步骤 1 / 3</span><h3 id="kb-config-title">配置构建规模</h3></div>
        <p>默认配置可以直接使用，所有规模参数都可以手工调整。</p>
      </div>

      <div className="course-kb-wizard__presets" role="radiogroup" aria-label="构建规模预设">
        {(Object.keys(PRESET_COPY) as Array<keyof typeof PRESET_COPY>).map((preset) => (
          <button
            key={preset}
            type="button"
            role="radio"
            aria-checked={config.preset === preset}
            className={config.preset === preset ? "is-selected" : ""}
            onClick={() => onChange(applyCourseKnowledgePreset(config, preset))}
          >
            <strong>{PRESET_COPY[preset][0]}{preset === "standard" ? " · 默认" : ""}</strong>
            <span>{PRESET_COPY[preset][1]}</span>
          </button>
        ))}
      </div>

      <div className="course-kb-wizard__fields">
        <label>图谱深度<input type="number" min={3} max={5} value={config.graph_depth} onChange={(event) => updateNumber("graph_depth", event.target.value)} /></label>
        <label>模块数量<input type="number" min={1} max={12} value={config.target_module_count} onChange={(event) => updateNumber("target_module_count", event.target.value)} /></label>
        <label>每模块知识点<input type="number" min={2} max={20} value={config.target_points_per_module} onChange={(event) => updateNumber("target_points_per_module", event.target.value)} /></label>
        <label>每知识点有效覆盖目标<input type="number" min={1} max={10} value={config.target_materials_per_leaf} onChange={(event) => updateNumber("target_materials_per_leaf", event.target.value)} /></label>
        <label>外部非 AI 来源下限<input type="number" min={0} max={10} value={config.minimum_web_materials_per_leaf} onChange={(event) => updateNumber("minimum_web_materials_per_leaf", event.target.value)} /></label>
        <label>每知识点 AI 补充上限<input type="number" min={0} max={10} disabled={!config.ai_supplement_enabled} value={config.maximum_ai_materials_per_leaf} onChange={(event) => updateNumber("maximum_ai_materials_per_leaf", event.target.value)} /></label>
        <label>每知识点搜索候选上限<input type="number" min={1} max={20} value={config.max_search_results_per_leaf} onChange={(event) => updateNumber("max_search_results_per_leaf", event.target.value)} /></label>
        <label>在线教材上限<input type="number" min={0} max={5} disabled={!config.prefer_complete_textbooks} value={config.max_online_textbooks} onChange={(event) => updateNumber("max_online_textbooks", event.target.value)} /></label>
        <label>内容语言<input type="text" value={config.content_language} onChange={(event) => onChange({ ...config, preset: "custom", content_language: event.target.value })} /></label>
        <label className="course-kb-wizard__checkbox"><input type="checkbox" checked={config.ai_supplement_enabled} onChange={(event) => onChange({ ...config, ai_supplement_enabled: event.target.checked, maximum_ai_materials_per_leaf: event.target.checked ? Math.max(1, config.maximum_ai_materials_per_leaf) : 0 })} />允许 AI 补充网络和教材未覆盖的缺口</label>
        <label className="course-kb-wizard__checkbox"><input type="checkbox" checked={config.prefer_complete_textbooks} onChange={(event) => onChange({ ...config, prefer_complete_textbooks: event.target.checked })} />优先查找并解析完整教材（含 PDF）</label>
      </div>

      <div className="course-kb-wizard__strategy-note">
        <strong>增量追加</strong>
        <span>保留现有知识结构，只补充新节点与资料。</span>
      </div>
      <details className="course-kb-wizard__advanced">
        <summary>高级设置</summary>
        <label>
          更新方式
          <select
            value={config.update_strategy}
            onChange={(event) => {
              const strategy = event.target.value as CourseKnowledgeBuildConfig["update_strategy"];
              if (
                strategy === "full_rebuild"
                && !window.confirm("完全重建会用新结构替换当前知识图谱，但历史版本仍可恢复。确认继续吗？")
              ) return;
              onChange({ ...config, update_strategy: strategy });
            }}
          >
            <option value="incremental">增量追加（推荐）</option>
            <option value="merge_rebuild">合并重建</option>
            <option value="full_rebuild">完全重建</option>
          </select>
        </label>
      </details>

      <div className="course-kb-wizard__estimate">
        <span>预计 <strong>{estimate.leafCount}</strong> 个叶子知识点</span>
        <span>预计 <strong>{estimate.materialCount}</strong> 份学习资料</span>
      </div>
      {errors.length ? <ul className="course-kb-wizard__validation" role="alert">{errors.map((error) => <li key={error}>{error}</li>)}</ul> : null}
      <div className="course-kb-wizard__footer"><button type="button" className="course-kb-wizard__primary" disabled={saving || errors.length > 0} onClick={onContinue}>{saving ? "正在保存…" : "保存并选择教材"}</button></div>
    </section>
  );
}
