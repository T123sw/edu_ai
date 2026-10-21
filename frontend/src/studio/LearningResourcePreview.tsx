import { useState } from 'react';
import type { CourseMaterial } from '../stitch/api/types';
import { useAuthenticatedBlobUrl } from '../stitch/api/useAuthenticatedBlobUrl';
import { MarkdownPreview } from '../stitch/components/MarkdownPreview';
import './learningResources.css';

type Segment = { title: string; text: string };
type Podcast = { title: string; summary: string; audio_url: string; segments: Segment[] };
function PodcastAudio({ url, title, onRetry }: { url: string; title: string; onRetry: () => void }) {
  const audio = useAuthenticatedBlobUrl(url);
  const [failed, setFailed] = useState(false);
  if (audio.loading) return <p role="status">正在加载播客音频…</p>;
  if (audio.error || !audio.url || failed) return <p role="alert">音频暂时无法播放。<button type="button" onClick={onRetry}>重新加载音频</button></p>;
  return <div className="studio-podcast-audio"><audio controls preload="metadata" src={audio.url} aria-label={title || '播客音频'} onError={() => setFailed(true)} /><a href={audio.url} download={`${title || '播客'}.mp3`}>下载音频</a></div>;
}
export function PodcastPreview({ material }: { material: CourseMaterial }) {
  const content = material.content as Partial<Podcast> | null;
  const [retry, setRetry] = useState(0);
  if (!content || !Array.isArray(content.segments) || !content.segments.length) return <p>播客内容暂时无法读取。</p>;
  const url = typeof content.audio_url === 'string' && content.audio_url.startsWith('/api/personal-studio/resources/podcast/') ? content.audio_url : '';
  return <section className="studio-podcast" aria-label="播客播放器">
    <h3>{content.title || material.title}</h3><p>{content.summary}</p>
    <PodcastAudio key={retry} url={url} title={content.title || material.title || '播客'} onRetry={() => setRetry(value => value + 1)} />
    <h4>分章节文字稿</h4><div className="studio-transcript">{content.segments.map((segment, index) => <details key={index} open={index === 0}><summary>{index + 1}. {segment.title}</summary><div className="edu-rich-preview"><MarkdownPreview content={segment.text} /></div></details>)}</div>
  </section>;
}

type Choice = { id: string; text: string; feedback: string; next_id: string };
type Scene = { id: string; title: string; situation: string; choices: Choice[]; ending: string; takeaway: string };
type Scenario = { title: string; introduction: string; learning_objectives: string[]; start_id: string; scenes: Scene[] };
export function ScenarioPreview({ material }: { material: CourseMaterial }) {
  const content = material.content as Partial<Scenario> | null;
  const [current, setCurrent] = useState(content?.start_id || '');
  const [choice, setChoice] = useState<Choice | null>(null);
  const [history, setHistory] = useState<{ scene: string; choice: string; feedback: string }[]>([]);
  const scene = content?.scenes?.find(item => item.id === current);
  if (!scene) return <p role="alert">情景案例暂时无法读取。</p>;
  const restart = () => { setCurrent(content?.start_id || ''); setChoice(null); setHistory([]); };
  const advance = () => {
    if (!choice) return;
    setHistory(previous => [...previous, { scene: scene.title, choice: choice.text, feedback: choice.feedback }]);
    setCurrent(choice.next_id); setChoice(null);
  };
  return <section className="studio-scenario" aria-label="情景案例练习">
    <span className="studio-scenario-label">模拟情景</span><h3>{content?.title || material.title}</h3><p>{content?.introduction}</p>
    <details className="studio-scenario-objectives"><summary>练习目标</summary><ul>{content?.learning_objectives?.map((objective, i) => <li key={i}>{objective}</li>)}</ul></details>
    <article className="studio-scenario-scene"><small>{scene.choices.length ? `决策 ${history.length + 1}` : '情景结束'}</small><h4>{scene.title}</h4><div className="edu-rich-preview"><MarkdownPreview content={scene.situation} /></div>
      {scene.choices.length ? <><div className="studio-scenario-choices">{scene.choices.map((item, i) => <button key={item.id} type="button" disabled={!!choice} aria-pressed={choice?.id === item.id} onClick={() => setChoice(item)}><span>{String.fromCharCode(65 + i)}</span>{item.text}</button>)}</div>
        {choice && <div className="studio-scenario-feedback" role="status"><strong>选择后的反馈</strong><MarkdownPreview content={choice.feedback} /><button type="button" onClick={advance}>继续情景</button></div>}</>
        : <div className="studio-scenario-ending"><strong>你的结局</strong><MarkdownPreview content={scene.ending} /><h4>复盘与启示</h4><MarkdownPreview content={scene.takeaway} /><button type="button" onClick={restart}>重新体验</button></div>}
    </article>
    {!!history.length && <details className="studio-scenario-history"><summary>本次选择记录 · {history.length}</summary><ol>{history.map((item, i) => <li key={i}><strong>{item.scene}</strong><p>{item.choice}</p><p>{item.feedback}</p></li>)}</ol></details>}
  </section>;
}
