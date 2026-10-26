/** Read-only version-one projections. No checkpoint payloads or arbitrary fields escape. */
import { DatabaseSync } from "node:sqlite";

type Fact = Record<string, unknown>;
const kinds: Record<string, string[] | null> = {
  events: null,
  export: null,
  milestones: [
    "node_finished",
    "node_failed",
    "approval_waiting",
    "planning_blocked",
    "delivery_state",
    "recovery_dispatched",
    "recovery_resolved",
  ],
  calls: ["call_succeeded", "call_failed"],
  commands: ["verification_finished"],
  sessions: null,
};
const tokenKeys = [
  "input_tokens",
  "output_tokens",
  "total_tokens",
  "cached_input_tokens",
];
const events = new Set([
  "run_started",
  "run_finished",
  "node_started",
  "node_finished",
  "node_failed",
  "call_started",
  "call_succeeded",
  "call_failed",
  "approval_waiting",
  "planning_blocked",
  "delivery_state",
  "verification_started",
  "verification_finished",
  "runtime_failed",
  "recovery_opened",
  "recovery_admitted",
  "recovery_dispatched",
  "recovery_resolved",
  "recovery_failed",
  "recovery_stopped",
  "recovery_human_input",
  "recovery_rejected",
]);
for (
  const event of [
    "human_input_received",
    "cli_attempt_failed",
    "inspection_round_started",
    "inspection_budget_reached",
    "plan_preflight_rejected",
    "plan_review_rejected",
    "verification_rejected",
    "inspection_read_rejected",
    "tool_failed",
    "resource_cleanup_observed",
  ]
) events.add(event);
const stages = new Set([
  "runtime",
  "model",
  "roadmap",
  "roadmap_review",
  "architect",
  "plan_review",
  "plan_revision",
  "strategy_reset",
  "plan_blocked",
  "worker",
  "prover",
  "phase_complete",
  "investigation",
  "gatekeeper",
  "final_review",
  "finished_change_review",
  "governor",
  "arbiter",
  "recovery_admit",
  "recovery_dispatch",
  "recovery_result",
  "requirements_gate",
  "intake_draft",
]);
stages.add("requirements_reopen");
stages.add("proof_refresh");
const dimensions = new Set([
  "role",
  "operation",
  "provider",
  "requested_model",
  "reported_model",
]);
const identifier = /^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$/;
const count = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 &&
  value <= 1e12;
const record = (value: unknown): Fact =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Fact
    : {};

function safeComparison(value: unknown): Fact {
  const input = record(value), output: Fact = {};
  for (
    const key of [
      "engine_graph_sha256",
      "requirements_sha256",
      "accepted_plan_sha256",
      "obligations_sha256",
    ]
  ) {
    output[key] = typeof input[key] === "string" &&
        /^[a-f0-9]{64}$/.test(input[key] as string)
      ? input[key]
      : null;
  }
  output.distribution_version =
    typeof input.distribution_version === "string" &&
      /^[0-9][A-Za-z0-9.+-]{0,63}$/.test(input.distribution_version)
      ? input.distribution_version
      : null;
  output.policy = Object.fromEntries(
    Object.entries(record(input.policy)).filter(([key, value]) =>
      ["orchestration", "integrity", "governance", "recovery"].includes(key) &&
      typeof value === "number" && Number.isSafeInteger(value) && value >= 0 &&
      value <= 4
    ),
  );
  output.roles = Object.fromEntries(
    Object.entries(record(input.roles)).filter(([role]) =>
      ["orchestrator", "coder", "investigator", "reviewer"].includes(role)
    ).map(([role, raw]) => {
      const settings = record(raw), result: Fact = {};
      for (const key of ["provider", "requested_model"]) {
        if (
          typeof settings[key] === "string" &&
          identifier.test(settings[key] as string) &&
          !/^(sk-|bearer|aiza|[A-Za-z]:)/i.test(settings[key] as string)
        ) result[key] = settings[key];
      }
      if (count(settings.configured_timeout_seconds)) {
        result.configured_timeout_seconds = settings.configured_timeout_seconds;
      }
      return [role, result];
    }),
  );
  return output;
}

function safe(value: unknown): Fact | null {
  const raw = record(value);
  if (
    typeof raw.event !== "string" || !events.has(raw.event) ||
    typeof raw.timestamp !== "string" ||
    !Number.isFinite(Date.parse(raw.timestamp))
  ) return null;
  const output: Fact = {
    event: raw.event,
    timestamp: raw.timestamp,
    stage: stages.has(String(raw.stage)) ? raw.stage : "runtime",
  };
  if (raw.comparison !== undefined) {
    output.comparison = safeComparison(raw.comparison);
  }
  for (const key of ["call", "task_index", "command_index", "phase_index"]) {
    if (count(raw[key]) && Number.isSafeInteger(raw[key])) {
      output[key] = raw[key];
    }
  }
  if (count(raw.elapsed_seconds)) output.elapsed_seconds = raw.elapsed_seconds;
  for (const key of ["functional_complete", "pr_ready"]) {
    if (typeof raw[key] === "boolean") output[key] = raw[key];
  }
  if (
    typeof raw.run_status === "string" && /^[A-Z_]{1,32}$/.test(raw.run_status)
  ) output.run_status = raw.run_status;
  if (
    [
      "GRAPH_EVIDENCE_INVALID",
      "DELIVERY_BOUNDARY_NOT_MET",
      "FINAL_REVIEW_NON_TEXT_UNSUPPORTED",
      "REQUIREMENTS_DRAFT_REJECTED",
      "CODEX_TOOL_FAILED",
      "PROPOSAL_FORMAT_INVALID",
      "VERIFICATION_FAILED",
      "READINESS_FAILED",
      "CLI_TIMEOUT",
    ].includes(String(raw.code))
  ) output.code = raw.code;
  const accounting: Fact = {};
  const source = record(raw.accounting);
  for (
    const key of [
      "provider",
      "requested_model",
      "returned_model",
      "cli_reported_model",
      "operation",
      "role",
    ]
  ) {
    const value = source[key];
    if (
      typeof value === "string" && identifier.test(value) &&
      !/^(sk-|bearer|aiza|[A-Za-z]:)/i.test(value)
    ) accounting[key] = value;
  }
  for (
    const key of [
      "duration_seconds",
      "effective_timeout_seconds",
      "request_bytes",
    ]
  ) if (count(source[key])) accounting[key] = source[key];
  accounting.usage = Object.fromEntries(
    tokenKeys.filter((key) =>
      count(record(source.usage)[key]) &&
      Number.isSafeInteger(record(source.usage)[key])
    ).map((key) => [key, record(source.usage)[key]]),
  );
  if (raw.accounting !== undefined) output.accounting = accounting;
  const measured = record(raw.measurement), measurement: Fact = {};
  for (const key of ["execution_id", "command_sha256"]) {
    if (
      typeof measured[key] === "string" &&
      /^[a-f0-9]{64}$/.test(measured[key] as string)
    ) measurement[key] = measured[key];
  }
  for (const key of ["started_utc", "ended_utc"]) {
    if (
      typeof measured[key] === "string" &&
      Number.isFinite(Date.parse(measured[key] as string))
    ) measurement[key] = measured[key];
  }
  if (count(measured.duration_seconds)) {
    measurement.duration_seconds = measured.duration_seconds;
  }
  if (["completed", "incomplete"].includes(String(measured.completion))) {
    measurement.completion = measured.completion;
  }
  if (raw.measurement !== undefined) output.measurement = measurement;
  return output;
}

function interpret(fact: Fact | undefined): Fact | null {
  if (!fact) return null;
  if (fact.code === "DELIVERY_BOUNDARY_NOT_MET") {
    return {
      state: "quality_blocked",
      message:
        "Functional behavior is verified; required PR-readiness evidence remains unresolved.",
      timestamp: fact.timestamp,
    };
  }
  let state = "recorded_activity",
    message =
      `Recorded ${fact.stage} activity; next work depends on remaining checks.`;
  if (
    ["COMPLETED", "FAILED", "STOPPED", "INTERRUPTED"].includes(
      String(fact.run_status),
    )
  ) {
    state = String(fact.run_status).toLowerCase();
    message = fact.run_status === "COMPLETED"
      ? "Functional delivery completed; PR readiness follows separately recorded quality evidence."
      : "Execution ended with its recorded outcome and limitations preserved.";
  } else if (
    ["approval_waiting", "planning_blocked"].includes(String(fact.event)) ||
    ["PLAN_BLOCKED", "REQUIREMENTS_WAITING"].includes(String(fact.run_status))
  ) {
    state = "waiting_for_human";
    message =
      "Waiting for explicit human input; silence does not approve this gate.";
  } else if (
    (fact.event === "node_finished" && fact.stage === "worker") ||
    (fact.event === "delivery_state" && fact.stage === "worker" &&
      fact.run_status === "TESTING")
  ) {
    state = "verification_pending";
    message = "Coding turn finished; independent verification is pending.";
  } else if (
    fact.event === "delivery_state" && fact.stage === "prover" &&
    ["EXECUTING", "GATEKEEPER_AUDIT"].includes(String(fact.run_status))
  ) {
    state = "verification_passed";
    message =
      "Independent task verification passed; phase and final delivery checks still apply.";
  } else if (
    fact.event === "node_failed" && fact.code === "GRAPH_EVIDENCE_INVALID"
  ) {
    state = "stale_proof";
    message =
      "Execution proof is absent or stale; this alone does not establish a product defect.";
  } else if (["node_failed", "runtime_failed"].includes(String(fact.event))) {
    state = "failure_recorded";
    message =
      "A failure was recorded; subsequent recovery or a terminal outcome may follow.";
  } else if (String(fact.event).startsWith("recovery_")) {
    state = "recovering";
    message =
      "A recovery event was recorded; recommendation and execution remain distinct.";
  } else if (fact.event === "run_finished") {
    state = "session_ended";
    message = "This process session ended; run completion is not implied.";
  }
  return { state, message, timestamp: fact.timestamp };
}

function usageSummary(calls: Fact[]): Fact {
  const coverage = Object.fromEntries(
    tokenKeys.map((key) => [
      key,
      calls.filter((c) => key in record(c.usage)).length,
    ]),
  );
  const usage: Fact = Object.fromEntries(
    tokenKeys.map((key) => [
      `reported_${key}`,
      coverage[key]
        ? calls.reduce(
          (total, call) => total + Number(record(call.usage)[key] ?? 0),
          0,
        )
        : null,
    ]),
  );
  usage.field_attempt_counts = coverage;
  usage.missing_attempts =
    calls.filter((c) => !Object.keys(record(c.usage)).length).length;
  usage.partial_attempts =
    calls.filter((c) =>
      Object.keys(record(c.usage)).length &&
      !tokenKeys.slice(0, 3).every((k) => k in record(c.usage))
    ).length;
  usage.measured_attempts = calls.length - Number(usage.missing_attempts);
  return usage;
}

export function readObservations(
  path: string,
  runId: string,
  kind: string,
  after = 0,
  limit = 100,
  groupBy?: string,
): Fact {
  if (groupBy !== undefined && !dimensions.has(groupBy)) {
    throw new RangeError("Invalid accounting dimension");
  }
  if (
    !["summary", ...Object.keys(kinds)].includes(kind) ||
    !Number.isSafeInteger(after) || after < 0 || !Number.isSafeInteger(limit) ||
    limit < 1 || limit > 200
  ) throw new RangeError("Invalid observation query");
  let db: DatabaseSync | undefined;
  try {
    const info = Deno.lstatSync(path);
    if (info.isSymlink || !info.isFile || info.size > 128 * 1024 * 1024) {
      return { version: 1, status: "unavailable" };
    }
    db = new DatabaseSync(path, { readOnly: true, timeout: 100 });
    db.exec("PRAGMA query_only=ON");
    const version = db.prepare("SELECT version FROM observation_meta LIMIT 2")
      .all();
    if (version.length !== 1 || version[0].version !== 1) {
      return { version: 1, status: "unsupported_schema" };
    }
    if (kind === "sessions") {
      const rows = db.prepare(
        "SELECT generation AS position,session_id FROM observation_sessions WHERE run_id=? AND generation>? ORDER BY generation LIMIT ?",
      ).all(runId, after, limit);
      return {
        version: 1,
        items: rows,
        next_cursor: rows.at(-1)?.position ?? after,
      };
    }
    if (kind === "summary") {
      const rows = db.prepare(
        "SELECT e.payload FROM observation_events e JOIN observation_sessions s USING(run_id,session_id) WHERE e.run_id=? ORDER BY s.generation,e.source_seq LIMIT 8192",
      ).all(runId);
      const facts = rows.map((row) => safe(JSON.parse(String(row.payload))))
        .filter((fact): fact is Fact => fact !== null);
      const waiting = new Map<string, string>(), waits: number[] = [];
      for (const fact of facts) {
        const stage = String(fact.stage);
        if (
          ["approval_waiting", "planning_blocked"].includes(
            String(fact.event),
          ) && !waiting.has(stage)
        ) waiting.set(stage, String(fact.timestamp));
        else if (fact.event === "human_input_received" && waiting.has(stage)) {
          const duration = (Date.parse(String(fact.timestamp)) -
            Date.parse(waiting.get(stage)!)) / 1000;
          waiting.delete(stage);
          if (duration >= 0) waits.push(duration);
        }
      }
      const calls = facts.filter((f) =>
        ["call_succeeded", "call_failed"].includes(String(f.event))
      ).map((f) => record(f.accounting));
      const durations = calls.map((c) => c.duration_seconds).filter(count).sort(
        (a, b) => a - b,
      );
      const usage = usageSummary(calls);
      const grouped = new Map<unknown, Fact[]>();
      if (groupBy) {
        for (const call of calls) {
          const key = groupBy === "reported_model"
            ? call.returned_model ?? call.cli_reported_model ?? null
            : call[groupBy] ?? null;
          grouped.set(key, [...(grouped.get(key) ?? []), call]);
        }
      }
      const middle = Math.floor(durations.length / 2);
      return {
        version: 1,
        run_id: runId,
        event_count: facts.length,
        coverage: facts.length ? "prospective_events_only" : "unavailable",
        liveness: "unknown",
        current: interpret(
          facts.findLast((f) => f.event !== "run_finished") ?? facts.at(-1),
        ),
        usage,
        calls: {
          count: calls.length,
          duration_population: durations.length,
          median_seconds: !durations.length
            ? null
            : durations.length % 2
            ? durations[middle]
            : (durations[middle - 1] + durations[middle]) / 2,
          duration_semantics:
            "inclusive; do not add to node or command durations",
        },
        wall_time_seconds: null,
        unclassified_gaps: true,
        completed_session_durations_seconds: facts.filter((f) =>
          f.event === "run_finished" && count(f.elapsed_seconds)
        ).map((f) => f.elapsed_seconds),
        history_capped: facts.length >= 8192,
        human_wait_seconds: waits.length
          ? waits.reduce((a, b) => a + b, 0)
          : null,
        completed_human_waits: waits.length,
        unmatched_human_waits: waiting.size,
        group_by: groupBy ?? null,
        groups: [...grouped].slice(0, 64).map(([value, calls]) => ({
          value,
          attempts: calls.length,
          usage: usageSummary(calls),
        })),
        groups_truncated: grouped.size > 64,
        comparison: facts.findLast((f) =>
          f.comparison !== undefined
        )?.comparison ?? null,
        interpretation: {
          method: "event_derived",
          model_enabled: false,
          model_calls: 0,
        },
      };
    }
    const filter = kinds[kind];
    const sql =
      "SELECT position,e.session_id,source_seq,event_id,payload,s.generation FROM observation_events e JOIN observation_sessions s USING(run_id,session_id) WHERE e.run_id=? AND position>?" +
      (filter ? ` AND event IN (${filter.map(() => "?").join(",")})` : "") +
      " ORDER BY position LIMIT ?";
    const rows = db.prepare(sql).all(runId, after, ...(filter ?? []), limit);
    return {
      version: 1,
      items: rows.flatMap((row) => {
        const fact = safe(JSON.parse(String(row.payload)));
        return fact
          ? [{
            position: row.position,
            session_id: row.session_id,
            session_generation: row.generation,
            source_seq: row.source_seq,
            event_id: row.event_id,
            ...fact,
            method: "event_derived",
            ...(kind === "milestones" ? { explanation: interpret(fact) } : {}),
          }]
          : [];
      }),
      next_cursor: rows.at(-1)?.position ?? after,
    };
  } catch {
    return { version: 1, status: "unavailable" };
  } finally {
    db?.close();
  }
}
