import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

function read(filePath: string) {
  return readFileSync(resolve(filePath), "utf8");
}

function assertIncludes(filePath: string, snippet: string) {
  const content = read(filePath);
  if (!content.includes(snippet)) {
    throw new Error(`Expected ${filePath} to include: ${snippet}`);
  }
}

const videoDocPath = "D:/Edu_AI_1/docs/architecture/video-playback-interfaces.md";
if (!existsSync(resolve(videoDocPath))) {
  throw new Error(`Expected ${videoDocPath} to exist`);
}

assertIncludes(videoDocPath, "/api/video/stream");
assertIncludes(videoDocPath, "/api/video/upload");
assertIncludes(videoDocPath, "/api/video/search");
assertIncludes(videoDocPath, "getAiLecturerVideoUrl");

assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.tsx", "className=\"profile-hero-card\"");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.tsx", "handleLogout");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.tsx", "navigate('/login', { replace: true })");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.tsx", "handleAvatarChange");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.tsx", "handleResetPassword");

assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/KnowledgeBasePage.tsx", "getKnowledgeBaseDocuments");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/KnowledgeBasePage.tsx", "uploadKnowledgeBaseDocument");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/KnowledgeBasePage.tsx", "className=\"kb-shell\"");

assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "updateCourse");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "addKnowledgeBaseItem");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "removeKnowledgeBaseItem");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "className=\"course-edit-hero\"");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "className=\"course-cover-preview\"");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "coverImage");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "image: values.image?.trim()");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "handleCoverImageUpload");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.tsx", "readAsDataURL");

assertIncludes("D:/Edu_AI_1/Edu_AI/src/store/course/useCourseStore.ts", "image?: string");
assertIncludes("D:/Edu_AI_1/Edu_AI/src/store/course/useCourseStore.ts", "COURSE_IMAGE_STORAGE_KEY");

console.log("profile-kb-courseedit replacement tests passed");
