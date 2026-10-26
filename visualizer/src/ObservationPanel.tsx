import * as React from "react";
import { causalOrder, mergePage, readObservation } from "./observations.ts";
import type {
  GroupBy,
  ObservationItem,
  ObservationPage,
  ObservationSummary,
  StreamKind,
  Usage,
} from "./observations.ts";

const show = (value: string | number | null | undefined) => value ?? "Unknown";
const seconds = (value: number | null | undefined) =>
  value === null || value === undefined
    ? "Unknown"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}s`;
export const deliveryLabel = (value: boolean | null) =>
  value === null ? "Unknown" : value ? "Yes" : "No";
const readable = (value: string | null | undefined) =>
  value ? value.replaceAll("_", " ") : "Unknown";
const tokenFields = [
  "input_tokens",
  "output_tokens",
  "total_tokens",
  "cached_input_tokens",
] as const;
const { useEffect, useState } = React;

function UsageFacts({ usage }: { usage: Usage }) {
  return (
    <dl className="observation-facts">
      {tokenFields.map((key) => (
        <div key={key}>
          <dt>Reported {readable(key)}</dt>
          <dd>
            {show(usage[`reported_${key}`])}{" "}
            <small>
              ({show(usage.field_attempt_counts[key])} measured attempts)
            </small>
          </dd>
        </div>
      ))}
      <div>
        <dt>Measured attempts</dt>
        <dd>{show(usage.measured_attempts)}</dd>
      </div>
      <div>
        <dt>Missing attempts</dt>
        <dd>{show(usage.missing_attempts)}</dd>
      </div>
      <div>
        <dt>Partial attempts</dt>
        <dd>{show(usage.partial_attempts)}</dd>
      </div>
    </dl>
  );
}

export function ObservationSummaryView(
  { summary, error, connected, children }: {
    summary: ObservationSummary | null;
    error: string | null;
    connected: boolean;
    children?: React.ReactNode;
  },
) {
  if (!summary || summary.status !== "available" || error) {
    return (
      <>
        <p className="observation-notice" role="status">
          {error || summary
            ? "Observations unavailable"
            : "Loading observations…"}
          {error
            ? `: ${error}`
            : summary?.status === "unsupported_schema"
            ? ": unsupported storage schema."
            : ". Historical observation coverage may be absent."}
        </p>
        <details className="technical-details">
          <summary>Technical details</summary>
          {children}
        </details>
      </>
    );
  }
  return (
    <>
      {!connected && (
        <p className="observation-notice">
          Live updates unavailable. All facts below are last observed; current
          execution is unknown.
        </p>
      )}
      <div className="observation-overview">
        <div className="observation-progress">
          <span className="micro-label">
            LAST OBSERVED · {readable(summary.current?.state)}
          </span>
          <h2>
            {summary.current?.message ?? "No progress observations recorded."}
          </h2>
          <p>{show(summary.current?.timestamp)}</p>
        </div>
        <details className="technical-details summary-technical">
          <summary>Technical details</summary>
          <details className="technical-details">
            <summary>Observation coverage</summary>
            <dl className="observation-facts">
              <div>
                <dt>Coverage</dt>
                <dd>{readable(summary.coverage)}</dd>
              </div>
              <div>
                <dt>Liveness</dt>
                <dd>{readable(summary.liveness)}</dd>
              </div>
              <div>
                <dt>Recorded events</dt>
                <dd>{show(summary.event_count)}</dd>
              </div>
              <div>
                <dt>History capped</dt>
                <dd>{deliveryLabel(summary.history_capped)}</dd>
              </div>
            </dl>
          </details>
          <div>
            <h3>Reported usage</h3>
            <UsageFacts usage={summary.usage} />
          </div>
          <div>
            <h3>Timing & coverage</h3>
            <dl className="observation-facts">
              <div>
                <dt>Wall time</dt>
                <dd>{seconds(summary.wall_time_seconds)}</dd>
              </div>
              <div>
                <dt>Call attempts</dt>
                <dd>{show(summary.calls.count)}</dd>
              </div>
              <div>
                <dt>Median call duration</dt>
                <dd>
                  {seconds(summary.calls.median_seconds)}{" "}
                  <small>
                    ({show(summary.calls.duration_population)} measured)
                  </small>
                </dd>
              </div>
              <div>
                <dt>Completed human wait</dt>
                <dd>{seconds(summary.human_wait_seconds)}</dd>
              </div>
              <div>
                <dt>Completed / open waits</dt>
                <dd>
                  {show(summary.completed_human_waits)} /{" "}
                  {show(summary.unmatched_human_waits)}
                </dd>
              </div>
              <div>
                <dt>Unclassified session gaps</dt>
                <dd>{deliveryLabel(summary.unclassified_gaps)}</dd>
              </div>
            </dl>
            <p className="observation-caption">
              Node, call and command durations overlap; do not add them as wall
              time. Unreported measurements remain unknown.
            </p>
          </div>
          <details className="observation-identities">
            <summary>Run identity & configured models</summary>
            <dl className="observation-facts">
              <div>
                <dt>Installed distribution</dt>
                <dd>{show(summary.comparison?.distribution_version)}</dd>
              </div>
              <div>
                <dt>Executed graph SHA256</dt>
                <dd>{show(summary.comparison?.engine_graph_sha256)}</dd>
              </div>
              <div>
                <dt>Requirements SHA256</dt>
                <dd>{show(summary.comparison?.requirements_sha256)}</dd>
              </div>
              <div>
                <dt>Accepted plan SHA256</dt>
                <dd>{show(summary.comparison?.accepted_plan_sha256)}</dd>
              </div>
              <div>
                <dt>Obligations SHA256</dt>
                <dd>{show(summary.comparison?.obligations_sha256)}</dd>
              </div>
              {Object.entries(summary.comparison?.policy ?? {}).map((
                [key, version],
              ) => (
                <div key={key}>
                  <dt>{key} policy</dt>
                  <dd>{version}</dd>
                </div>
              ))}
              {Object.entries(summary.comparison?.roles ?? {}).map((
                [role, settings],
              ) => (
                <div key={role}>
                  <dt>{role} configuration</dt>
                  <dd>
                    {show(settings.provider)} · requested{" "}
                    {show(settings.requested_model)} · deadline{" "}
                    {seconds(settings.configured_timeout_seconds)}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="observation-caption">
              Configured choices are separate from per-attempt reported models
              and effective deadlines. The displayed graph is a source snapshot.
            </p>
          </details>
          <div className="observation-settings">{children}</div>
        </details>
      </div>
    </>
  );
}

function ObservationDetail({ item }: { item: ObservationItem }) {
  const call = item.accounting, command = item.measurement;
  return (
    <li>
      <div className="observation-event-title">
        <strong>{readable(item.event ?? "process_session")}</strong>
        <span>#{item.position} · {readable(item.stage)}</span>
      </div>
      <p className="activity-explanation">
        {item.explanation?.message ??
          `${readable(item.event ?? "process_session")} · ${
            readable(item.stage)
          }. No further explanation was recorded.`}
      </p>
      <details className="technical-details event-technical">
        <summary>Event technical details</summary>
        <p className="observation-caption">
          {show(item.timestamp)} · Session {show(item.session_id)} · generation
          {" "}
          {show(item.session_generation)} · source sequence{" "}
          {show(item.source_seq)}
        </p>
        {item.run_status && <p>Reported status: {readable(item.run_status)}</p>}
        {(item.functional_complete !== null || item.pr_ready !== null) && (
          <p>
            Functional completion: {deliveryLabel(item.functional_complete)}
            {" "}
            · PR ready: {deliveryLabel(item.pr_ready)}
          </p>
        )}
        {item.code && <p>Diagnostic: {item.code}</p>}
        {call && (
          <dl className="observation-facts observation-call">
            <div>
              <dt>Call / role / operation</dt>
              <dd>
                {show(item.call)} · {show(call.role)} · {show(call.operation)}
              </dd>
            </div>
            <div>
              <dt>Provider</dt>
              <dd>{show(call.provider)}</dd>
            </div>
            <div>
              <dt>Requested model</dt>
              <dd>{show(call.requested_model)}</dd>
            </div>
            <div>
              <dt>Returned model</dt>
              <dd>{show(call.returned_model)}</dd>
            </div>
            <div>
              <dt>CLI reported model</dt>
              <dd>{show(call.cli_reported_model)}</dd>
            </div>
            <div>
              <dt>Duration / effective deadline</dt>
              <dd>
                {seconds(call.duration_seconds)} /{" "}
                {seconds(call.effective_timeout_seconds)}
              </dd>
            </div>
            {tokenFields.map((field) => (
              <div key={field}>
                <dt>Reported {readable(field)}</dt>
                <dd>{show(call.usage[field])}</dd>
              </div>
            ))}
          </dl>
        )}
        {command && (
          <dl className="observation-facts">
            <div>
              <dt>Execution ID</dt>
              <dd>{show(command.execution_id)}</dd>
            </div>
            <div>
              <dt>Command SHA256</dt>
              <dd>{show(command.command_sha256)}</dd>
            </div>
            <div>
              <dt>UTC start / end</dt>
              <dd>{show(command.started_utc)} / {show(command.ended_utc)}</dd>
            </div>
            <div>
              <dt>Duration / completion</dt>
              <dd>
                {seconds(command.duration_seconds)} / {show(command.completion)}
              </dd>
            </div>
          </dl>
        )}
        <details>
          <summary>Safe event identity</summary>
          <p className="observation-caption">{show(item.event_id)}</p>
        </details>
      </details>
    </li>
  );
}

function DetailStream({ runId, kind }: { runId: string; kind: StreamKind }) {
  const [page, setPage] = useState<ObservationPage | null>(null);
  const [after, setAfter] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPage, setLastPage] = useState<ObservationPage | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let next: ReturnType<typeof globalThis.setTimeout> | undefined;
    let nextCursor = after;
    const timeout = globalThis.setTimeout(() => controller.abort(), 8000);
    setBusy(true);
    setError(null);
    void readObservation(runId, kind, after, undefined, controller.signal).then(
      (result) => {
        if (!active) return;
        if (result.status === "available") nextCursor = result.next_cursor;
        setLastPage(result);
        setPage((current) =>
          after === 0 || !current ? result : mergePage(current, result)
        );
      },
    ).catch((failure: unknown) => {
      if (active) {
        setError(
          failure instanceof Error
            ? failure.message
            : "Observation request failed",
        );
      }
    }).finally(() => {
      globalThis.clearTimeout(timeout);
      if (active) {
        setBusy(false);
        next = globalThis.setTimeout(() => {
          setAfter(nextCursor);
          setRefresh((value) => value + 1);
        }, 5000);
      }
    });
    return () => {
      active = false;
      controller.abort();
      globalThis.clearTimeout(timeout);
      globalThis.clearTimeout(next);
    };
  }, [runId, kind, after, refresh]);

  function downloadPage() {
    if (!lastPage || lastPage.status !== "available") return;
    const url = URL.createObjectURL(
      new Blob([
        JSON.stringify(
          { version: 1, run_id: runId, kind, ...lastPage },
          null,
          2,
        ),
      ], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `council-${runId}-${kind}-${lastPage.next_cursor}.json`;
    link.click();
    globalThis.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="observation-stream" aria-busy={busy}>
      <details className="technical-details">
        <summary>History controls & export</summary>
        <div className="observation-toolbar">
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={() => {
              setPage(null);
              setLastPage(null);
              setAfter(0);
              setRefresh((value) => value + 1);
            }}
          >
            First page
          </button>
          <button
            type="button"
            className="button"
            disabled={busy || !page || page.status !== "available"}
            onClick={() => {
              setAfter(page!.next_cursor);
              setRefresh((value) => value + 1);
            }}
          >
            Load next / check for new
          </button>
          <button
            type="button"
            className="button"
            disabled={busy || !!error || lastPage?.status !== "available"}
            onClick={downloadPage}
          >
            Export this page
          </button>
          <span className="observation-caption">
            {busy
              ? "Loading…"
              : `${page?.items.length ?? 0} retained · cursor ${
                page?.next_cursor ?? 0
              }`}
          </span>
        </div>
        <p className="observation-caption">
          Causal order by session generation and source sequence. Pagination
          uses ingestion positions. Retains up to 1,000 items; export each page
          to preserve a longer history.
        </p>
      </details>
      {error && (
        <p className="observation-notice" role="status">
          Details unavailable: {error}. Retained items below are last observed.
        </p>
      )}
      {page && page.status !== "available" && (
        <p className="observation-notice">
          Details unavailable: {readable(page.status)}.
        </p>
      )}
      {!busy && page?.status === "available" && !lastPage?.items.length && (
        <p className="observation-caption">
          No further observations on this page.
        </p>
      )}
      <ol className="observation-events">
        {causalOrder(page?.items ?? []).map((item) => (
          <ObservationDetail key={item.position} item={item} />
        ))}
      </ol>
    </div>
  );
}

export default function ObservationPanel(
  { runId, connected }: { runId: string; connected: boolean },
) {
  const [summary, setSummary] = useState<ObservationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [groupBy, setGroupBy] = useState<GroupBy>("role");
  const [kind, setKind] = useState<StreamKind>("milestones");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    let next: ReturnType<typeof globalThis.setTimeout> | undefined;
    let timeout: ReturnType<typeof globalThis.setTimeout> | undefined;
    let controller: AbortController | undefined;
    setSummary(null);
    setError(null);
    const poll = async () => {
      controller = new AbortController();
      timeout = globalThis.setTimeout(() => controller?.abort(), 8000);
      try {
        const result = await readObservation(
          runId,
          "summary",
          0,
          groupBy,
          controller.signal,
        );
        if (active) {
          setSummary(result);
          setError(null);
        }
      } catch (failure) {
        if (active) {
          setSummary(null);
          setError(
            failure instanceof Error
              ? failure.message
              : "Observation request failed",
          );
        }
      } finally {
        globalThis.clearTimeout(timeout);
        if (active) next = globalThis.setTimeout(() => void poll(), 5000);
      }
    };
    void poll();
    return () => {
      active = false;
      controller?.abort();
      globalThis.clearTimeout(timeout);
      globalThis.clearTimeout(next);
    };
  }, [runId, groupBy, refresh]);
  return (
    <>
      <details
        className="observation-panel accordion-section activity-accordion"
        open
      >
        <summary>Activity explained</summary>
        <DetailStream key={`${runId}:${kind}`} runId={runId} kind={kind} />
      </details>
      <details
        className="observation-panel accordion-section observations-accordion"
        aria-label="Run observations"
      >
        <summary>What’s happening</summary>
        <div className="section-heading">
          <span>What’s happening</span>
          <span>Current run · refreshes every 5s · read only</span>
        </div>
        <ObservationSummaryView
          summary={summary}
          error={error}
          connected={connected}
        >
          <div className="observation-toolbar">
            <label>
              Group usage by{" "}
              <select
                value={groupBy}
                onChange={(event) => setGroupBy(event.target.value as GroupBy)}
              >
                {([
                  "role",
                  "operation",
                  "provider",
                  "requested_model",
                  "reported_model",
                ] as const).map((value) => (
                  <option key={value} value={value}>{readable(value)}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="button"
              onClick={() => setRefresh((value) => value + 1)}
            >
              Refresh summary
            </button>
          </div>
          {!!summary?.groups.length && !error && (
            <details className="observation-groups">
              <summary>
                Usage by {readable(groupBy)}
                {summary.groups_truncated ? " (first 64 groups)" : ""}
              </summary>
              <div className="observation-group-grid">
                {summary.groups.map((group, index) => (
                  <div key={index}>
                    <h3>
                      {show(group.value)} · {show(group.attempts)} attempts
                    </h3>
                    <UsageFacts usage={group.usage} />
                  </div>
                ))}
              </div>
            </details>
          )}
          <h3>Choose technical event stream</h3>
          <div className="observation-toolbar">
            <label>
              Detail stream{" "}
              <select
                value={kind}
                onChange={(event) => setKind(event.target.value as StreamKind)}
              >
                {([
                  "milestones",
                  "calls",
                  "commands",
                  "sessions",
                  "events",
                  "export",
                ] as const).map((value) => (
                  <option key={value} value={value}>{readable(value)}</option>
                ))}
              </select>
            </label>
          </div>
        </ObservationSummaryView>
      </details>
    </>
  );
}
