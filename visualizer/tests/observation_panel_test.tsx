import { renderToStaticMarkup } from "react-dom/server";
import { ObservationSummaryView } from "../src/ObservationPanel.tsx";
import { decodeSummary } from "../src/observations.ts";

function contains(html: string, text: string) {
  if (!html.includes(text)) throw new Error(`Missing UI text: ${text}`);
}
Deno.test("observation panel: missing storage discloses unavailable observations", () => {
  const summary = decodeSummary({ version: 1, status: "unavailable" }, "run");
  const html = renderToStaticMarkup(
    <ObservationSummaryView summary={summary} error={null} connected />,
  );
  contains(html, "Observations unavailable");
  if (html.includes("0 tokens")) throw new Error("Invented usage");
});
Deno.test("observation panel: waiting, missing usage and identities stay distinct", () => {
  const summary = decodeSummary({
    version: 1,
    run_id: "run",
    current: {
      state: "waiting_for_human",
      message: "Waiting for explicit human input.",
      timestamp: "2026-10-25T12:00:00Z",
    },
    comparison: {
      distribution_version: "0.2.43",
      engine_graph_sha256: "a".repeat(64),
    },
    coverage: "prospective_events_only",
    liveness: "unknown",
    unclassified_gaps: true,
    usage: {
      reported_input_tokens: 0,
      measured_attempts: 1,
      missing_attempts: 2,
      partial_attempts: 1,
    },
  }, "run");
  const html = renderToStaticMarkup(
    <ObservationSummaryView summary={summary} error={null} connected={false} />,
  );
  for (
    const text of [
      "Waiting for explicit human input.",
      "Live updates unavailable",
      "Unknown",
      "0.2.43",
      "Executed graph SHA256",
      "Measured attempts",
      "Missing attempts",
      "Partial attempts",
      "do not add",
      "Unclassified",
    ]
  ) contains(html, text);
});
Deno.test("observation panel: transport failure does not present stale progress", () => {
  const html = renderToStaticMarkup(
    <ObservationSummaryView
      summary={null}
      error="Observation request failed (HTTP 503)"
      connected
    />,
  );
  contains(html, "HTTP 503");
  contains(html, "Observations unavailable");
});
