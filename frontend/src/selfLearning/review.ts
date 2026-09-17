import { allResources, uid, type Classroom, type LearningState } from "./model";
import { restoreState, storageKey } from "./store";

export const reviewEnabled = () => new URLSearchParams(location.search).get("review") === "1";
type LearningSession = { owner: string; role: "teacher" | "student"; search: string };
function learningSession(id = new URLSearchParams(location.search).get("learningSession")): LearningSession | undefined {
  if (!id) return;
  try { return JSON.parse(sessionStorage.getItem(`edu-learning-session:${id}`) || "null") || undefined; } catch { return; }
}
export function createLearningSession(owner: string, role?: string) {
  const id = uid();
  sessionStorage.setItem(`edu-learning-session:${id}`, JSON.stringify({ owner, role: role === "student" ? "student" : "teacher", search: location.search }));
  return id;
}
export const reviewRole = () => learningSession()?.role || (new URLSearchParams(location.search).get("role") === "student" ? "student" : "teacher");
export const reviewOwner = () => learningSession()?.owner || `review:${reviewRole()}`;

export function readReviewState(): LearningState {
  return restoreState(localStorage.getItem(storageKey(reviewOwner())), true);
}
export function writeReviewState(state: LearningState) {
  localStorage.setItem(storageKey(reviewOwner()), JSON.stringify(state));
}
export function reviewPageHref(page: "classroom" | "resources" | "home", roomId?: string, resourceId?: string) {
  const url = new URL(location.href);
  url.searchParams.delete("workbench");
  url.searchParams.delete("workspace");
  const source = learningSession();
  if (source) url.search = source.search;
  const query = new URLSearchParams();
  if (page === "resources" && roomId) query.set("classroom", roomId);
  if (resourceId) query.set("resource", resourceId);
  url.hash = page === "home" ? "/" : page === "classroom" ? `/classroom/${roomId}${query.size ? `?${query}` : ""}` : `/resources?${query}`;
  return `${url.pathname}${url.search}${url.hash}`;
}
export function reviewWorkbenchHref(room: Classroom, resourceId?: string, sessionId?: string) {
  const url = new URL(location.href);
  url.searchParams.set("review", "1");
  url.searchParams.set("workbench", "1");
  if (sessionId) url.searchParams.set("learningSession", sessionId);
  const source = learningSession(sessionId);
  const sourceState = source ? restoreState(localStorage.getItem(storageKey(source.owner)), false) : readReviewState();
  const resource = allResources(room).find(r => r.id === (resourceId || room.selectedId))
    || sourceState.resources.find(r => r.id === resourceId && (!r.courseId || r.courseId === room.id));
  const chapter = room.chapters.find(c => c.id === resource?.chapterId || c.resources.some(r => r.id === resource?.id));
  const params = new URLSearchParams({ course_id: room.id });
  if (chapter) {
    params.set("scopeType", "knowledge_point");
    params.set("scopeId", chapter.id);
    params.set("scopeLabel", chapter.title);
  }
  if (resourceId && sourceState.resources.some(r => r.id === resourceId && (!r.courseId || r.courseId === room.id))) params.set("reference", resourceId);
  url.hash = `${(source?.role || reviewRole()) === "student" ? "student-ai" : "ai"}?${params}`;
  return `${url.pathname}${url.search}${url.hash}`;
}
