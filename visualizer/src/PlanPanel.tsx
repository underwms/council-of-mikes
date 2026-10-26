type ImplementationPlan = {
  title: string;
  steps: { text: string; status: "pending" | "in_progress" | "completed" }[];
};

type PlanPanelProps = {
  plan: ImplementationPlan | null;
};

export default function PlanPanel({ plan }: PlanPanelProps) {
  if (!plan) {
    return null;
  }

  return (
    <div className="plan-panel">
      <div className="section-heading"><span>{plan.title}</span></div>
      <ul>
        {plan.steps.map((step, index) => (
          <li key={index} className={`plan-step--${step.status}`}>
            <span>{step.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
