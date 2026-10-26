import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  type Edge,
  MarkerType,
  type Node,
  Position,
  ReactFlow,
} from "@xyflow/react";
import GraphNavigation from "./GraphNavigation.tsx";
import { type GroupId, groupNodeClass } from "./graphGroups.ts";
import PlanPanel from "./PlanPanel.tsx";
import ObservationPanel, { deliveryLabel } from "./ObservationPanel.tsx";
import Tooltip, { NODE_TOOLTIP_ID, type TooltipTarget } from "./Tooltip.tsx";
import { type EventEnvelope, parseRecording } from "./contracts.ts";
import { appendLiveEvent, parseLiveEnvelope } from "./live.ts";
import { initialRunState, type NodeVisit, projectAt } from "./reducer.ts";
import { displayTimes, formatElapsed, positionAtElapsed } from "./timeline.ts";
import { snapshotGraph } from "./topology.ts";
import { graphCanvas } from "./graphLayout.ts";
import NodeTicker from "./NodeTicker.tsx";
import {
  latestNodeNarration,
  tickerForNode,
  useNodeNarrations,
} from "./narrations.ts";
import { nodeHeight, nodeWidth, routeGraph } from "./edgeRouting.ts";
import GraphEdge from "./GraphEdge.tsx";
import { useEdgeMotion } from "./useEdgeMotion.ts";
import { HEAT_COLORS, visitBadgeStyle } from "./heatmap.ts";
import {
  edgeAppearance,
  nodeIsAnimating,
  nodeIsCurrent,
  nodeStatusLabel,
  projectEdgeHistory,
} from "./graphProgress.ts";
import { describeNode, type ObservationContext } from "./nodeActivity.ts";

const edgeTypes = { handoff: GraphEdge };
const canvas = graphCanvas(snapshotGraph);

function pretty(value: string | undefined): string {
  return value
    ? value.replaceAll("_", " ").replace(
      /\b\w/g,
      (letter) => letter.toUpperCase(),
    )
    : "Not reported";
}

function statusFor(
  visits: NodeVisit[],
  id: string,
): NodeVisit["status"] | "unobserved" {
  const visit = [...visits].reverse().find((entry) => entry.nodeId === id);
  return visit?.status ?? "unobserved";
}

export default function App() {
  const [liveRunId] = useState(() => {
    const run = new URLSearchParams(window.location.search).get("run");
    return run && /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(run) ? run : null;
  });
  const [events, setEvents] = useState<EventEnvelope[]>([]);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<GroupId | null>(null);
  const [allRoutes, setAllRoutes] = useState(false);
  const [speed, setSpeed] = useState(30);
  const [selected, setSelected] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<TooltipTarget | null>(null);
  const [focusedNode, setFocusedNode] = useState<TooltipTarget | null>(null);
  const hideTooltipTimer = useRef<number | undefined>(undefined);
  const tooltipTarget = hoveredNode ?? focusedNode;
  const [message, setMessage] = useState("Loading the supplied recording…");
  const [connection, setConnection] = useState("connecting");
  const [sourceStatus, setSourceStatus] = useState("unknown");
  const [checkpointCount, setCheckpointCount] = useState<number | null>(null);
  const [lastReceived, setLastReceived] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const positionRef = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  function keepTooltipOpen() {
    window.clearTimeout(hideTooltipTimer.current);
  }

  function leaveTooltip() {
    keepTooltipOpen();
    hideTooltipTimer.current = window.setTimeout(
      () => setHoveredNode(null),
      120,
    );
  }

  function dismissTooltip() {
    keepTooltipOpen();
    setHoveredNode(null);
    setFocusedNode(null);
  }

  useEffect(() => {
    const dismiss = () => {
      window.clearTimeout(hideTooltipTimer.current);
      setHoveredNode(null);
      setFocusedNode(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismiss();
    };
    const scroll = (event: Event) => {
      // A tall popup may scroll without losing its own hover target.
      if (
        event.target instanceof Element &&
        event.target.closest(`#${NODE_TOOLTIP_ID}`)
      ) return;
      dismiss();
    };
    window.addEventListener("keydown", escape);
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", scroll, true);
    return () => {
      window.clearTimeout(hideTooltipTimer.current);
      window.removeEventListener("keydown", escape);
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", scroll, true);
    };
  }, []);

  useEffect(() => {
    if (liveRunId) return;
    fetch("./sample-events.jsonl")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Recording fetch failed: ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        const loaded = parseRecording(text, "supplied-excerpt");
        setEvents(loaded);
        setMessage(
          `${loaded.length} recorded events loaded. Outcome beyond the excerpt is unknown.`,
        );
      })
      .catch((error: unknown) =>
        setMessage(
          error instanceof Error
            ? error.message
            : "Recording could not be loaded",
        )
      );
  }, [liveRunId]);

  useEffect(() => {
    if (!liveRunId) return;
    setMessage("Waiting for Council diagnostic events…");
    const stream = new EventSource(
      `/api/runs/${encodeURIComponent(liveRunId)}/events`,
    );
    stream.onopen = () => setConnection("connected");
    stream.onerror = () => setConnection("reconnecting");
    stream.addEventListener("record", (received) => {
      try {
        const event = parseLiveEnvelope(
          JSON.parse((received as MessageEvent).data),
        );
        if (event.payload.run_id !== liveRunId) {
          throw new Error("Unexpected run ID");
        }
        setEvents((current) => appendLiveEvent(current, event));
        setLastReceived(Date.now());
      } catch {
        setMessage("A malformed live record was rejected.");
      }
    });
    stream.addEventListener("source_status", (received) => {
      try {
        const status = JSON.parse((received as MessageEvent).data) as {
          status?: string;
        };
        if (typeof status.status === "string") setSourceStatus(status.status);
      } catch { /* ignore malformed status */ }
    });
    stream.addEventListener("reset", () => {
      setEvents([]);
      setPosition(0);
      setMessage(
        "The diagnostic recording changed; rebuilding from its available prefix.",
      );
    });
    return () => stream.close();
  }, [liveRunId]);

  useEffect(() => {
    if (liveRunId) setPosition(events.length);
  }, [events.length, liveRunId]);

  useEffect(() => {
    if (!liveRunId) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [liveRunId]);

  useEffect(() => {
    if (!liveRunId) return;
    let active = true;
    const poll = async () => {
      try {
        const response = await fetch("/api/checkpoint", { cache: "no-store" });
        const result = await response.json() as {
          status?: string;
          count?: number;
        };
        if (active) {
          setCheckpointCount(
            result.status === "available" && Number.isSafeInteger(result.count)
              ? result.count!
              : null,
          );
        }
      } catch {
        if (active) setCheckpointCount(null);
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [liveRunId]);

  const runId = liveRunId ?? events[0]?.payload.run_id ?? "unknown";
  const state = useMemo(
    () => projectAt(events, position, initialRunState(runId)),
    [events, position, runId],
  );
  const times = useMemo(() => displayTimes(events), [events]);
  const total = times.at(-1) ?? 0;
  const elapsed = position > 0 ? times[position - 1] ?? 0 : 0;
  const activeId = state.activeNode ?? state.dotNode;
  const inspectedId = selected ?? activeId;
  const inspectedVisit = [...state.visits].reverse().find((visit) =>
    visit.nodeId === inspectedId
  );
  const latestCall = inspectedVisit?.calls.at(-1);
  const narration = useNodeNarrations(liveRunId);
  const inspectedNarration = latestNodeNarration(
    inspectedId ?? "",
    state,
    narration.items,
  );
  const observationContext = useMemo<ObservationContext>(() => ({
    mode: liveRunId ? "live" : "replay",
    atEnd: position === events.length,
    connected: connection === "connected" &&
      (sourceStatus === "available" || sourceStatus === "near_capacity"),
  }), [liveRunId, position, events.length, connection, sourceStatus]);
  const edgeHistory = useMemo(
    () => projectEdgeHistory(events, position, snapshotGraph),
    [events, position],
  );

  const latestVisit = state.visits.at(-1);
  const expandedNode = tickerForNode(state.dotNode ?? "", state, [])
    ? state.dotNode
    : undefined;
  const routePaths = useMemo(() => routeGraph(snapshotGraph, expandedNode), [
    expandedNode,
  ]);
  const motionEnabled =
    (liveRunId ? observationContext.connected === true : playing) &&
    (state.segments === 0 || state.segmentOpen) &&
    latestVisit?.status !== "waiting" &&
    state.lastEvent?.payload.event !== "runtime_failed";
  const motion = useEdgeMotion(
    edgeHistory.latest,
    position,
    motionEnabled,
    `${runId}:${events[0]?.recordingId ?? "empty"}`,
  );
  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  useEffect(() => {
    if (!playing || events.length === 0) return;
    const startPosition = positionRef.current;
    const startElapsed = startPosition ? times[startPosition - 1] : 0;
    const startWall = performance.now();
    const timer = window.setInterval(() => {
      const target = startElapsed +
        (performance.now() - startWall) / 1000 * speed;
      const next = positionAtElapsed(events, target);
      if (next > positionRef.current) {
        positionRef.current = next;
        setPosition(next);
      }
      if (next >= events.length) setPlaying(false);
    }, 30);
    return () => window.clearInterval(timer);
  }, [playing, speed, events, times]);

  const nodes = useMemo<Node[]>(() =>
    snapshotGraph.nodes.map((node) => {
      const status = statusFor(state.visits, node.id);
      const visitCount = state.visits.filter((v) => v.nodeId === node.id)
        .length;
      const visited = visitCount > 0 || (state.segments > 0 &&
        (node.id === "__start__" ||
          (node.id === "__end__" &&
            [...edgeHistory.traversals.keys()].some((key) =>
              key.endsWith("->__end__")
            ))));
      const current = nodeIsCurrent(node.id, state);
      const animating = nodeIsAnimating(node.id, state, observationContext);

      const visit = [...state.visits].reverse().find((entry) =>
        entry.nodeId === node.id
      );
      const busy = visit?.calls.some((call) => call.status === "running") ??
        false;
      const ticker = tickerForNode(node.id, state, narration.items);
      const dimensions = {
        width: nodeWidth(node, expandedNode),
        height: nodeHeight(node, expandedNode),
      };
      return {
        id: node.id,
        ...dimensions,
        measured: dimensions,
        style: dimensions,
        type: "default",
        position: { x: node.x, y: node.y },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        className: `stage stage-${status} ${
          node.kind === "boundary" ? "stage-boundary" : ""
        } ${visited ? "stage-visited" : ""} ${current ? "stage-current" : ""} ${
          current && node.id === "plan_blocked" ? "stage-current-blocked" : ""
        } ${inspectedId === node.id ? "stage-selected" : ""} ${
          groupNodeClass(node.id, selectedGroup)
        }`,
        data: {
          label: (
            <>
              <span
                className="stage-visit-badge"
                data-digits={Math.min(String(visitCount).length, 4)}
                style={visitBadgeStyle(visitCount)}
                aria-label={`${visitCount} stage visits`}
              >
                {visitCount}
              </span>
              <span className="stage-title">{node.label}</span>
              <span className="stage-detail">
                {busy && animating
                  ? "Model call in flight"
                  : nodeStatusLabel(status)}
              </span>
              {visit && ticker && node.kind !== "boundary" && (
                <NodeTicker
                  key={`${node.id}:${visit.segment}:${visit.ordinal}`}
                  message={ticker.message}
                  source={ticker.source}
                  stale={!current ||
                    (liveRunId !== null &&
                      (narration.status !== "available" ||
                        !observationContext.connected))}
                  animate={current && animating &&
                    (!liveRunId || narration.status === "available")}
                />
              )}
              {animating && (
                <span className="stage-activity" aria-hidden="true">
                  <span className="stage-activity-ball" />
                  <span className="stage-activity-shadow" />
                </span>
              )}
            </>
          ),
        },
        draggable: false,
        selectable: true,
        focusable: true,
        domAttributes: {
          "aria-describedby": tooltipTarget?.nodeId === node.id
            ? NODE_TOOLTIP_ID
            : undefined,
        },
      };
    }), [
    state,
    narration,
    expandedNode,
    liveRunId,
    edgeHistory,
    observationContext,
    inspectedId,
    tooltipTarget?.nodeId,
    selectedGroup,
  ]);

  const edges = useMemo<Edge[]>(
    () =>
      snapshotGraph.edges.filter((edge) =>
        allRoutes || edge.kind !== "conditional" ||
        edgeHistory.traversals.has(`${edge.source}->${edge.target}`)
      ).map((edge) => {
        const appearance = edgeAppearance(
          edgeHistory.traversals.get(`${edge.source}->${edge.target}`),
          edgeHistory.totalTraversals,
          (state.segments === 0 || state.segmentOpen) &&
            latestVisit?.status !== "waiting" &&
            state.lastEvent?.payload.event !== "runtime_failed" &&
            (!liveRunId || observationContext.connected === true),
        );
        const moving = motion?.source === edge.source &&
          motion?.target === edge.target;
        return {
          id: `${edge.source}->${edge.target}`,
          source: edge.source,
          target: edge.target,
          type: "handoff",
          label: edge.label,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 16,
            height: 16,
            color: appearance.endColor,
          },
          className: `${
            appearance.visited ? "edge-visited" : "edge-unobserved"
          } ${moving ? "edge-traversing" : ""}`,
          style: {
            stroke: appearance.endColor,
            strokeWidth: moving ? 4.5 : appearance.width,
          },
          data: {
            moving,
            routePath: routePaths.get(`${edge.source}->${edge.target}`)?.path,
            motionKey: motion?.cursor,
            gradientStart: appearance.visited
              ? appearance.startColor
              : undefined,
            gradientEnd: appearance.visited ? appearance.endColor : undefined,
          },
        };
      }),
    [
      motion,
      routePaths,
      edgeHistory,
      allRoutes,
      state,
      latestVisit,
      liveRunId,
      observationContext,
    ],
  );

  async function importFile(file: File | undefined) {
    if (!file) return;
    setPlaying(false);
    try {
      if (file.size > 1024 * 1024) {
        throw new Error("Recording exceeds the 1 MiB import limit");
      }
      const loaded = parseRecording(await file.text(), file.name);
      setEvents(loaded);
      setPosition(0);
      positionRef.current = 0;
      setSelected(null);
      dismissTooltip();
      setMessage(`${loaded.length} events imported from ${file.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Import failed");
    }
  }

  function seek(next: number) {
    setPlaying(false);
    setPosition(next);
    positionRef.current = next;
  }

  return (
    <div className="shell">
      <header className="header">
        <div>
          <p className="eyebrow">COUNCIL / ORCHESTRATION</p>
          <h1>Execution, made visible.</h1>
          <p className="subtitle">
            Follow the graph. Inspect the work inside each stage.
          </p>
        </div>
        <div className="header-actions">
          <span className="mode-pill">
            <span className="mode-dot" />{" "}
            {liveRunId ? `LIVE · ${connection.toUpperCase()}` : "REPLAY MODE"}
          </span>
          {!liveRunId && (
            <>
              <button
                type="button"
                className="button"
                onClick={() => inputRef.current?.click()}
              >
                Import JSONL
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".jsonl,application/json"
                hidden
                onChange={(event) => void importFile(event.target.files?.[0])}
              />
            </>
          )}
        </div>
      </header>

      <div className="workspace">
        <section className="canvas-panel" aria-label="Execution graph">
          <div className="section-heading">
            <span>EXECUTION GRAPH</span>
            <span>{state.visits.length} stage visits observed</span>
          </div>
          <div className="graph-navigation">
            <GraphNavigation
              selectedGroup={selectedGroup}
              onGroupChange={setSelectedGroup}
              onNavigate={(id) => {
                const node = snapshotGraph.nodes.find((entry) =>
                  entry.id === id
                )!;
                document.querySelector(".graph-scroll")?.scrollTo({
                  left: Math.max(0, node.x * canvas.scale - 32),
                  behavior: "instant",
                });
                setSelected(id);
              }}
            />
            <label>
              <input
                type="checkbox"
                checked={allRoutes}
                onChange={(event) => setAllRoutes(event.target.checked)}
              />{" "}
              Show all conditional routes
            </label>
          </div>
          <div
            className="graph-scroll"
            aria-label="Execution graph, scroll horizontally for more stages"
            onFocusCapture={(event) => {
              const element = event.target.closest<HTMLElement>(
                ".react-flow__node",
              );
              if (element?.dataset.id) {
                setFocusedNode({ nodeId: element.dataset.id, element });
              }
            }}
            onBlurCapture={() => setFocusedNode(null)}
          >
            <div
              className="graph-wrap"
              style={{ width: canvas.width, height: canvas.height }}
            >
              <ReactFlow
                nodes={nodes}
                edges={edges}
                edgeTypes={edgeTypes}
                defaultViewport={{ x: 16, y: 16, zoom: canvas.scale }}
                minZoom={canvas.scale}
                maxZoom={canvas.scale}
                zoomOnScroll={false}
                zoomOnPinch={false}
                zoomOnDoubleClick={false}
                panOnScroll={false}
                panOnDrag={false}
                preventScrolling={false}
                nodesDraggable={false}
                nodesConnectable={false}
                edgesReconnectable={false}
                elementsSelectable
                onNodeMouseEnter={(event, node) => {
                  keepTooltipOpen();
                  if (event.currentTarget instanceof HTMLElement) {
                    setHoveredNode({
                      nodeId: node.id,
                      element: event.currentTarget,
                    });
                  }
                }}
                onNodeMouseLeave={leaveTooltip}
                onNodeClick={(_event, node) => setSelected(node.id)}
                proOptions={{ hideAttribution: true }}
              >
                <Background color="#b7cad4" gap={22} size={1} />
              </ReactFlow>
            </div>
          </div>
          {tooltipTarget && (
            <Tooltip
              target={tooltipTarget}
              state={state}
              context={observationContext}
              tickerMessage={tickerForNode(
                tooltipTarget.nodeId,
                state,
                narration.items,
              )?.message}
              onMouseEnter={keepTooltipOpen}
              onMouseLeave={leaveTooltip}
            />
          )}
          <div className="legend">
            <span>
              <i className="legend-dot active" /> Active
            </span>
            <span>
              <i className="legend-dot visited" /> Visited
            </span>
            <span>
              <i className="legend-dot blocked" /> Blocked
            </span>
            <span>
              <i className="legend-dot" /> Not observed
            </span>
            <span
              className="heat-legend"
              aria-label="Visit badges: pale red at 1, full red at 10 or more; number shows total visits"
            >
              Visit badges: 1
              <i
                className="heat-ramp"
                aria-hidden="true"
                style={{
                  background: `linear-gradient(90deg, ${
                    HEAT_COLORS.join(", ")
                  })`,
                }}
              />
              10+
            </span>
            <span
              className="route-legend"
              aria-label="Traversed routes: older muted teal to recent strong teal; unused routes are dashed"
            >
              Routes: older <i className="route-ramp" aria-hidden="true" />{" "}
              recent
            </span>
            <span>
              {allRoutes
                ? "All conditional routes shown"
                : "Unvisited recovery and scope-return routes hidden"}{" "}
              · scroll horizontally for all stages
            </span>
          </div>
        </section>

        {liveRunId && (
          <ObservationPanel
            key={liveRunId}
            runId={liveRunId}
            connected={observationContext.connected === true}
          />
        )}

        <details
          className="inspector accordion-section"
          aria-label="Selected node activity"
        >
          <summary>Node activity</summary>
          <div className="section-heading">
            <span>NODE ACTIVITY</span>
            <span>{selected ? "SELECTED" : "FOLLOWING"}</span>
          </div>
          <div className="inspector-grid">
            <div className="inspector-summary">
              <h2>
                {snapshotGraph.nodes.find((node) => node.id === inspectedId)
                  ?.label ?? "Runtime"}
              </h2>
              <p
                className={`inspector-status status-${
                  inspectedVisit?.status ?? "unobserved"
                }`}
              >
                {inspectedVisit
                  ? nodeStatusLabel(inspectedVisit.status)
                  : "Not observed"}
              </p>
              <div className="inspector-note">
                {describeNode(
                  inspectedId ?? "runtime",
                  state,
                  observationContext,
                ).summary}
              </div>
              {inspectedNarration && (
                <p className="inspector-note">{inspectedNarration.message}</p>
              )}
              {liveRunId && narration.status !== "available" && (
                <p className="observation-caption">
                  Narration unavailable; node text uses event summaries.
                </p>
              )}
              {selected && (
                <button
                  type="button"
                  className="button follow"
                  onClick={() => setSelected(null)}
                >
                  Follow active node
                </button>
              )}
            </div>
            <details className="inspector-technical technical-details">
              <summary>Node technical details</summary>
              <div className="operation-card">
                <span className="micro-label">LATEST OPERATION</span>
                <strong>{pretty(latestCall?.operation)}</strong>
                <span>
                  {latestCall?.status === "running"
                    ? "Model call in flight"
                    : latestCall
                    ? `Call ${latestCall.number} ${latestCall.status}`
                    : "No model activity recorded"}
                </span>
              </div>
              <dl className="facts">
                <div>
                  <dt>Role</dt>
                  <dd>{pretty(latestCall?.role)}</dd>
                </div>
                <div>
                  <dt>Model call</dt>
                  <dd>{latestCall ? `#${latestCall.number}` : "—"}</dd>
                </div>
                <div>
                  <dt>Inspection round</dt>
                  <dd>{inspectedVisit?.inspectionRound ?? "—"}</dd>
                </div>
                <div>
                  <dt>Stage visits</dt>
                  <dd>
                    {state.visits.filter((visit) =>
                      visit.nodeId === inspectedId
                    )
                      .length}
                  </dd>
                </div>
              </dl>
            </details>
          </div>
          {/* Plan payloads are not part of the diagnostic event contract yet. */}
          <details className="technical-details">
            <summary>Plan data</summary>
            <PlanPanel plan={null} />
          </details>
          {state.notices.length > 0 && (
            <div className="notices">{state.notices.at(-1)}</div>
          )}
          {inspectedVisit?.status === "failed" && (
            <details className="error-panel">
              <summary>Recorded error details</summary>
              <div className="section-heading">
                <span>ERROR DETAILS</span>
              </div>
              <pre>
                {JSON.stringify(
                  events.find((e) =>
                    e.payload.stage === inspectedId &&
                    (e.payload.event === "node_failed" ||
                      e.payload.event === "call_failed")
                  )?.payload ?? "No failure event found",
                  null,
                  2
                )}
              </pre>
            </details>
          )}
        </details>
      </div>

      <details className="run-information accordion-section">
        <summary>Run information</summary>
        <div className="run-strip">
          <span>
            RUN{" "}
            <strong>
              {runId === "unknown" ? "—" : `${runId.slice(0, 12)}…`}
            </strong>
          </span>
          <span>
            GRAPH{" "}
            <strong>
              {snapshotGraph.graphVersion.replaceAll("-", " ").toUpperCase()}
            </strong>
          </span>
          <span className="run-time">
            {liveRunId
              ? `SOURCE ${sourceStatus.replaceAll("_", " ").toUpperCase()}`
              : (
                <>
                  {formatElapsed(elapsed)} <span>/ {formatElapsed(total)}</span>
                </>
              )}
          </span>
        </div>
      </details>

      <details className="delivery-strip accordion-section">
        <summary>Delivery status</summary>
        <div aria-label="Reported delivery status">
          <strong>
            {liveRunId
              ? "Last reported delivery"
              : "Delivery at selected event"}
          </strong>
          <span>
            Functional completion:{" "}
            <b>{deliveryLabel(state.functionalComplete)}</b>
          </span>
          <span>
            PR ready: <b>{deliveryLabel(state.prReady)}</b>
          </span>
        </div>
      </details>

      <details className="playback accordion-section">
        <summary>
          {liveRunId ? "Live stream & diagnostics" : "Recording & playback"}
        </summary>
        <div className="playback-top">
          <div>
            <p className="eyebrow">
              {liveRunId ? "LIVE OBSERVATION" : "RECORDING"}
            </p>
            <strong>
              {liveRunId
                ? "Council diagnostic stream"
                : events.length
                ? "Console diagnostic excerpt"
                : "No recording"}
            </strong>
          </div>
          <span className="outcome">
            Task outcome: {pretty(state.taskStatus)}
          </span>
        </div>
        {liveRunId
          ? (
            <div className="live-status">
              {connection === "connected" ? "Connected" : "Reconnecting"} ·{" "}
              {lastReceived === null
                ? "Waiting for the first event"
                : `Last event received ${
                  Math.floor((now - lastReceived) / 1000)
                }s ago`}
            </div>
          )
          : (
            <>
              <div className="controls-row">
                <button
                  type="button"
                  className="button button-primary"
                  disabled={!events.length ||
                    position >= events.length && !playing}
                  onClick={() => setPlaying((value) => !value)}
                >
                  {playing ? "Pause" : "Play recording"}
                </button>
                <button
                  type="button"
                  className="button"
                  disabled={!events.length || position >= events.length}
                  onClick={() => seek(Math.min(position + 1, events.length))}
                >
                  Next event
                </button>
                <button
                  type="button"
                  className="button"
                  disabled={!events.length}
                  onClick={() => seek(0)}
                >
                  Restart
                </button>
                <label className="speed-label">
                  Speed{" "}
                  <select
                    value={speed}
                    onChange={(event) => setSpeed(Number(event.target.value))}
                  >
                    <option value={1}>1×</option>
                    <option value={10}>10×</option>
                    <option value={30}>30×</option>
                  </select>
                </label>
                <span className="event-count">
                  {position} / {events.length} events
                </span>
              </div>
              <label className="seek-label" htmlFor="event-position">
                <span>Recording position</span>
                <span>{formatElapsed(elapsed)}</span>
              </label>
              <input
                id="event-position"
                className="seek"
                type="range"
                min={0}
                max={events.length}
                value={position}
                onChange={(event) => seek(Number(event.target.value))}
                aria-label="Recording event position"
              />
            </>
          )}
        <div className="message" role="status">{message}</div>
        <details className="technical-details stream-diagnostics">
          <summary>Stream technical details</summary>
          {liveRunId && (
            <p>
              {events.length} events observed · Checkpoint commits:{" "}
              {checkpointCount ?? "unavailable"}
            </p>
          )}
          <details className="last-event">
            <summary>Last structured event</summary>
            <pre>{state.lastEvent ? JSON.stringify(state.lastEvent.payload, null, 2) : "No event applied yet."}</pre>
          </details>
        </details>
      </details>
    </div>
  );
}
