import { useEffect, useMemo, useState } from 'react';
import type { Slide } from '@openmaic/renderer';
import type { Action } from '@openmaic/dsl';
import { SlidePlayer } from '../../../openmaic/SlidePlayer';

/**
 * Dev-only viewer for a real, SPEC-04-persisted classroom (ACC-08 AC-08-3).
 * Not linked from any nav — reachable at
 * `#classroom-player?course_id=...&classroom_id=...` during development.
 *
 * Unlike PlayerSmoke (hand-written fixture), this fetches the actual
 * Stage/Scene[] JSON that `classroom_service.generate_classroom_for_course`
 * validated and persisted, and plays every scene in order — the first real
 * end-to-end check of generation → storage → frontend playback.
 */

const API_BASE_URL = (import.meta as unknown as { env: Record<string, string | undefined> }).env
  .VITE_API_BASE_URL || 'http://localhost:8001';

interface ClassroomScene {
  id: string;
  type: string;
  content?: { type?: string; canvas?: Slide };
  actions?: Action[];
}

interface ClassroomMaterial {
  title?: string;
  stage?: { id: string; name?: string };
  scenes?: ClassroomScene[];
  scenes_count?: number;
}

function getAuthToken(): string | null {
  try {
    const raw = window.localStorage.getItem('edu-ai-auth');
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { token?: string };
    return parsed.token ?? null;
  } catch {
    return null;
  }
}

function getQueryParams(): { courseId: string | null; classroomId: string | null } {
  const query = window.location.hash.split('?')[1] ?? '';
  const params = new URLSearchParams(query);
  return { courseId: params.get('course_id'), classroomId: params.get('classroom_id') };
}

export function ClassroomPlayerPage() {
  const { courseId, classroomId } = useMemo(getQueryParams, []);
  const [material, setMaterial] = useState<ClassroomMaterial | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sceneIndex, setSceneIndex] = useState(0);

  useEffect(() => {
    if (!courseId || !classroomId) {
      setError('缺少 course_id / classroom_id query 参数');
      return;
    }
    const token = getAuthToken();
    if (!token) {
      setError('未登录（localStorage 里没有 edu-ai-auth token），请先在主应用登录一次');
      return;
    }

    fetch(`${API_BASE_URL}/api/courses/${courseId}/classrooms/${classroomId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        return res.json();
      })
      .then((data: ClassroomMaterial) => setMaterial(data))
      .catch((err: Error) => setError(err.message));
  }, [courseId, classroomId]);

  const scenes = material?.scenes ?? [];
  const currentScene = scenes[sceneIndex];
  const slideScenes = scenes.filter((s) => s.content?.type === 'slide' && s.content.canvas);

  if (error) {
    return <div style={{ padding: 24, color: '#c0392b' }}>加载失败：{error}</div>;
  }
  if (!material) {
    return <div style={{ padding: 24 }}>加载中…（course_id={courseId}, classroom_id={classroomId}）</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 24 }}>
      <h2>
        {material.title ?? material.stage?.name ?? 'Untitled'} — 共 {scenes.length} 个 scene
        （{slideScenes.length} 个 slide 类型）
      </h2>
      <p style={{ color: '#667085', fontSize: 13 }}>
        当前 scene {sceneIndex + 1}/{scenes.length}：{currentScene?.id} (type={currentScene?.type})
      </p>
      {currentScene?.content?.type === 'slide' && currentScene.content.canvas ? (
        <div style={{ width: 960, height: 540, border: '1px solid #ddd' }}>
          <SlidePlayer
            key={currentScene.id}
            slide={currentScene.content.canvas}
            actions={currentScene.actions}
            sceneId={currentScene.id}
            onComplete={() => setSceneIndex((i) => Math.min(i + 1, scenes.length - 1))}
          />
        </div>
      ) : currentScene ? (
        <div style={{ width: 960, padding: 24, border: '1px solid #ddd', color: '#667085' }}>
          scene type "{currentScene.type}" 暂不支持播放（P3-1 只接了 slide 类型的渲染）
        </div>
      ) : null}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          disabled={sceneIndex === 0}
          onClick={() => setSceneIndex((i) => Math.max(i - 1, 0))}
        >
          上一个 scene
        </button>
        <button
          type="button"
          disabled={sceneIndex >= scenes.length - 1}
          onClick={() => setSceneIndex((i) => Math.min(i + 1, scenes.length - 1))}
        >
          下一个 scene
        </button>
      </div>
    </div>
  );
}
