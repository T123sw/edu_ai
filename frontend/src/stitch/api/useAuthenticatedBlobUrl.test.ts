import assert from "node:assert/strict";
import test from "node:test";

import { requiresAuthenticatedAssetFetch } from "./authenticatedAsset";

test("protected API assets are loaded through the authenticated client", () => {
  assert.equal(requiresAuthenticatedAssetFetch("/api/images/searched/abc.jpg"), true);
  assert.equal(requiresAuthenticatedAssetFetch("/api/chat/v2/games/html?path=x"), true);
  assert.equal(requiresAuthenticatedAssetFetch("https://example.com/image.jpg"), false);
  assert.equal(requiresAuthenticatedAssetFetch("blob:http://localhost/id"), false);
});
