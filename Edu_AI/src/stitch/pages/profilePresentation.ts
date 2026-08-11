export function presentAccessibleCourseCount(
  courseCount: number | null | undefined,
): string {
  if (typeof courseCount === "undefined") return "加载中";
  return courseCount === null ? "暂不可用" : String(courseCount);
}
