import assert from "node:assert/strict";
import test from "node:test";
import { clearRevisionIntent, createRevisionIntent, dispatchRevisionIntent, subscribeRevisionIntent } from "./intent";

const material = { material_id: "one", material_type: "quiz", course_id: "course", version: 3, content_hash: "server-hash", owner_user_id: "teacher", visibility: "private" as const, title: "数组练习" };

test("stable ID and server version are required; ownership is checked", () => {
  assert.equal(createRevisionIntent(material, "other"), null);
  assert.equal(createRevisionIntent({ ...material, visibility: "course" }, "teacher"), null);
  assert.equal(createRevisionIntent({ ...material, version: undefined }, "teacher"), null);
  assert.equal(createRevisionIntent({ ...material, published_from_material_id: "source" }, "teacher"), null);
  assert.deepEqual(createRevisionIntent(material, "teacher")?.reference, { artifact_id: "one", artifact_type: "quiz", content_hash: "server-hash", version_id: "v3", title: "数组练习", source_course_id: "course" });
});

test("intent is delivered once across route mount, unsubscribe and account clearing work", async () => {
  clearRevisionIntent();
  const intent = createRevisionIntent(material, "teacher")!;
  dispatchRevisionIntent(intent);
  const received: unknown[] = [];
  const unsubscribe = subscribeRevisionIntent((item) => received.push(item));
  await Promise.resolve();
  assert.deepEqual(received, [intent]);
  unsubscribe();
  dispatchRevisionIntent(intent);
  clearRevisionIntent();
  const stop = subscribeRevisionIntent((item) => received.push(item));
  assert.equal(received.length, 1);
  dispatchRevisionIntent(intent);
  assert.equal(received.length, 2);
  stop();
});
