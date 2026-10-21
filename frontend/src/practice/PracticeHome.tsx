import { useEffect, useState } from 'react';
import { Home } from '../selfLearning/Home';
import type { usePracticeHome } from './usePracticeHome';
import { usePblHome } from '../pbl/usePblHome';
import { PracticeModeSelect, type PracticeMode } from './PracticeModeSelect';
import { PracticeResourceSection } from './PracticeResourceSection';
import './practiceHome.css';
import { TrackedPracticeGeneration } from './PracticeGenerationProgress';

export function PracticeHome({ state, initialMode = 'simulation' }: { state: ReturnType<typeof usePracticeHome>; initialMode?: PracticeMode }) {
  const [mode, setMode] = useState<PracticeMode>(initialMode);
  const projects = usePblHome();
  const [generation, setGeneration] = useState<{ key: string; mode: PracticeMode; goal: string; id?: string }>();
  useEffect(() => { setMode(initialMode); }, [initialMode]);
  const code = mode === 'code';
  const submitting = state.submitting || projects.submitting;
  const create = async (text: string) => {
    if (submitting || !text.trim()) return;
    const selection = { key: crypto.randomUUID(), mode, goal: text.trim() };
    setGeneration(selection);
    const id = await (code ? projects.create(text) : state.create(text));
    setGeneration(previous => previous?.key === selection.key ? { ...previous, id } : previous);
  };
  const open = (id: string, selectedMode: PracticeMode) => {
    const item = selectedMode === 'code' ? projects.items.find(item => item.exerciseId === id) : state.items.find(item => item.id === id);
    if (item && !['succeeded', 'ready'].includes(item.status)) {
      setGeneration({ key: crypto.randomUUID(), mode: selectedMode, goal: item.topic, id });
    } else location.hash = `/practice/${selectedMode === 'code' ? 'code/' : ''}${encodeURIComponent(id)}`;
  };
  return <><Home live mode="practice" promptValue={state.prompt} onPromptChange={state.setPrompt}
    onCreate={text => void create(text)} submitting={submitting}
    createLabel={code ? '生成项目' : '生成互动实验'}
    promptPlaceholder={code ? '描述你想完成的网页项目、需要的功能，以及希望练习的知识' : undefined}
    preparationOptions={<div className="sl-module-options"><PracticeModeSelect value={mode} onChange={setMode} /></div>}
    feedback={code ? projects.error && <p className="sl-module-feedback" role="alert">{projects.error}</p> : state.submitFailed && <p className="sl-module-feedback" role="alert">暂时无法提交，请稍后重试。</p>}
    resourceContent={<div className="sl-practice-resources">
      <PracticeResourceSection kind="实验" items={state.items} loading={state.loading} loadFailed={state.loadFailed} onRefresh={() => void state.refresh()} onOpen={id => open(id, 'simulation')} />
      <PracticeResourceSection kind="项目" items={projects.items.map(item => ({ id: item.exerciseId, topic: item.topic, status: item.status }))} loading={projects.loading} loadFailed={projects.loadFailed} onRefresh={() => void projects.refresh()} onOpen={id => open(id, 'code')} />
    </div>} />
    {generation && <TrackedPracticeGeneration key={generation.key} id={generation.id} mode={generation.mode} goal={generation.goal}
      submitting={submitting && !generation.id} submitError={generation.id ? '' : generation.mode === 'code' ? projects.error : state.submitFailed ? '暂时无法提交，请关闭窗口后重试。' : ''}
      onClose={() => setGeneration(undefined)} onEnter={() => { location.hash = `/practice/${generation.mode === 'code' ? 'code/' : ''}${encodeURIComponent(generation.id!)}`; }} />}
  </>;
}

export { ExamHome } from '../exam/ExamHome';
