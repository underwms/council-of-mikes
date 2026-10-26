import type { EventEnvelope } from "./contracts.ts";

export function displayTimes(events: readonly EventEnvelope[]): number[] {
  const result: number[] = [];
  let segment = events[0]?.segment ?? 0;
  let offset = 0;
  let segmentMax = 0;
  for (const event of events) {
    if (event.segment !== segment) {
      offset += segmentMax;
      segmentMax = 0;
      segment = event.segment;
    }
    segmentMax = Math.max(segmentMax, event.payload.elapsed_seconds);
    result.push(offset + event.payload.elapsed_seconds);
  }
  return result;
}

export function positionAtElapsed(
  events: readonly EventEnvelope[],
  elapsed: number,
): number {
  const times = displayTimes(events);
  let position = 0;
  while (position < times.length && times[position] <= elapsed) position++;
  return position;
}

export function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${
    remainder.toFixed(1).padStart(4, "0")
  }`;
}
