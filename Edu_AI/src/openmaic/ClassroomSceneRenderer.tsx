import type { Slide } from '@openmaic/renderer';
import type {
  ClassroomScene,
  InteractiveClassroomContent,
  QuizClassroomContent,
  SlideClassroomContent,
} from '../stitch/api/types';
import { resolveClassroomSceneKind } from './classroomScene';
import { InteractiveScenePlayer } from './InteractiveScenePlayer';
import { QuizScenePlayer } from './QuizScenePlayer';
import { SlidePlayer } from './SlidePlayer';
import type { PlaybackMode } from './playbackEngine';

export interface ClassroomSceneRendererProps {
  scene: ClassroomScene;
  courseId: string;
  classroomId: string;
  autoPlay?: boolean;
  onComplete?: () => void;
  onModeChange?: (mode: PlaybackMode) => void;
}

export function ClassroomSceneRenderer({
  scene,
  courseId,
  classroomId,
  autoPlay = true,
  onComplete,
  onModeChange,
}: ClassroomSceneRendererProps) {
  const kind = resolveClassroomSceneKind(scene);

  switch (kind) {
    case 'slide': {
      const content = scene.content as SlideClassroomContent;
      if (!content.canvas) {
        return <SceneError message="幻灯片场景缺少画布数据。" />;
      }
      return (
        <SlidePlayer
          slide={content.canvas as unknown as Slide}
          actions={scene.actions as never}
          sceneId={scene.id}
          autoPlay={autoPlay}
          onComplete={onComplete}
          onModeChange={onModeChange}
        />
      );
    }
    case 'interactive':
      return (
        <InteractiveScenePlayer
          sceneId={scene.id}
          content={scene.content as InteractiveClassroomContent}
          actions={scene.actions}
          autoPlay={autoPlay}
          onComplete={onComplete}
          onModeChange={onModeChange}
        />
      );
    case 'quiz':
      return (
        <QuizScenePlayer
          courseId={courseId}
          classroomId={classroomId}
          sceneId={scene.id}
          title={scene.title}
          content={scene.content as QuizClassroomContent}
          actions={scene.actions}
          autoPlay={autoPlay}
          onComplete={onComplete}
          onModeChange={onModeChange}
        />
      );
    case 'invalid':
      return (
        <SceneError
          message="这一页的数据不完整，暂时无法播放。请返回后重新生成课件。"
        />
      );
    default:
      return <SceneError message="这一页暂不支持在线播放，可尝试导出课件后查看。" />;
  }
}

function SceneError({ message }: { message: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-(--surface-subtle) p-10 text-center text-sm text-(--muted-text)">
      {message}
    </div>
  );
}
