import type { JobRecord } from "./types";

export type JobCourseGroup = {
  courseId: string | null;
  title: string;
  jobs: JobRecord[];
};

type JobCourseGroupingOptions = {
  currentCourseId: string | null;
  currentCourseTitle?: string | null;
  courseTitles: ReadonlyMap<string, string>;
};

function courseTitle(
  courseId: string,
  options: JobCourseGroupingOptions,
): string {
  if (
    courseId === options.currentCourseId &&
    options.currentCourseTitle?.trim()
  ) {
    return options.currentCourseTitle.trim();
  }
  return options.courseTitles.get(courseId)?.trim() || `课程 ${courseId}`;
}

export function buildJobCourseGroups(
  jobs: JobRecord[],
  options: JobCourseGroupingOptions,
): JobCourseGroup[] {
  if (options.currentCourseId) {
    return [
      {
        courseId: options.currentCourseId,
        title: courseTitle(options.currentCourseId, options),
        jobs: jobs.filter((job) => job.course_id === options.currentCourseId),
      },
    ];
  }

  const groups = new Map<string, JobCourseGroup>();
  let unscopedGroup: JobCourseGroup | null = null;

  jobs.forEach((job) => {
    const id = String(job.course_id ?? "").trim();
    if (!id) {
      unscopedGroup ??= { courseId: null, title: "其他任务", jobs: [] };
      unscopedGroup.jobs.push(job);
      return;
    }

    const group = groups.get(id) ?? {
      courseId: id,
      title: courseTitle(id, options),
      jobs: [],
    };
    group.jobs.push(job);
    groups.set(id, group);
  });

  return [...groups.values(), ...(unscopedGroup ? [unscopedGroup] : [])];
}
