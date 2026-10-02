import sys
from pathlib import Path

package_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(package_root))

from council.tools.test_runner import parse_dotnet_errors, parse_test_counts, parse_deno_errors

def test_parse_dotnet_cs_errors():
    sample_output = """
Build FAILED.
C:\\repo\\RatesQuery.cs(42,15): error CS0246: The type or namespace 'DistanceUnit' could not be found
C:\\repo\\RatesQuery.cs(50,20): error CS1061: 'RatesQueryRequest' does not contain 'Unit'
    0 Warning(s)
    2 Error(s)
Passed! - Failed: 0, Passed: 110, Skipped: 0, Total: 110
    """
    errors = parse_dotnet_errors(sample_output)
    assert len(errors) == 2
    assert "CS0246" in errors[0]
    assert "CS1061" in errors[1]

def test_parse_dotnet_test_counts():
    sample_output = "Passed: 118, Failed: 2, Skipped: 0"
    passed, failed = parse_test_counts(sample_output)
    assert passed == 118
    assert failed == 2

def test_parse_deno_errors():
    sample_output = """
running 6 tests from ./tests/shipping-rates-transform.test.ts
test calculate rates ... FAILED (12ms)
error: AssertionError: Values are not equal:
  [Diff] Actual / Expected
  - "MILE"
  + "KM"
FAILURES:
./tests/shipping-rates-transform.test.ts > calculate rates
    """
    deno_errors = parse_deno_errors(sample_output)
    assert len(deno_errors) > 0
    assert any("AssertionError" in e for e in deno_errors)

if __name__ == "__main__":
    test_parse_dotnet_cs_errors()
    test_parse_dotnet_test_counts()
    test_parse_deno_errors()
    print("[PASS] test_test_runner passed successfully")
