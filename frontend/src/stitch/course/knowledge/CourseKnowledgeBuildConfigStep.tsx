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
  small: ["少量补充", "约 3 个模块 · 9 个知识点"],
  standard: ["适量补充", "约 4 个模块 · 16 个知识点"],
  large: ["丰富内容", "约 6 个模块 · 36 个知识点"],
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
        <div><h3 id="kb-config-title">选择内容规模</h3></div>
        <p>不确定选哪种？使用推荐方案即可。</p>
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
            <strong>{PRESET_COPY[preset][0]}{preset === "standard" ? " · 推荐" : ""}</strong>
            <span>{PRESET_COPY[preset][1]}</span>
          </button>
        ))}
      </div>


      <p className="course-kb-wizard__strategy-note">{config.update_strategy === "incremental" ? "保留现有目录，补充知识点和学习资料。" : config.update_strategy === "merge_rebuild" ? "结合现有目录，重新整理知识点和学习资料。" : "重新生成课程目录，历史版本可恢复。"}</p>
      <details className="course-kb-wizard__advanced">
        <summary>更多设置</summary>
      <div className="course-kb-wizard__fields">
        <label>目录层级<input type="number" min={3} max={5} value={config.graph_depth} onChange={(event) => updateNumber("graph_depth", event.target.value)} /></label>
        <label>模块数量<input type="number" min={1} max={12} value={config.target_module_count} onChange={(event) => updateNumber("target_module_count", event.target.value)} /></label>
        <label>每模块知识点<input type="number" min={2} max={20} value={config.target_points_per_module} onChange={(event) => updateNumber("target_points_per_module", event.target.value)} /></label>
        <label>每个知识点的资料数量<input type="number" min={1} max={10} value={config.target_materials_per_leaf} onChange={(event) => updateNumber("target_materials_per_leaf", event.target.value)} /></label>
        <label>每个知识点至少参考的外部资料数<input type="number" min={0} max={10} value={config.minimum_web_materials_per_leaf} onChange={(event) => updateNumber("minimum_web_materials_per_leaf", event.target.value)} /></label>
        <label>每个知识点最多生成的 AI 资料数<input type="number" min={0} max={10} disabled={!config.ai_supplement_enabled} value={config.maximum_ai_materials_per_leaf} onChange={(event) => updateNumber("maximum_ai_materials_per_leaf", event.target.value)} /></label>
        <label>每个知识点最多查找的资料数<input type="number" min={1} max={20} value={config.max_search_results_per_leaf} onChange={(event) => updateNumber("max_search_results_per_leaf", event.target.value)} /></label>
        <label>最多查找的在线教材数<input type="number" min={0} max={5} disabled={!config.prefer_complete_textbooks} value={config.max_online_textbooks} onChange={(event) => updateNumber("max_online_textbooks", event.target.value)} /></label>
        <label>内容语言<input type="text" value={config.content_language} onChange={(event) => onChange({ ...config, preset: "custom", content_language: event.target.value })} /></label>
        <label className="course-kb-wizard__checkbox"><input type="checkbox" checked={config.ai_supplement_enabled} onChange={(event) => onChange({ ...config, ai_supplement_enabled: event.target.checked, maximum_ai_materials_per_leaf: event.target.checked ? Math.max(1, config.maximum_ai_materials_per_leaf) : 0 })} />资料不足时允许 AI 补充</label>
        <label className="course-kb-wizard__checkbox"><input type="checkbox" checked={config.prefer_complete_textbooks} onChange={(event) => onChange({ ...config, prefer_complete_textbooks: event.target.checked })} />优先参考完整教材</label>
      </div>

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
            <option value="incremental">保留目录并补充（推荐）</option>
            <option value="merge_rebuild">合并整理目录</option>
            <option value="full_rebuild">重新生成目录</option>
          </select>
        </label>
      </details>

      <div className="course-kb-wizard__estimate">
        <span>预计 <strong>{estimate.leafCount}</strong> 个知识点</span>
        <span>预计 <strong>{estimate.materialCount}</strong> 份学习资料</span>
      </div>
      {errors.length ? <ul className="course-kb-wizard__validation" role="alert">{errors.map((error) => <li key={error}>{error}</li>)}</ul> : null}
      <div className="course-kb-wizard__footer"><button type="button" className="course-kb-wizard__primary" disabled={saving || errors.length > 0} onClick={onContinue}>{saving ? "正在保存…" : "下一步：添加教材"}</button></div>
    </section>
  );
}
