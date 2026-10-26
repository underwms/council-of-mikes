import { type EventEnvelope, parseEvent } from "./contracts.ts";

export function parseLiveEnvelope(input: unknown): EventEnvelope {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("Invalid live envelope");
  }
  const value = input as Record<string, unknown>;
  if (
    value.schemaVersion !== 1 || typeof value.recordingId !== "string" ||
    !/^[A-Za-z0-9_-]{1,192}$/.test(value.recordingId) ||
    typeof value.cursor !== "string" ||
    !value.cursor.startsWith(`${value.recordingId}:`) ||
    !/^\d{1,8}$/.test(value.cursor.slice(value.recordingId.length + 1)) ||
    !Number.isSafeInteger(value.ordinal) || (value.ordinal as number) < 1 ||
    !Number.isSafeInteger(value.segment) || (value.segment as number) < 0
  ) {
    throw new Error("Invalid live envelope fields");
  }
  return {
    schemaVersion: 1,
    recordingId: value.recordingId,
    cursor: value.cursor,
    ordinal: value.ordinal as number,
    segment: value.segment as number,
    payload: parseEvent(value.payload),
  };
}

export function appendLiveEvent(
  events: readonly EventEnvelope[],
  event: EventEnvelope,
): EventEnvelope[] {
  if (events.length && events[0].recordingId !== event.recordingId) {
    return [event];
  }
  if (events.some((existing) => existing.cursor === event.cursor)) {
    return [...events];
  }
  return [...events, event];
}
