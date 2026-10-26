export const HEAT_COLORS = [
  "#fff2f2",
  "#ffd6d6",
  "#ffbaba",
  "#ff9e9e",
  "#ff8282",
  "#ff6666",
  "#ff4a4a",
  "#ff2e2e",
  "#ff1212",
  "#ff0000",
] as const;

type VisitBadgeStyle = {
  backgroundColor: string;
  color: string;
};

// Visits come from the projected state's visit count, not model-call activity.
export function visitBadgeStyle(visits: number): VisitBadgeStyle {
  if (visits < 1) return { backgroundColor: "#edf2f6", color: "#496374" };
  const level = Math.min(visits, HEAT_COLORS.length);
  return {
    backgroundColor: HEAT_COLORS[level - 1],
    color: "#280808",
  };
}
