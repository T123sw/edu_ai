import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function assertIncludes(filePath: string, snippet: string) {
  const content = readFileSync(resolve(filePath), "utf8");
  if (!content.includes(snippet)) {
    throw new Error(`Expected ${filePath} to include: ${snippet}`);
  }
}

assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.css",
  "linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%)",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/teacher/CourseDetailPage.css",
  "backdrop-filter: blur(20px)",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.css",
  "box-shadow: 0 24px 60px",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/UserCenterPage.css",
  "linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%)",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DataPipelinePage.css",
  "border-radius: 28px",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DataPipelinePage.css",
  "backdrop-filter: blur(18px)",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DeepSearchPage.css",
  "box-shadow: 0 24px 60px",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DeepSearchPage.css",
  "border-radius: 28px",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DocsPage.css",
  "border-radius: 28px",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DocsPage.css",
  "backdrop-filter: blur(18px)",
);
assertIncludes(
  "D:/Edu_AI_1/Edu_AI/src/pages/DataPipelinePage.tsx",
  "className=\"pipeline-tabs\"",
);

console.log("legacy-shell-style-integration tests passed");
