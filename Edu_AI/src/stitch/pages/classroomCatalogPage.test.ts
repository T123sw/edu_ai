import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


const source = (relativePath: string) => readFile(new URL(relativePath, import.meta.url), "utf8");


test("AI classroom page is coordinated by the role-safe curriculum catalog", async () => {
  const page = await source("./ClassroomStudio.tsx");
  assert.match(page, /getClassroomCatalog/);
  assert.match(page, /<CurriculumResourceTree/);
  assert.match(page, /<CurriculumNodeOverview/);
  assert.match(page, /<CourseResourceViewer/);
  assert.match(page, /LearningResourceGenerationPanel/);
  assert.doesNotMatch(page, /getCourseMaterials\(courseId, \{ materialType: "classroom"/);
  assert.doesNotMatch(page, /已生成的课件/);
  assert.match(page, /课程目录/);
});


test("curriculum directory exposes keyboard tree semantics and visible statuses", async () => {
  const tree = await source("../course/classroomCatalog/CurriculumResourceTree.tsx");
  assert.match(tree, /role="tree"/);
  assert.match(tree, /role="treeitem"/);
  assert.match(tree, /aria-expanded/);
  assert.match(tree, /tabIndex/);
  assert.match(tree, /catalogResourceStatus/);
  for (const key of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"]) {
    assert.match(tree, new RegExp(key));
  }
});

test("personal classrooms stay at the bottom of the directory with local loading states", async () => {
  const [page, personalList] = await Promise.all([
    source("./ClassroomStudio.tsx"),
    source("../course/classroomCatalog/MyClassroomList.tsx"),
  ]);
  assert.match(page, /listClassrooms\(courseId,\s*"mine"\)/);
  assert.match(page, /<MyClassroomList/);
  assert.match(page, /personal_classroom_id|buildWorkspaceHash/);
  assert.match(personalList, /我的课堂/);
  assert.match(personalList, /aria-labelledby="my-classroom-title"/);
  for (const status of ["可观看", "生成中", "生成失败", "暂无内容"]) {
    assert.match(personalList, new RegExp(status));
  }
  assert.match(personalList, /个人课堂暂时无法加载/);
  assert.match(personalList, /重新加载/);
});

test("teacher reviews a selected version without hiding its preview", async () => {
  const [page, viewer, review] = await Promise.all([
    source("./ClassroomStudio.tsx"),
    source("../course/classroomCatalog/CourseResourceViewer.tsx"),
    source("../course/classroomCatalog/TeacherResourceReviewPanel.tsx"),
  ]);
  assert.match(page, /onChanged/);
  assert.match(viewer, /CourseMaterialArtifactPreview/);
  assert.match(viewer, /TeacherResourceReviewPanel/);
  assert.match(review, /reviewStandardResource/);
  assert.match(review, /批准并发布/);
  assert.match(review, /退回修改/);
  assert.match(review, /rejectionReason/);
  assert.match(review, /disabled=\{submitting/);
});
