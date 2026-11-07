import assert from "node:assert/strict";
import { test } from "node:test";
import { RETRY_LIMIT, retryDelayMs, screenChoices, shouldRetry } from "../js/client.js";

test("reconnects after a dropped connection, and after a network blink once it had worked", () => {
  assert.equal(shouldRetry("connection_lost", { retries: 0 }), true);
  assert.equal(shouldRetry("connection_lost", { retries: RETRY_LIMIT }), false);
  // the relay unreachable on the first try = the PC/relay is off: say so instead of retrying
  assert.equal(shouldRetry("offline", { wasConnected: false }), false);
  assert.equal(shouldRetry("offline", { wasConnected: true, retries: 2 }), true);
  assert.equal(shouldRetry("connect_timeout", { wasConnected: true }), true);
  for (const r of ["declined", "revoked", "busy", "not_allowed", "closed", "replaced"]) {
    assert.equal(shouldRetry(r, { wasConnected: true }), false, r);
  }
  assert.deepEqual([1, 2, 3, 4, 5].map(retryDelayMs), [2000, 4000, 8000, 15000, 15000]);
});

test("screen picker only for a PC sharing several screens", () => {
  assert.deepEqual(screenChoices(null), []);
  assert.deepEqual(screenChoices({ type: "monitors", active: 0, screens: [{ index: 0, name: "Screen 1", w: 1920, h: 1080 }] }), []);
  assert.deepEqual(screenChoices({ type: "monitors", active: 1, screens: [
    { index: 0, name: "Screen 1", w: 1920, h: 1080, x: 0, y: 0 },
    { index: 1, w: 2560, h: 1440, x: 1920, y: 0 },
    { index: "2" },
  ] }), [{ index: 0, label: "Screen 1 (1920×1080)" }, { index: 1, label: "Screen 2 (2560×1440)" }]);
});
