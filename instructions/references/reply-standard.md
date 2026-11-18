# Council reply standard

The user approved this two-hook design on 2026-11-17. Its scope is replies to the user in supported Council clients. The shared rule definition is [reply-standard.json](reply-standard.json). The implementation is [council-reply-standard.mjs](../../scripts/council-reply-standard.mjs). This is a Council implementation of the described approach, not Kem's unpublished code.

## Operation

| Client | Before the reply | After the reply |
|---|---|---|
| Codex | UserPromptSubmit adds rules and same-chat feedback | Stop scores last_assistant_message |
| Gemini CLI | BeforeAgent adds rules and same-chat feedback | AfterAgent scores prompt_response |

The prompt hook repeats a compact set of rules without a manual skill call. The completion hook saves a short assessment. The next prompt receives that assessment. The hooks do not block, retry, rewrite replies or start another model. They do not prevent all context loss or prove that a model followed the rules.

Use short sentences, simple words, active voice where possible and consistent technical names. Keep technical facts accurate. Preserve exact code, commands, paths, URLs, identifiers and quoted source text. Apply the writing rules to the surrounding explanation.

## Advisory checks

The checker reports descriptive sentences over 25 words, numbered procedural sentences over 20 words, and the five explicit word-choice entries in the shared JSON. It starts at 100 and subtracts five points per finding, down to zero. Findings contain rule IDs and counts. This is a local heuristic score, not an official ASD-STE100 metric.

The checker ignores fenced code, inline code, block quotes, double-quoted text, URLs and Windows paths. It counts Markdown link labels as prose. Sentence splitting and procedure detection are limited. A numbered descriptive list can produce a false warning. Dictionary meanings, parts of speech, technical terminology, passive voice and complete STE compliance need semantic review. Never present 100/100 as full compliance.

## Storage and failures

State lives under central memory/runtime/reply-standard. A SHA-256 of the client and native session ID selects the file. There is no shared fallback chat. Records contain only schema/client, hook times, score and rule IDs/counts. No prompts, replies, excerpts, credentials or raw session IDs are saved. Feedback expires after 24 hours; old files remain as small local receipts until explicitly removed. Missing session IDs still receive the rules, with no saved feedback.

Cache fields are validated and rendered from allowed IDs; arbitrary cached text never becomes prompt context. Corrupt, oversized, future-dated or stale assessments are ignored. Input is limited to 1 MiB. Missing reply text skips scoring. Storage and input failures return an empty JSON object and permit the turn to continue. A missing rule file also permits the turn to continue; shared instructions and the saved user preference remain the fallback.

The installer preserves existing native hooks and settings. Changed native configurations require their normal client review/trust. A script test proves the supplied protocol only. Fresh native receipts prove those hooks ran in that sample; they do not prove all models, desktop sessions, resumed turns or compaction paths. Reload/restart a client if its active session has not loaded the changed hook configuration.

## Verification

Run `node --test scripts/tests/council-reply-standard.test.mjs` and `node scripts/tests/council-codex.test.mjs`. Follow the [behavior checks](../../docs/behavior-evaluation.md) for a fresh native sample. Keep source, placement, native execution and observed reply behavior as separate results.

References: [ASD-STE100](https://www.asd-ste100.org/), [Codex hooks](https://learn.chatgpt.com/docs/hooks), [Gemini hooks](https://geminicli.com/docs/hooks/reference/). Hook registration belongs in native client configuration; a Markdown instruction file does not execute shell hooks by itself.

## Review before delivery

The replying actor reviews the current draft before sending it. Check meaning, one main idea per sentence, consistent technical names, active voice, step order, missing decisions and evidence limits. Preserve literal source text. Correct unclear or unsupported statements in this reply.

Do not defer a known problem to next-turn feedback. A score of 100 only describes the checked subset. It does not establish clarity, complete STE compliance or workflow completion. Do not add a compliance claim to each reply.

For a substantive saved deliverable, record this review and any remaining limits in its existing verification record. Routine chat replies need no separate file. Prompt and completion hooks remain advisory; these instructions do not add a blocking checker or an automatic rewrite.

## Answer order

For status reports and decision requests, state the current status or decision and the required next action before supporting details. Keep evidence, reasoning and secondary facts after that opening.

Preserve the scope, conditions and uncertainty of the source. If status is unknown, say so. Do not invent a next action, approval or rejection. State that no action is needed only when the source supports it. Explanations and open discussions do not require a status-report template. Follow the user's requested format.

Example: Deployment is not authorized. Run the database integration tests with duplicate message cases before requesting approval.

The existing prompt hooks supply this rule from the shared JSON. Shared instructions provide the fallback. Event registrations and the completion score do not change. The score does not assess answer order. The focused behavioral cases below test known synthetic facts and opening order; they are not a general semantic checker.

Use reply-order for known deployment status and reply-order-unknown for unknown authorization. A status/action opening must precede supporting evidence. Correct order cannot excuse missing or false facts. Do not use a universal word-position threshold.
