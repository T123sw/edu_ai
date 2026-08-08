import assert from "node:assert/strict";
import test from "node:test";

import {
  buildWebsiteFaviconUrl,
  inferWebsiteUrlFromFileName,
} from "./websiteIcon.ts";

test("web documents fall back to the source website favicon", () => {
  assert.equal(
    buildWebsiteFaviconUrl("https://www.example.com/articles/rag?q=1"),
    "https://www.example.com/favicon.ico",
  );
});

test("legacy deep-research filenames retain enough information for a site icon", () => {
  assert.equal(
    inferWebsiteUrlFromFileName("web_blog.csdn.net_快速排序_12fc537fe108.md"),
    "https://blog.csdn.net",
  );
  assert.equal(inferWebsiteUrlFromFileName("chapter-one.md"), undefined);
});

test("invalid and non-web URLs do not create favicon requests", () => {
  assert.equal(buildWebsiteFaviconUrl(""), undefined);
  assert.equal(buildWebsiteFaviconUrl("not a URL"), undefined);
  assert.equal(buildWebsiteFaviconUrl("file:///tmp/page.md"), undefined);
});
