import type { GameConfig } from "../definitions/game";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

const games: Array<[GameConfig["gameType"], string, string]> = [["category_sort", "分类挑战", "把卡片放入正确类别"], ["drag_match", "拖拽配对", "匹配概念与解释"], ["memory_flip", "记忆翻牌", "通过翻牌寻找配对"]];

export function GameForm({ value, onChange, errors = {} }: GenerationFormProps<GameConfig>) {
  const patch = (next: Partial<GameConfig>) => onChange({ ...value, ...next });
  const selected = games.find(([type]) => type === value.gameType) || games[0];
  return <div className="generation-factory__form" data-resource-form="game">
    <fieldset><legend>游戏类型</legend><div className="generation-type-buttons">{games.map(([type, label, description]) => <button type="button" key={type} aria-pressed={value.gameType === type} onClick={() => patch({ gameType: type })}><strong>{label}</strong><small>{description}</small></button>)}</div></fieldset>
    <GenerationField label="游戏主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} /></GenerationField>
    <GenerationField label="卡片 / 题目数量" required error={errors.cardCount}><input type="number" min={4} max={30} value={value.cardCount} onChange={(event) => patch({ cardCount: Number(event.target.value) })} /></GenerationField>
    <details><summary>更多设置</summary><GenerationField label="难度"><select value={value.difficulty} onChange={(event) => patch({ difficulty: event.target.value as GameConfig["difficulty"] })}><option value="easy">基础</option><option value="medium">中等</option><option value="hard">挑战</option></select></GenerationField><GenerationField label="课堂用时（分钟）" error={errors.durationMinutes}><input type="number" min={1} max={60} value={value.durationMinutes} onChange={(event) => patch({ durationMinutes: Number(event.target.value) })} /></GenerationField></details>
    <section className="generation-mini-preview" aria-label="游戏配置预览"><strong>{selected[1]}</strong><span>{value.cardCount} 张卡片 · {value.durationMinutes} 分钟 · {value.difficulty === "hard" ? "挑战" : value.difficulty === "easy" ? "基础" : "中等"}</span></section>
  </div>;
}
