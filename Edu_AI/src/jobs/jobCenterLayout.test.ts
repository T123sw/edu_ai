import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("job cards stay inside the narrow task drawer", async () => {
  const css = await readFile(new URL("./jobCenter.css", import.meta.url), "utf8");

  assert.match(
    css,
    /\.job-center-list\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s,
  );
  assert.match(
    css,
    /\.job-card\s*\{[^}]*min-width:\s*0/s,
  );
  assert.match(
    css,
    /\.job-card__actions\s*\{[^}]*flex-wrap:\s*wrap/s,
  );
}
);
