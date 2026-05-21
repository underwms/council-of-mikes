# Example 02 — The Purifier finds a SonarQube tripwire

**Scenario:** The Coder just finished implementing a small helper. The Purifier runs automatically (per the Council's operating principles) and catches an issue that would have failed CI.

**Members involved:** The Coder → The Purifier → The Prover
**Skill demonstrated:** Quality sweep after every code change; catching SonarQube issues *before* the gate, not after.

---

> @TheCoder please implement `OrderTotalCalculator.ComputeTotal(IEnumerable<OrderLine> lines, decimal taxRate)` that returns the sum of `(line.Quantity * line.UnitPrice)` plus tax.

**The Coder:**

```csharp
public static class OrderTotalCalculator
{
    public static decimal ComputeTotal(IEnumerable<OrderLine> lines, decimal taxRate)
    {
        decimal subtotal = 0;
        foreach (var line in lines)
        {
            subtotal += line.Quantity * line.UnitPrice;
        }
        return subtotal + (subtotal * taxRate);
    }
}
```

Idiomatic C#. The Purifier should run before I declare this done.

---

**The Purifier** *(runs automatically per operating principle #2):*

Three findings. Two real, one stylistic — calling them all out, you decide on the stylistic one.

### Finding 1 — `S3242` Method parameter should be the most general type (real)

`IEnumerable<OrderLine>` is correct — no action needed. ✅

### Finding 2 — Null-input crash (real, not a Sonar rule but a defensive gap)

`lines` is not null-checked. Calling `ComputeTotal(null!, 0.07m)` throws `NullReferenceException` from the `foreach`, not a clear `ArgumentNullException`. Fix:

```csharp
public static decimal ComputeTotal(IEnumerable<OrderLine> lines, decimal taxRate)
{
    ArgumentNullException.ThrowIfNull(lines);
    if (taxRate < 0) throw new ArgumentOutOfRangeException(nameof(taxRate));
    // ... rest unchanged
}
```

### Finding 3 — `S3267` Loop should be simplified using LINQ (stylistic, contentious)

Sonar will suggest:

```csharp
var subtotal = lines.Sum(l => l.Quantity * l.UnitPrice);
```

This is correct but **changes enumeration semantics** if `lines` is a lazy enumerable backed by I/O — `.Sum()` enumerates fully, same as the loop, so functionally equivalent. The loop is more debuggable. I recommend keeping the loop and adding `// Sonar: intentional, single-pass enumeration with explicit subtotal for debuggability` if Sonar flags it.

### Tax math edge case (not a Sonar finding — domain concern)

Floating-point-style accumulation. With `decimal` this is safe. **But:** the rounded tax-on-subtotal vs. tax-per-line distinction is a real domain decision. Confirm with the requester that "tax on subtotal" is correct — some jurisdictions require per-line rounding.

### Recommended diff:

```csharp
public static decimal ComputeTotal(IEnumerable<OrderLine> lines, decimal taxRate)
{
    ArgumentNullException.ThrowIfNull(lines);
    if (taxRate < 0)
        throw new ArgumentOutOfRangeException(nameof(taxRate), "Tax rate must be non-negative.");

    decimal subtotal = 0;
    foreach (var line in lines)
    {
        subtotal += line.Quantity * line.UnitPrice;
    }
    return subtotal + (subtotal * taxRate);
}
```

Handing off to @TheProver for coverage on:
- Empty enumerable → returns 0
- Null enumerable → `ArgumentNullException`
- Negative tax rate → `ArgumentOutOfRangeException`
- Zero tax rate → returns subtotal exactly
- Single line, multiple lines → arithmetic correctness
- The "tax on subtotal vs. per line" decision needs a domain answer before final test cases are written.

---

**The Prover:**

Test list locked. Six cases above plus one parameterized `[InlineData]` set for "tax on subtotal" arithmetic. Writing RED first per TDD discipline. Will produce the implementation only after RED is confirmed.

*(note: the original "looks fine" code shipped with no input validation, no tax-rate bounds, and an unanswered domain question. The Purifier caught all three before the Gatekeeper had to.)*
