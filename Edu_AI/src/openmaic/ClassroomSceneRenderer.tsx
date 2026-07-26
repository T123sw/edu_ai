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

export interface ClassroomSceneRendererProps {
  scene: ClassroomScene;
  courseId: string;
  classroomId: string;
  onSlideComplete?: () => void;
}

export function ClassroomSceneRenderer({
  scene,
  courseId,
  classroomId,
  onSlideComplete,
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
          onComplete={onSlideComplete}
        />
      );
    }
    case 'interactive':
      return (
        <InteractiveScenePlayer
          sceneId={scene.id}
          content={scene.content as InteractiveClassroomContent}
          actions={scene.actions}
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
        />
      );
    case 'invalid':
      return (
        <SceneError
          message={`场景声明不一致：scene.type="${scene.type}"，content.type="${scene.content?.type ?? 'missing'}"。`}
        />
      );
    default:
      return <SceneError message={`暂不支持场景类型 "${scene.type}"。`} />;
  }
}

function SceneError({ message }: { message: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-(--surface-subtle) p-10 text-center text-sm text-(--muted-text)">
      {message}
    </div>
  );
}
