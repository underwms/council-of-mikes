import { useEffect, useRef, useState } from "react";

/** Updates move downward once; old observations never cycle as invented progress. */
export default function NodeTicker({ message, source, stale, animate }: {
  message: string;
  source: string;
  stale: boolean;
  animate: boolean;
}) {
  const previous = useRef(message);
  const [outgoing, setOutgoing] = useState<string | null>(null);
  useEffect(() => {
    if (!animate) setOutgoing(null);
    if (previous.current === message) return;
    setOutgoing(animate ? previous.current : null);
    previous.current = message;
  }, [message, animate]);
  useEffect(() => {
    if (!outgoing) return;
    const timer = globalThis.setTimeout(() => setOutgoing(null), 450);
    return () => globalThis.clearTimeout(timer);
  }, [outgoing]);
  return (
    <span
      className={`node-ticker ${animate ? "node-ticker-animate" : ""}`}
      title={message}
    >
      <span className="node-ticker-caption">
        {stale ? "Last observed" : source}
      </span>
      <span
        className="node-ticker-window"
        aria-live={stale ? "off" : "polite"}
        aria-atomic="true"
      >
        {outgoing && (
          <span className="node-ticker-outgoing" aria-hidden="true">
            {outgoing}
          </span>
        )}
        <span key={message} className="node-ticker-current">{message}</span>
      </span>
    </span>
  );
}
