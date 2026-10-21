import { useEffect, useState } from 'react';
import type { ClassroomReadingContext } from '../../../classroom/reading';
import type { PlaybackCommand } from '../../../classroom/playbackTypes';
import { HyperframesClassroom } from '../../../hyperframes/HyperframesClassroom';
import { nativeContent } from '../../../hyperframes/types';
import { getClassroom } from '../../api/classroom';
import { apiBlob } from '../../api/client';
import type { ClassroomMaterial } from '../../api/types';
import type { WorkspaceQaRegistration } from './workspaceQaBinding';

export type ClassroomQaBinding = Omit<WorkspaceQaRegistration, 'kind'> & { kind: 'classroom' | 'personal_classroom'; version: number | null };
export type ClassroomPlaybackSurfaceProps = {
  courseId: string; classroomId: string; initialScene?: number; initialSceneId?: string;
  initialSeconds?: number; initialSegmentId?: string; restoreSavedPosition?: boolean; externallyPaused?: boolean;
  playbackCommand?: PlaybackCommand;
  onPositionChange?: (position: number) => void;
  onReadingContext?: (segmentId: string, version: number, reachedEnd: boolean, classroom: ClassroomReadingContext) => void;
  resourceVersion?: number; exactMaterial?: ClassroomMaterial; mode: 'manage' | 'learn';
  catalogNodeId?: string | null; catalogResourceId?: string | null; kind?: 'classroom' | 'personal_classroom';
  qaTargetKey?: string; onQaControllerChange?: (targetKey: string, binding: ClassroomQaBinding | null) => void;
};
export function ClassroomPlaybackSurface(props: ClassroomPlaybackSurfaceProps) {
  const [loaded, setLoaded] = useState<{ key: string; material: ClassroomMaterial }>();
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const key = JSON.stringify([props.courseId, props.classroomId, props.resourceVersion]);
  useEffect(() => {
    let active = true; setError(''); setLoaded(undefined);
    const load = props.exactMaterial ? Promise.resolve(props.exactMaterial) : getClassroom(props.courseId, props.classroomId, props.resourceVersion);
    void load.then(material => {
      if (props.resourceVersion !== undefined && material.version !== props.resourceVersion) throw new Error('资料版本已变化，请重新打开');
      if (active) setLoaded({ key, material });
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : '课堂加载失败'); });
    return () => { active = false; };
  }, [key, props.courseId, props.classroomId, props.resourceVersion, props.exactMaterial, retry]);
  if (error) return <section role="alert">{error}<button onClick={() => setRetry(n => n + 1)}>重新加载</button></section>;
  if (!loaded || loaded.key !== key) return <p role="status">正在读取课堂…</p>;
  const content = nativeContent(loaded.material);
  if (content) return <HyperframesClassroom key={`${key}:${content.project.digest}`} {...props} material={loaded.material} content={content} />;
  return <ArchivedClassroom material={loaded.material} />;
}
function ArchivedClassroom({ material }: { material: ClassroomMaterial }) {
  const [error, setError] = useState('');
  const [video, setVideo] = useState<string>();
  useEffect(() => {
    let active = true; let objectUrl: string | undefined;
    if (material.video_url?.startsWith('/api/')) void apiBlob(material.video_url).then(blob => { objectUrl = URL.createObjectURL(blob); if (active) setVideo(objectUrl); else URL.revokeObjectURL(objectUrl); }).catch(() => { if (active) setError('历史视频暂不可读取'); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [material.video_url]);
  return <article className="hf-classroom"><h2>{material.title || '历史课堂'}</h2><p role="status">这是历史课堂归档。保留已有讲稿与视频；如需动画课堂，请重新生成。</p>{error && <p>{error}</p>}{video && <video controls src={video} style={{ width: '100%' }} />}{material.scenes?.map(scene => <section key={scene.id}><h3>{scene.title}</h3>{scene.actions?.filter(action => action.type === 'speech').map((action, i) => <p key={i}>{String(action.text || '')}</p>)}</section>)}</article>;
}
