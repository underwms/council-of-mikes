# Council LangGraph visualizer side build

This directory packages the browser viewer for the Council LangGraph engine. The
workspace handoff is under
`temp/.todo/ai_orchestration/langgraph-visualizer-handoff/`. The viewer does not
modify or run the Council engine. The supplied 37-event diagnostic excerpt is
loaded on startup; a local JSONL file can be imported through the browser
without uploading it.

## Run locally

From this directory on Windows:

```powershell
npm.cmd ci
deno task test
deno task check
deno task build
deno task serve
```

Open the loopback URL printed by Vite for replay. `deno task dev` runs the
development server. The browser offers play, pause, next event, restart,
1×/10×/30× speed, event seeking, horizontal graph scrolling, node selection, and
follow active node. The graph scale is fixed and the minimap is hidden.

Each node has a small circular visit badge overlapping its upper-left corner.
The badge shows the exact visit count: neutral at zero, pale red on the first
visit, and increasingly red with each revisit. Color saturates at 10 visits; the
number keeps increasing. Counts follow the selected replay position or live run,
so seeking backwards reduces heat and restarting replay clears it. Model calls
and duplicate live delivery do not add visits. START/END boundaries have no
diagnostic stage visits and show zero.

Visited nodes retain a blue-gray fill (`#bdcfdc`), matching the screenshot's
Roadmap nodes, and completed status labels say **Visited**. The current node
uses the screenshot's pale blue (`#eff7fc`) and a teal outline/glow. Current
Plan Blocked uses red instead; after leaving it, its fill becomes visited
blue-gray. Failure borders and detailed status remain available independently of
the fill. Observed START/END boundaries also receive the visited fill.

A small ball bounces inside the current active node. It stops when that node
finishes, waits, the run ends/fails, live observation becomes unavailable, or
replay reaches an incomplete excerpt's end. Reduced-motion preferences show a
static ball. Replay otherwise shows activity at the selected position.

Traversed edges have solid directional teal gradients and matching arrowheads.
Recent handoffs have stronger color and line weight; older handoffs fade to
muted blue-gray while remaining visibly traversed. Waiting, terminal, and
disconnected observations clear teal emphasis. Unused routes are faint and dashed. Recency follows handoff
order, so pauses and elapsed-clock resets do not distort the history. A repeat
handoff refreshes its route. Only observed handoffs allowed by the topology are
marked; resumes do not connect separate segments or manufacture another START
route. A session ending for approval does not traverse END. END requires an
explicit terminal status, completed delivery, or a failed node followed by session
closure; unknown excerpt boundaries are not inferred. Seeking backwards or restarting rebuilds this history too.

Travelling dots expire independently of incoming call events and clear at
observation boundaries. Batched updates use the latest observed handoff, including
approval-to-Roadmap and self-loops. Reduced-motion preferences hide travellers.
Routes use a fixed obstacle-aware orthogonal grid, with separate phase-return
lanes and congestion penalties to spread return paths. Stage bounds are fixed at
190 by 164 pixels so paths avoid titles and activity indicators. Route identities
remain stable when conditional routes appear.

The current stage contains a four-line activity ticker. Persisted model
narration arrives through the read-only `/api/v1/runs/RUN_ID/narrations` endpoint.
A new blurb enters from above and replaces the old one downward once; reduced
motion replaces it immediately. Full text is available in the node's title and
inspector. Narration is tied to its source node visit, so a delayed result does
not move into a different node or overwrite a later visit. Completed/disconnected
observations are labelled **Last observed**. Missing narration uses explicitly
labelled event summaries. Old recordings do not acquire invented model history.
Only the current stage expands to 190 by 164 pixels; other stages shrink to
150 by 96 pixels. START/END retain their smaller bounds.
React Flow receives these dimensions explicitly, including its measurement
metadata, so unchanged nodes remain visible across activity refreshes while
browser resize measurements catch up.
Routing shortens port stubs in narrow corridors to avoid neighboring nodes.

Hover any node, including START and END, for its purpose and observed activity.
The popup shows the latest operation, role, model call, inspection round, and
visit timing when reported. Tab to a node for the same information; Escape
dismisses it. The popup stays open while hovered and stays inside the window.
Scrolling the graph or resizing the window dismisses it. Hovering does not
change inspector selection or replay position.

Popup activity follows incoming live events or the selected replay position.
Unvisited nodes say no activity is recorded. An incomplete excerpt, ended run,
or unavailable live stream does not confirm that an old open call is still
running. Model internals and plan payloads are not present in the diagnostic
event contract; the viewer displays only the available metadata.

For live observation, build first, then launch the read-only companion against
one selected run:

```powershell
deno task live --run-id <run-id> --diagnostics-dir 'C:\Users\munderwood\.council\memory\engine\diagnostics' --checkpoint-db 'C:\Users\munderwood\.council\memory\engine\council_checkpoints.db'
```

Open the printed `127.0.0.1` URL. It follows that run's JSONL file over SSE,
including records appended after the page loads. The optional SQLite path adds a
read-only checkpoint count for that run. The service never invokes the graph or
reads checkpoint payloads. The `--run-id` value must match the Council
diagnostic filename stem.

The real excerpt ends with Plan review active and reviewer call 12 still open.
Its task outcome is unknown. `run_finished` without an allowlisted `task_status`
also leaves outcome unknown.

## Current boundary

The graph is a labelled Council 0.2.43 source snapshot of `council/graph.py`,
refreshed on 2026-10-25. It includes all 23 registered stages plus START and
END: requirements drafting, exact human approval and reopening; phased planning
and delivery; the single arbiter with recovery admission, dispatch and results;
proof refresh and independent finished-change review. Finalization polish
remains a worker assignment rather than an invented graph stage. Older phased
and legacy routes remain visible for historical recordings.

Use the Requirements, Planning & delivery, Recovery and Final checks buttons to
navigate the horizontally scrolling graph and highlight every stage in that
group: purple for Requirements, blue for Planning & delivery, orange for
Recovery, and green for Final checks. The selected button stays pressed; clicking
it again clears the highlight. Other stages dim slightly, while current,
waiting, failed and selected stages keep their visibility. Status borders,
visit badges, animation and keyboard focus remain independent of group fills.
START and END have no group color. Shared conditional failure, recovery
and scope-return routes appear when observed; select **Show all conditional
routes** to inspect dormant paths too. Waiting stages have amber styling and do
not animate. Selection, tooltips, visit heat and edge history include new
stages. Reported functional completion and PR readiness are separate; replay
displays only facts available at its selected event. Requirements reopening
clears obsolete readiness. Missing facts are unknown.

This is not an engine-exported topology digest or proof of a historical run's
graph identity. The snapshot label is separate from installed-distribution and
executed graph identities in telemetry. `src/topology.ts` must be refreshed when
routes change; tests compare its node set to the Python registrations and cover
the requirements, recovery and review routes. Older supplied recordings leave
new stages unobserved.

The read-only JSONL tail service and live connection state are present. The
installed Council CLI now opens this viewer automatically for interactive task
runs and resumes; `--no-viewer` disables it. A generated topology manifest and
full browser visual acceptance remains separate verification. No provider calls,
diagnostic writes, or execution controls are present here. The SQLite reader
selects only `COUNT(*)` for the configured thread ID and empty namespace, opens
the database read-only, and closes it after each request.

The import parser enforces a 1 MiB file limit, a 16 KiB record limit, required
event fields, one run ID, and an allowlist for terminal task statuses. Unknown
payload fields are discarded before display.

## Live run observations

The graph stays expanded. **Activity explained** sits immediately underneath it
in an accordion that starts open. **What’s happening**, **Node activity**,
**Run information**, **Delivery status**, and **Live stream & diagnostics** sit
below it and start collapsed. Each section can open independently. Collapsing
activity preserves its loaded events and automatic updates. Replay keeps its
recording controls in a collapsed **Recording & playback** section.

Live mode also reads the existing `/api/v1/runs/RUN_ID/` GET endpoints. The
summary refreshes every five seconds, with an eight-second request timeout and
cancellation when its selection changes. **What’s happening** leads with the
current plain-language explanation and an **Activity explained** history. These
reuse the existing sanitized event explanations without extra model calls;
events lacking explanations say that no further explanation was recorded.
Usage, timing, identities, event metadata, stream selection and export controls
start collapsed under technical details. Node operation metrics, plan data,
delivery flags and raw stream diagnostics are also expandable. It retains deterministic last-observed
progress, coverage/liveness, measured/missing/partial usage populations, timing,
human waits, and separate distribution, executed graph, requirements and
accepted-plan hashes. Usage can be grouped by role, operation, provider,
requested model or reported model. Requested models never fill missing reported
model values. Inclusive timings are not added as wall time; absent measurements
remain unknown. A disconnected stream qualifies all progress as last observed,
and HTTP/storage/schema failures remain explicit.

Choose milestones, calls, commands, sessions, events or export in the detail
selector under **Technical details → Choose technical event stream**. The activity history checks
for new records every five seconds after each request completes, advancing its
ingestion cursor and preserving the retained window. **Load next / check for new** reads 100 records after the ingestion
cursor; **First page** clears the retained window. Events display in causal
session/sequence order, including delayed observations. At most 1,000 decoded
items are retained. **Export this page** downloads the current sanitized, typed
page projection, with run identity and ingestion cursor. Preserve every page for
longer comparisons; the existing backend export endpoint remains available for
its complete safe projection. Neither export includes private checkpoint,
requirements or source content. Calls show requested/returned/CLI-reported
models independently; commands show measured UTC endpoints, duration and
execution identity where reported.

Replay does not fetch live aggregate observations. Live observation storage is
prospective: historical recordings/checkpoints do not manufacture missing
history. The panel observes the run; it cannot approve requirements, resume,
repair or dispatch work.

## Verification

`deno task test` covers the real excerpt, unknown terminal outcome, repeated
visits across resume, duplicate delivery, import validation, timeline bursts,
the graph snapshot, partial JSONL lines, append delivery, and SSE reconnect.
`deno task check` includes browser and service typechecking. `deno task build`
bundles the production page. Live verification uses an inert copied recording;
no live provider run is needed.

The test task includes React DOM tests in jsdom for pagination, refresh,
grouping, stream changes, failures and stale-response cancellation, alongside
static display, client contract and existing backend/SSE tests. Its explicit
import map uses the same pinned React packages as the browser build.
`@types/node` and jsdom packages are development dependencies. Simulated DOM
checks do not establish pixel layout or browser rendering quality.
