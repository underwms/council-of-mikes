import { graphGroups, type GroupId } from "./graphGroups.ts";

export default function GraphNavigation(
  { selectedGroup, onGroupChange, onNavigate }: {
    selectedGroup: GroupId | null;
    onGroupChange: (group: GroupId | null) => void;
    onNavigate: (nodeId: string) => void;
  },
) {
  return (
    <div
      className="graph-group-buttons"
      role="group"
      aria-label="Highlight stage group"
    >
      {graphGroups.map((group) => (
        <button
          type="button"
          className={`button group-button group-${group.id}`}
          key={group.id}
          aria-pressed={selectedGroup === group.id}
          onClick={() => {
            const next = selectedGroup === group.id ? null : group.id;
            onGroupChange(next);
            if (next) onNavigate(group.anchor);
          }}
        >
          <span className="group-swatch" aria-hidden="true" />
          {group.label}
        </button>
      ))}
    </div>
  );
}
