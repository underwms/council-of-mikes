/** Browser projection of the existing sanitized observation API. Null is unmeasured. */
export type Fact = Record<string, unknown>;
export type StreamKind =
  | "milestones"
  | "calls"
  | "commands"
  | "sessions"
  | "events"
  | "export";
export type GroupBy =
  | "role"
  | "operation"
  | "provider"
  | "requested_model"
  | "reported_model";
export type Availability = "available" | "unavailable" | "unsupported_schema";
export type Explanation = {
  state: string | null;
  message: string | null;
  timestamp: string | null;
};
const tokenKeys = [
  "input_tokens",
  "output_tokens",
  "total_tokens",
  "cached_input_tokens",
] as const;
type TokenKey = typeof tokenKeys[number];
export type Usage = Record<`reported_${TokenKey}`, number | null> & {
  measured_attempts: number | null;
  missing_attempts: number | null;
  partial_attempts: number | null;
  field_attempt_counts: Record<TokenKey, number | null>;
};
export type RoleSettings = {
  provider: string | null;
  requested_model: string | null;
  configured_timeout_seconds: number | null;
};
export type Comparison = {
  distribution_version: string | null;
  engine_graph_sha256: string | null;
  requirements_sha256: string | null;
  accepted_plan_sha256: string | null;
  obligations_sha256: string | null;
  roles: Record<string, RoleSettings>;
  policy: Record<string, number>;
};
export type ObservationSummary = {
  status: Availability;
  run_id: string;
  current: Explanation | null;
  coverage: string | null;
  liveness: string | null;
  event_count: number | null;
  usage: Usage;
  calls: {
    count: number | null;
    median_seconds: number | null;
    duration_population: number | null;
  };
  wall_time_seconds: number | null;
  human_wait_seconds: number | null;
  completed_human_waits: number | null;
  unmatched_human_waits: number | null;
  unclassified_gaps: boolean | null;
  history_capped: boolean | null;
  comparison: Comparison | null;
  groups: { value: string | null; attempts: number | null; usage: Usage }[];
  groups_truncated: boolean | null;
};
export type ObservationItem = {
  position: number;
  session_id: string | null;
  session_generation: number | null;
  source_seq: number | null;
  event_id: string | null;
  event: string | null;
  stage: string | null;
  timestamp: string | null;
  explanation: Explanation | null;
  functional_complete: boolean | null;
  pr_ready: boolean | null;
  run_status: string | null;
  call: number | null;
  code: string | null;
  task_index: number | null;
  command_index: number | null;
  phase_index: number | null;
  comparison: Comparison | null;
  accounting: null | {
    role: string | null;
    operation: string | null;
    provider: string | null;
    requested_model: string | null;
    returned_model: string | null;
    cli_reported_model: string | null;
    duration_seconds: number | null;
    effective_timeout_seconds: number | null;
    usage: Record<TokenKey, number | null>;
  };
  measurement: null | {
    execution_id: string | null;
    command_sha256: string | null;
    started_utc: string | null;
    ended_utc: string | null;
    duration_seconds: number | null;
    completion: string | null;
  };
};
export type ObservationPage = {
  status: Availability;
  items: ObservationItem[];
  next_cursor: number;
};

const record = (value: unknown): Fact =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Fact
    : {};
const text = (value: unknown, max = 256): string | null =>
  typeof value === "string" && value.length > 0 && value.length <= max
    ? value
    : null;
const numeric = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 &&
    value <= 1e12
    ? value
    : null;
const integer = (value: unknown): number | null =>
  Number.isSafeInteger(value) ? numeric(value) : null;
const boolean = (value: unknown): boolean | null =>
  typeof value === "boolean" ? value : null;
const hash = (value: unknown): string | null =>
  typeof value === "string" && /^[a-f0-9]{64}$/.test(value) ? value : null;
const timestamp = (value: unknown): string | null =>
  text(value, 64) && Number.isFinite(Date.parse(String(value)))
    ? String(value)
    : null;
function availability(input: Fact): Availability {
  if (input.version !== 1) {
    throw new Error("Unsupported observation response version");
  }
  if (input.status === undefined) return "available";
  if (input.status === "unavailable" || input.status === "unsupported_schema") {
    return input.status;
  }
  throw new Error("Invalid observation availability");
}
function explanation(value: unknown): Explanation | null {
  if (value === undefined || value === null) return null;
  const raw = record(value);
  return {
    state: text(raw.state),
    message: text(raw.message, 512),
    timestamp: timestamp(raw.timestamp),
  };
}
function usage(value: unknown): Usage {
  const raw = record(value), counts = record(raw.field_attempt_counts);
  return {
    reported_input_tokens: integer(raw.reported_input_tokens),
    reported_output_tokens: integer(raw.reported_output_tokens),
    reported_total_tokens: integer(raw.reported_total_tokens),
    reported_cached_input_tokens: integer(raw.reported_cached_input_tokens),
    measured_attempts: integer(raw.measured_attempts),
    missing_attempts: integer(raw.missing_attempts),
    partial_attempts: integer(raw.partial_attempts),
    field_attempt_counts: {
      input_tokens: integer(counts.input_tokens),
      output_tokens: integer(counts.output_tokens),
      total_tokens: integer(counts.total_tokens),
      cached_input_tokens: integer(counts.cached_input_tokens),
    },
  };
}
function comparison(value: unknown): Comparison | null {
  if (value === undefined || value === null) return null;
  const raw = record(value), roles: Record<string, RoleSettings> = {};
  for (const role of ["orchestrator", "coder", "investigator", "reviewer"]) {
    const settings = record(record(raw.roles)[role]);
    if (Object.keys(settings).length) {
      roles[role] = {
        provider: text(settings.provider),
        requested_model: text(settings.requested_model),
        configured_timeout_seconds: numeric(
          settings.configured_timeout_seconds,
        ),
      };
    }
  }
  return {
    distribution_version: text(raw.distribution_version, 64),
    engine_graph_sha256: hash(raw.engine_graph_sha256),
    requirements_sha256: hash(raw.requirements_sha256),
    accepted_plan_sha256: hash(raw.accepted_plan_sha256),
    obligations_sha256: hash(raw.obligations_sha256),
    roles,
    policy: Object.fromEntries(
      Object.entries(record(raw.policy)).filter(([key, value]) =>
        ["orchestration", "integrity", "governance", "recovery"].includes(
          key,
        ) && integer(value) !== null && Number(value) <= 4
      ),
    ) as Record<string, number>,
  };
}
export function decodeSummary(
  value: unknown,
  runId: string,
): ObservationSummary {
  const raw = record(value),
    status = availability(raw),
    calls = record(raw.calls);
  if (status === "available" && raw.run_id !== runId) {
    throw new Error("Observation run identity mismatch");
  }
  if (Array.isArray(raw.groups) && raw.groups.length > 64) {
    throw new Error("Observation groups exceed limit");
  }
  return {
    status,
    run_id: runId,
    current: explanation(raw.current),
    coverage: text(raw.coverage),
    liveness: text(raw.liveness),
    event_count: integer(raw.event_count),
    usage: usage(raw.usage),
    calls: {
      count: integer(calls.count),
      median_seconds: numeric(calls.median_seconds),
      duration_population: integer(calls.duration_population),
    },
    wall_time_seconds: numeric(raw.wall_time_seconds),
    human_wait_seconds: numeric(raw.human_wait_seconds),
    completed_human_waits: integer(raw.completed_human_waits),
    unmatched_human_waits: integer(raw.unmatched_human_waits),
    unclassified_gaps: boolean(raw.unclassified_gaps),
    history_capped: boolean(raw.history_capped),
    comparison: comparison(raw.comparison),
    groups_truncated: boolean(raw.groups_truncated),
    groups: Array.isArray(raw.groups)
      ? raw.groups.map((entry) => {
        const group = record(entry);
        return {
          value: text(group.value),
          attempts: integer(group.attempts),
          usage: usage(group.usage),
        };
      })
      : [],
  };
}
function decodeItem(value: unknown): ObservationItem {
  const raw = record(value), position = integer(raw.position);
  if (position === null || position < 1) {
    throw new Error("Invalid observation position");
  }
  const accounting = record(raw.accounting),
    measurement = record(raw.measurement),
    tokens = record(accounting.usage);
  return {
    position,
    session_id: text(raw.session_id),
    session_generation: integer(raw.session_generation),
    source_seq: integer(raw.source_seq),
    event_id: hash(raw.event_id),
    event: text(raw.event),
    stage: text(raw.stage),
    timestamp: timestamp(raw.timestamp),
    explanation: explanation(raw.explanation),
    functional_complete: boolean(raw.functional_complete),
    pr_ready: boolean(raw.pr_ready),
    run_status: text(raw.run_status),
    call: integer(raw.call),
    code: text(raw.code),
    task_index: integer(raw.task_index),
    command_index: integer(raw.command_index),
    phase_index: integer(raw.phase_index),
    comparison: comparison(raw.comparison),
    accounting: raw.accounting === undefined || raw.accounting === null
      ? null
      : {
        role: text(accounting.role),
        operation: text(accounting.operation),
        provider: text(accounting.provider),
        requested_model: text(accounting.requested_model),
        returned_model: text(accounting.returned_model),
        cli_reported_model: text(accounting.cli_reported_model),
        duration_seconds: numeric(accounting.duration_seconds),
        effective_timeout_seconds: numeric(
          accounting.effective_timeout_seconds,
        ),
        usage: {
          input_tokens: integer(tokens.input_tokens),
          output_tokens: integer(tokens.output_tokens),
          total_tokens: integer(tokens.total_tokens),
          cached_input_tokens: integer(tokens.cached_input_tokens),
        },
      },
    measurement: raw.measurement === undefined || raw.measurement === null
      ? null
      : {
        execution_id: hash(measurement.execution_id),
        command_sha256: hash(measurement.command_sha256),
        started_utc: timestamp(measurement.started_utc),
        ended_utc: timestamp(measurement.ended_utc),
        duration_seconds: numeric(measurement.duration_seconds),
        completion:
          ["completed", "incomplete"].includes(String(measurement.completion))
            ? String(measurement.completion)
            : null,
      },
  };
}
export function decodePage(
  value: unknown,
  _kind: StreamKind,
  after: number,
): ObservationPage {
  const raw = record(value), status = availability(raw);
  if (status !== "available") return { status, items: [], next_cursor: after };
  const cursor = integer(raw.next_cursor);
  if (
    !Array.isArray(raw.items) || raw.items.length > 200 || cursor === null ||
    cursor < after
  ) {
    throw new Error("Invalid observation page bounds");
  }
  const items = raw.items.map(decodeItem);
  let previous = after;
  for (const item of items) {
    if (item.position <= previous || item.position > cursor) {
      throw new Error("Invalid observation cursor progression");
    }
    previous = item.position;
  }
  return { status, items, next_cursor: cursor };
}
export function causalOrder(
  items: readonly ObservationItem[],
): ObservationItem[] {
  return [...items].sort((a, b) =>
    (a.session_generation ?? a.position) -
      (b.session_generation ?? b.position) ||
    (a.source_seq ?? a.position) - (b.source_seq ?? b.position) ||
    a.position - b.position
  );
}
export function mergePage(
  previous: ObservationPage,
  next: ObservationPage,
): ObservationPage {
  if (next.status !== "available") return next;
  const items = new Map(previous.items.map((item) => [item.position, item]));
  for (const item of next.items) items.set(item.position, item);
  // Retain a bounded window; the operator can reset to page through the prefix again.
  return {
    status: next.status,
    next_cursor: Math.max(previous.next_cursor, next.next_cursor),
    items: [...items.values()].sort((a, b) => a.position - b.position).slice(
      -1000,
    ),
  };
}
export async function boundedJson(response: Response): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`Observation request failed (HTTP ${response.status})`);
  }
  if (!response.body) throw new Error("Empty observation response");
  const reader = response.body.getReader(), chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      size += part.value.byteLength;
      if (size > 1024 * 1024) {
        throw new Error("Observation response exceeds 1 MiB");
      }
      chunks.push(part.value);
    }
  } finally {
    await reader.cancel();
  }
  const joined = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder().decode(joined));
}
export async function readObservation(
  runId: string,
  kind: "summary",
  after: number,
  groupBy: GroupBy | undefined,
  signal: AbortSignal,
  fetcher?: typeof fetch,
): Promise<ObservationSummary>;
export async function readObservation(
  runId: string,
  kind: StreamKind,
  after: number,
  groupBy: GroupBy | undefined,
  signal: AbortSignal,
  fetcher?: typeof fetch,
): Promise<ObservationPage>;
export async function readObservation(
  runId: string,
  kind: "summary" | StreamKind,
  after: number,
  groupBy: GroupBy | undefined,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<ObservationSummary | ObservationPage> {
  if (
    !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(runId) ||
    !Number.isSafeInteger(after) || after < 0
  ) {
    throw new Error("Invalid observation request");
  }
  signal.throwIfAborted();
  const query = kind === "summary"
    ? groupBy ? `?group_by=${groupBy}` : ""
    : `?after=${after}&limit=100`;
  const response = await fetcher(
    `/api/v1/runs/${encodeURIComponent(runId)}/${kind}${query}`,
    { signal, cache: "no-store" },
  );
  const value = await boundedJson(response);
  signal.throwIfAborted();
  return kind === "summary"
    ? decodeSummary(value, runId)
    : decodePage(value, kind, after);
}
