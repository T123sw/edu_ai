// Component acceptance only. Copy this plus the fixture into frontend/.classroom-e/.
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ClassroomSceneRenderer } from '/src/openmaic/ClassroomSceneRenderer';
import '/src/styles/global.css';
import '/src/stitch/styles.css';
import data from './classroom.fixture.json';

function Harness() {
  const [index, setIndex] = useState(0);
  const [mode, setMode] = useState('idle');
  const [narration, setNarration] = useState('');
  const [complete, setComplete] = useState(0);
  const [runtime, setRuntime] = useState<any>(null);
  return <main style={{ maxWidth: 1200, margin: '0 auto', padding: 12 }}>
    <p>确定性夹具 · 原生播放器组件验证 · 非真实备课验收</p>
    <nav style={{ display: 'flex', gap: 8, margin: '12px 0', flexWrap: 'wrap' }}>
      {data.scenes.map((s, i) => <button key={s.id} onClick={() => setIndex(i)}>{s.title}</button>)}
      <button id="play" onClick={() => runtime?.play()}>执行播放</button>
    </nav>
    <div style={{ height: index === 2 ? 620 : 'auto', aspectRatio: index === 2 ? undefined : '16 / 9' }}>
      <ClassroomSceneRenderer key={index} scene={data.scenes[index] as any}
        courseId="e-component-only" classroomId={data.stage.id} autoPlay={false}
        onRuntimeReady={setRuntime} onModeChange={setMode} onNarrationChange={setNarration}
        onComplete={() => setComplete(v => v + 1)} />
    </div>
    <output id="mode">{mode}</output><output id="complete">{complete}</output>
    <p id="narration">{narration}</p>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Harness />);
