# Example 03 — The Gatekeeper issues a BLOCKED verdict

**Scenario:** A developer claims a bug fix is "done, tests pass, ready to merge." The Gatekeeper runs the 11-phase Pre-Submit Gate and finds a regression that the existing tests *do not cover*. This is the canonical example of why the gate exists.

**Members involved:** The Gatekeeper
**Skill demonstrated:** Phase 8 (Diff-vs-behavior) and Phase 10 (Copilot PR-review simulation) catching what unit tests cannot.

---

> @TheGatekeeper use pre-submit skill — this is ready to merge.
>
> **Change:** `OrderService.cs` line 142, `GetOrderAsync` was returning `null` when the order existed but had no line items. Fixed it to return the order with an empty `Lines` collection.
>
> **Diff:**
> ```csharp
> // before
> var order = await _repo.GetByIdAsync(id);
> if (order == null || order.Lines == null || !order.Lines.Any())
>     return null;
> return order;
>
> // after
> var order = await _repo.GetByIdAsync(id);
> if (order == null) return null;
> order.Lines ??= new List<OrderLine>();
> return order;
> ```
>
> All 247 unit tests pass. Coverage on changed lines is 100%.

**The Gatekeeper:**

Running the 11-phase Pre-Submit Gate.

```
Phase 1  Brainstorm:                    n/a    Bug fix, no design phase needed.
Phase 2  Implement:                     ✅     Diff is minimal and focused.
Phase 3  Purify:                        ✅     ??= operator is idiomatic; no Sonar findings.
Phase 4  Static analysis (no new lint): ✅     Clean.
Phase 5  Unit tests:                    ✅     All 247 pass.
Phase 6  Coverage on changed lines:     ✅     100% reported.
Phase 7  Regression on affected suite:  ⚠️    All existing tests pass, BUT see Phase 8.
Phase 8  Diff-vs-behavior review:       ❌    BLOCKING FINDING.

         git show HEAD:OrderService.cs (lines 130-150) shows the original method.
         The original explicitly treated "order exists but empty Lines" as
         equivalent to "order does not exist" — both return null.
         The new code changes that contract: empty Lines now returns the order.

         The caller chain (OrderController.GetOrder, line 78) does:

             var order = await _service.GetOrderAsync(id);
             if (order == null) return NotFound();
             return Ok(order);

         Before this fix: empty-lines orders returned HTTP 404.
         After this fix:  empty-lines orders return HTTP 200 with an empty Lines array.

         This is an externally observable API behavior change. It may be the
         INTENDED fix — but it is not documented in the diff, no API contract
         test covers it, and no consumer was notified.

         Three of the 247 passing tests cover the OLD behavior:
           - OrderControllerTests.GetOrder_WhenOrderHasNoLines_Returns404
           - OrderServiceTests.GetOrderAsync_EmptyLines_ReturnsNull
           - OrderIntegrationTests.GetOrder_EmptyOrder_Returns404

         These tests pass because they were not re-run against the new code —
         OR they were re-run and they failed and were "fixed" by updating
         expectations. Either way, this is a contract change masquerading as
         a null-safety fix.

Phase 9  Integration & build:           ⏸     Not evaluated — blocked at Phase 8.
Phase 10 Copilot PR-review simulation:  ⏸     Not evaluated — blocked at Phase 8.
Phase 11 Documentation update:          ❌    No CHANGELOG entry, no API doc update,
                                              no migration note. If this IS intentional,
                                              all three are required.

Verdict: BLOCKED
```

**Required actions before re-submission:**

1. **Confirm intent.** Is "empty Lines should return 200, not 404" the intended behavior change? Get sign-off from whoever owns the API contract.
2. **If yes** (this is a real fix to a real bug):
   - Update the three tests above to assert the new behavior.
   - Add `CHANGELOG.md` entry under **BREAKING** or **CHANGED**.
   - Update the OpenAPI/Swagger description for `GET /orders/{id}`.
   - Notify downstream consumers (Service Bus contract? Frontend? Partner API docs?).
3. **If no** (the original 404 behavior was intentional):
   - Revert to the original null-return shape.
   - Add a test: `GetOrderAsync_EmptyLines_ReturnsNull` (it already exists — keep it green).
   - The "bug" was the caller's assumption, not the service's behavior.

The fact that 247 tests pass tells me the test suite is sound. The fact that this diff slipped past Phase 7 unnoticed tells me the diff was reviewed as code, not as behavior. Phase 8 exists specifically to catch this class of change.

I will not declare this READY until either path above is complete. Phase 10 (PR-review simulation) is not even worth running until the contract question is answered.

---

*(note: this transcript is the entire reason the Gatekeeper exists. Tests-pass-therefore-ship is the single most common reason for production regressions. Phase 8 reads the diff as a behavior change, not as a code change. The Gatekeeper's job is to be the reviewer who is paid to be cynical.)*
