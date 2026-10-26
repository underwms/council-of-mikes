import { useId } from "react";
import { BaseEdge, type EdgeProps, getSmoothStepPath } from "@xyflow/react";

function EdgeTrail(props: EdgeProps & { path: string }) {
  const gradientId = useId();
  const moving = props.data?.moving === true;
  const start = props.data?.gradientStart;
  const end = props.data?.gradientEnd;
  const gradient = typeof start === "string" && typeof end === "string";
  return (
    <>
      {gradient && (
        <defs>
          <linearGradient
            id={gradientId}
            gradientUnits="userSpaceOnUse"
            x1={props.sourceX}
            y1={props.sourceY}
            x2={props.targetX}
            y2={props.targetY}
          >
            <stop offset="0%" stopColor={start} />
            <stop offset="100%" stopColor={end} />
          </linearGradient>
        </defs>
      )}
      <BaseEdge
        id={props.id}
        path={props.path}
        markerEnd={props.markerEnd}
        style={gradient
          ? { ...props.style, stroke: `url(#${gradientId})` }
          : props.style}
      />
      {moving && (
        <circle key={String(props.data?.motionKey)} r="6" className="traveller">
          <animateMotion path={props.path} dur="0.65s" />
          <animate
            attributeName="opacity"
            values="1;1;0"
            keyTimes="0;0.95;1"
            dur="0.65s"
            fill="freeze"
          />
        </circle>
      )}
    </>
  );
}

export default function GraphEdge(props: EdgeProps) {
  const path = typeof props.data?.routePath === "string"
    ? props.data.routePath
    : getSmoothStepPath(props)[0];
  return <EdgeTrail {...props} path={path} />;
}
