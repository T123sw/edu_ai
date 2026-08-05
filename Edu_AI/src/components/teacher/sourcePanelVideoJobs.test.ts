import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("./SourcePanel.tsx", import.meta.url),
  "utf8",
);

test("video uploads delegate progress to the global recoverable job center", () => {
  assert.doesNotMatch(source, /getVideoJobStatus/);
  assert.doesNotMatch(source, /pollVideoJobUntilDone/);
  assert.match(source, /requestJobRefresh\(uploadRes\.job_id\)/);
  assert.match(source, /后台入库任务/);
});
