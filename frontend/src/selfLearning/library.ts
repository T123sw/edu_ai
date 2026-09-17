import { allResources, uid, updateRoom, type LearningResource, type LearningState } from "./model";

export function addToLearning(state: LearningState, roomId: string, chapterId: string, resource: LearningResource): LearningState {
  const room = state.rooms.find(r => r.id === roomId);
  if (!room || !room.chapters.some(c => c.id === chapterId)) return state;
  if (allResources(room).some(r => r.id === resource.id || r.sourceResourceId === resource.id)) return state;
  return updateRoom(state, roomId, r => ({
    ...r,
    chapters: r.chapters.map(chapter => chapter.id !== chapterId ? chapter : {
      ...chapter,
      resources: [...chapter.resources, { ...resource, id: uid(), sourceResourceId: resource.id, chapterId, courseId: roomId }],
    }),
  }));
}
