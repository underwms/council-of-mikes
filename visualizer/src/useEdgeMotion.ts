import { useEffect, useRef, useState } from "react";
import type { Transition } from "./graphProgress.ts";

/** The expiry belongs to the motion, not to the stream event that triggered it. */
export function useEdgeMotion(
  latest: Transition | undefined,
  position: number,
  enabled: boolean,
  identity: string,
): Transition | null {
  const [motion, setMotion] = useState<Transition | null>(null);
  const previous = useRef({ position, identity });
  useEffect(() => {
    const before = previous.current;
    previous.current = { position, identity };
    if (
      !enabled || !latest || before.identity !== identity ||
      position < before.position
    ) {
      setMotion(null);
    } else if (
      latest.position > before.position && latest.position <= position
    ) {
      setMotion(latest);
    }
  }, [latest, position, enabled, identity]);
  useEffect(() => {
    if (!motion) return;
    const timer = globalThis.setTimeout(() => setMotion(null), 680);
    return () => globalThis.clearTimeout(timer);
  }, [motion]);
  return enabled && previous.current.identity === identity ? motion : null;
}
