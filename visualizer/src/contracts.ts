export type DiagnosticEvent = {
  run_id: string;
  timestamp: string;
  event: string;
  stage: string;
  elapsed_seconds: number;
  role?: string;
  operation?: string;
  call?: number;
  inspection_round?: number;
  remaining_rounds?: number;
  task_status?: string;
  run_status?: string;
  graph_version?: string;
  functional_complete?: boolean;
  pr_ready?: boolean;
};

export type EventEnvelope = {
  schemaVersion: 1;
  recordingId: string;
  cursor: string;
  ordinal: number;
  segment: number;
  payload: DiagnosticEvent;
};

const TASK_STATUSES = new Set([
  "COMPLETED",
  "FAILED",
  "PAUSED",
  "BLOCKED",
  "PLAN_ONLY",
]);

const stringField = (value: unknown, max = 128): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= max;

const numberField = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;

export function parseEvent(input: unknown): DiagnosticEvent {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("Diagnostic record must be an object");
  }
  const value = input as Record<string, unknown>;
  if (
    !stringField(value.run_id) || !stringField(value.timestamp) ||
    !stringField(value.event) || !stringField(value.stage) ||
    !numberField(value.elapsed_seconds)
  ) {
    throw new Error("Diagnostic record has invalid required fields");
  }
  const event: DiagnosticEvent = {
    run_id: value.run_id,
    timestamp: value.timestamp,
    event: value.event,
    stage: value.stage,
    elapsed_seconds: value.elapsed_seconds,
  };
  for (const key of ["functional_complete", "pr_ready"] as const) {
    if (typeof value[key] === "boolean") event[key] = value[key];
  }
  for (const key of ["role", "operation", "graph_version"] as const) {
    if (stringField(value[key])) event[key] = value[key];
  }
  if (stringField(value.task_status) && TASK_STATUSES.has(value.task_status)) {
    event.task_status = value.task_status;
  }
  if (stringField(value.run_status) && TASK_STATUSES.has(value.run_status)) {
    event.run_status = value.run_status;
  }
  for (const key of ["call", "inspection_round", "remaining_rounds"] as const) {
    if (Number.isSafeInteger(value[key]) && numberField(value[key])) {
      event[key] = value[key];
    }
  }
  return event;
}

export function parseRecording(
  text: string,
  recordingId = "local-import",
): EventEnvelope[] {
  if (new TextEncoder().encode(text).length > 1024 * 1024) {
    throw new Error("Recording exceeds the 1 MiB import limit");
  }
  const lines = text.split(/\r?\n/);
  const events: EventEnvelope[] = [];
  let segment = 0;
  for (const [index, line] of lines.entries()) {
    if (!line.trim()) continue;
    if (new TextEncoder().encode(line).length > 16 * 1024) {
      throw new Error(`Record ${index + 1} exceeds 16 KiB`);
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      throw new Error(`Record ${index + 1} is not valid JSON`);
    }
    const payload = parseEvent(parsed);
    if (events.length && payload.run_id !== events[0].payload.run_id) {
      throw new Error("Recording contains multiple run IDs");
    }
    if (payload.event === "run_started") segment++;
    events.push({
      schemaVersion: 1,
      recordingId,
      cursor: `${recordingId}:${index + 1}`,
      ordinal: events.length + 1,
      segment,
      payload,
    });
  }
  return events;
}
