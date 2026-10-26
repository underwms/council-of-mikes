import { appendLiveEvent, parseLiveEnvelope } from "../src/live.ts";

const payload = {
  run_id: "run",
  timestamp: "2026-01-01T00:00:00Z",
  event: "node_started",
  stage: "architect",
  elapsed_seconds: 1,
};

Deno.test("live: reconnect duplicate cursor does not duplicate a visit", () => {
  const envelope = parseLiveEnvelope({
    schemaVersion: 1,
    recordingId: "gen",
    cursor: "gen:123",
    ordinal: 1,
    segment: 1,
    payload,
  });
  const once = appendLiveEvent([], envelope);
  const twice = appendLiveEvent(once, envelope);
  if (twice.length !== 1) throw new Error("Duplicate cursor was appended");
});

Deno.test("live: a new recording generation replaces stale events", () => {
  const old = parseLiveEnvelope({
    schemaVersion: 1,
    recordingId: "old",
    cursor: "old:123",
    ordinal: 1,
    segment: 1,
    payload,
  });
  const fresh = parseLiveEnvelope({
    schemaVersion: 1,
    recordingId: "new",
    cursor: "new:123",
    ordinal: 1,
    segment: 1,
    payload,
  });
  const events = appendLiveEvent([old], fresh);
  if (events.length !== 1 || events[0].recordingId !== "new") {
    throw new Error("Old generation remained");
  }
});

Deno.test("live: malformed envelope is rejected", () => {
  try {
    parseLiveEnvelope({
      schemaVersion: 1,
      recordingId: "gen",
      cursor: "bad\nheader",
      ordinal: 1,
      segment: 1,
      payload,
    });
  } catch {
    return;
  }
  throw new Error("Unsafe cursor was accepted");
});
