export type ClassroomAutoplayController = {
  complete(sceneIndex: number, revision: number): boolean;
  enter(sceneIndex: number): Promise<void>;
  play(): Promise<void>;
};

export async function completeAndAdvance({
  controller,
  sceneIndex,
  revision,
  sceneCount,
}: {
  controller: ClassroomAutoplayController;
  sceneIndex: number;
  revision: number;
  sceneCount: number;
}): Promise<boolean> {
  if (!controller.complete(sceneIndex, revision)) return false;
  if (sceneIndex >= sceneCount - 1) return true;
  await controller.enter(sceneIndex + 1);
  await controller.play();
  return true;
}
