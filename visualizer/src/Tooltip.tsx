import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  describeNode,
  type ObservationContext,
  readable,
} from "./nodeActivity.ts";
import type { RunState } from "./reducer.ts";
import { formatElapsed } from "./timeline.ts";
import { snapshotGraph } from "./topology.ts";
import { nodeStatusLabel } from "./graphProgress.ts";

export type TooltipTarget = { nodeId: string; element: HTMLElement };

type TooltipProps = {
  target: TooltipTarget;
  state: RunState;
  context: ObservationContext;
  tickerMessage: string | undefined;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
};

export const NODE_TOOLTIP_ID = "node-activity-tooltip";

export default function Tooltip(
  { target, state, context, tickerMessage, onMouseEnter, onMouseLeave }:
    TooltipProps,
) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const activity = describeNode(target.nodeId, state, context);
  const visit = activity.visit;
  const call = visit?.calls.at(-1);
  const label =
    snapshotGraph.nodes.find((node) => node.id === target.nodeId)?.label ??
      readable(target.nodeId);

  useLayoutEffect(() => {
    const popup = ref.current;
    if (!popup) return; // Defensive: the portal ref is normally attached before layout effects.
    const anchor = target.element.getBoundingClientRect();
    const box = popup.getBoundingClientRect();
    const margin = 12;
    const gap = 10;
    const right = anchor.right + gap;
    const left = right + box.width <= window.innerWidth - margin
      ? right
      : anchor.left - gap - box.width;
    setPosition({
      left: Math.max(
        margin,
        Math.min(left, window.innerWidth - box.width - margin),
      ),
      top: Math.max(
        margin,
        Math.min(anchor.top, window.innerHeight - box.height - margin),
      ),
    });
  }, [target, tickerMessage, visit, call]);

  return createPortal(
    <div
      ref={ref}
      id={NODE_TOOLTIP_ID}
      role="tooltip"
      className="node-tooltip"
      style={position}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="node-tooltip-heading">
        <h3>{label}</h3>
        <span className={`node-tooltip-status status-${activity.status}`}>
          {nodeStatusLabel(activity.status)}
        </span>
      </div>
      <p className="node-tooltip-purpose">{activity.purpose}</p>
      {tickerMessage !== undefined && (
        <p className="node-tooltip-summary">{tickerMessage}</p>
      )}
      <dl className="node-tooltip-facts">
        {call && (
          <>
            <div>
              <dt>Latest operation</dt>
              <dd>{readable(call.operation)}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{readable(call.role)}</dd>
            </div>
            <div>
              <dt>Model call</dt>
              <dd>
                #{call.number} · {call.status === "running"
                  ? "No result recorded"
                  : readable(call.status)}
              </dd>
            </div>
          </>
        )}
        {visit?.inspectionRound !== undefined && (
          <div>
            <dt>Inspection round</dt>
            <dd>
              {visit.inspectionRound}
              {visit.remainingRounds !== undefined
                ? ` · ${visit.remainingRounds} remaining`
                : ""}
            </dd>
          </div>
        )}
        {visit && (
          <>
            <div>
              <dt>Visit started</dt>
              <dd>{formatElapsed(visit.startedAt)}</dd>
            </div>
            {visit.finishedAt !== undefined && (
              <div>
                <dt>Visit finished</dt>
                <dd>{formatElapsed(visit.finishedAt)}</dd>
              </div>
            )}
          </>
        )}
        <div>
          <dt>Stage visits</dt>
          <dd>{activity.visitCount}</dd>
        </div>
      </dl>
      <span className="node-tooltip-caption">
        {context.mode === "live"
          ? "Latest observed activity"
          : "Activity at replay position"} · Esc to dismiss
      </span>
    </div>,
    document.body,
  );
}
