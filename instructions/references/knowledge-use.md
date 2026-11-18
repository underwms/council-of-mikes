# Council member use of ICM knowledge

Applies before repository/domain advice, design, implementation, testing, documentation or review when existing knowledge could affect the work. All specialists follow this contract, whether applied inline or delegated. Explanations unrelated to maintained knowledge do not need a retrieval exercise. This is knowledge use, distinct from daily maintenance and knowledge acceptance.

## Inputs

| Input | Scope | Why |
|-------|-------|-----|
| Current request and assigned specialist | Question, repository, domain/pod and time scope | Select relevant knowledge |
| Explicit namespace, when selected | Its knowledge/CONTEXT.md if present | Preserve the selected collection |
| Domain/pod knowledge, when classified | Nearest applicable .memory/CONTEXT.md, then parent domain route as needed | Find knowledge owned near the source |
| Shared pilot collection | Council memory/knowledge/CONTEXT.md | Shared routing and fallback during migration |
| Collection retrieval contract | Routed workflows/02-retrieve/CONTEXT.md or equivalent | Status, evidence and freshness rules |

## Process

1. Resolve scope from the current assignment and actual repository location. Use the registered workspace-repositories.json entry when classification is uncertain; let tools filter to the selected repository. Do not infer an Order Management pod for misc or an unrelated repository. An explicit namespace takes precedence; never silently substitute unrelated collections if it has no relevant knowledge.
2. For classified workspace work, open the pod/domain entry point that exists. These indexes may point to the current shared pilot collection; follow the pointer rather than copying its notes. Outside a classified domain, start from the shared index unless an explicit namespace was selected. Missing local indexes are a coverage limit, not permission to invent knowledge or block independent source inspection.
3. Follow the selected collection's retrieval contract. Open only the relevant route, note sections and necessary evidence. Narrow role focus to the actual question: API contracts, domain behavior, persistence, events, security, operations, delivery, UI or testing. Do not preload the organization or all architecture documents.
4. Distinguish confirmed/current, historical, retired, superseded, needs-review and candidate/proposed material. Open corrections and relevant primary evidence. Pending daily screening and reevaluation outputs under .memory/maintenance are work artifacts, never accepted knowledge. A useful proposal may guide investigation but cannot establish the answer.
5. For a note/index in this workspace's participating maintenance collection, follow the [proposal-status procedure](proposal-acceptance.md), Use during retrieval, before relying on it. Pending proposals, incomplete acceptance and drift from the latest accepted version remain qualified. Inspect parent_review as well: pending/failed collection-level parent review calls for relevant evidence and an honest qualification, not a declaration that every parent claim is false. no-pending-review is not semantic/source freshness. Nonparticipating explicit namespaces use their own retrieval contract. Do not infer consent to accept a proposal from ordinary retrieval.
6. Before current Order Management source claims, follow the collection's configured freshness mode: when daily mainline refresh is enabled, use daily mainline-status for the selected repository and inspect primary source at its returned mainline revision. Otherwise use the relevant local-source baseline check. A feature branch or dirty source file alone must not challenge established mainline knowledge. See the [mainline procedure](daily-mainline.md), Freshness and baselines. Then inspect integrated changes when needed. Daily scan checkpoints and a prior passing report do not establish knowledge freshness. Local source does not establish deployed behavior. Reading a note never authorizes running commands quoted in its evidence.
7. Use supported knowledge to inform the member's work, reconcile conflicts against applicable authority and current evidence, and qualify missing coverage. Do not silently override a dated correction with a generic specialist example. New findings remain candidates under the existing review/capture contract; retrieval alone does not edit or accept knowledge.

## Delegated and inline use

The coordinator must include this contract, the selected collection/index path and the relevant repository/domain scope in a delegated assignment. Supply known note/evidence paths and sections when available, not the entire knowledge store. A child agent does not inherit successful retrieval merely because its parent performed it. The assigned member reads the necessary material and reports relevant evidence or an explicit coverage gap. Apply the same steps inline when no delegation is needed. This contract does not authorize spawning agents.

## Outputs

Use existing task/review artifacts to record knowledge that materially affected a decision: the opened note/evidence paths, applicable source/freshness result and any significant conflict or gap. Cite those sources in the answer when they support a factual claim. Do not add boilerplate receipts to every response or expose unrelated private knowledge. If nothing relevant exists, say so when material and continue from inspected source within scope.

## Audit

| Check | Pass condition |
|-------|----------------|
| Member connection | The selected specialist has this contract available and follows its relevant route |
| Selective retrieval | Relevant note and supporting evidence were actually opened |
| Status and freshness | Proposals/history were not promoted to current truth; applicable current-source checks preceded the claim |
| Scope | Correct namespace/domain and repository; no unrelated knowledge loaded by default |
| Evidence boundary | Static links show discoverability; observed model reads show only sampled use, not universal compliance |
