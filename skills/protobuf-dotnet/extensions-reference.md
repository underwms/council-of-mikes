# Protobuf Extensions Reference — .NET

Comprehensive patterns for C# extension methods that bridge Google protobuf types and CLR types. All extensions belong in a shared `Extensions/` directory and are marked `[ExcludeFromCodeCoverage]`.

> **Tip**: Never modify generated files in `Generated/`. Use extension methods (this file) or partial classes instead. See SKILL.md for full guidance.

---

## Contents

- [Protobuf Extensions Reference — .NET](#protobuf-extensions-reference--net)
  - [Contents](#contents)
  - [Setup](#setup)
  - [GoogleMoney Conversions](#googlemoney-conversions)
    - [Money → decimal](#money--decimal)
    - [decimal → Money](#decimal--money)
    - [string → Money](#string--money)
  - [GoogleDecimal Conversions](#googledecimal-conversions)
  - [String Helpers for Protobuf](#string-helpers-for-protobuf)
  - [RepeatedField Helpers](#repeatedfield-helpers)
  - [Value to CLR Type Conversions](#value-to-clr-type-conversions)
    - [Value → Struct (value types)](#value--struct-value-types)
    - [Value → Class (reference types)](#value--class-reference-types)
  - [CLR Type to Value Conversions](#clr-type-to-value-conversions)
    - [Struct → Value](#struct--value)
    - [Class → Value](#class--value)
    - [DateTime → Value](#datetime--value)
  - [Enum Formatting](#enum-formatting)
  - [Creating Domain-Specific Extensions](#creating-domain-specific-extensions)

---

## Setup

```csharp
using Google.Protobuf;
using Google.Protobuf.Collections;
using Google.Protobuf.WellKnownTypes;
using System.Collections;
using System.Diagnostics.CodeAnalysis;
using GoogleDecimal = Google.Type.Decimal;
using GoogleMoney = Google.Type.Money;
using NewtonsoftJsonConvert = Newtonsoft.Json.JsonConvert;
using SystemEnum = System.Enum;
using SystemTextJsonSerializer = System.Text.Json.JsonSerializer;

[ExcludeFromCodeCoverage]
public static class ProtoBufExtensions
{
    private const string DefaultZero = "0";
    // Extension methods below
}
```

**Key aliases** — avoid naming collisions with CLR types:
- `GoogleDecimal = Google.Type.Decimal` (vs `System.Decimal`)
- `GoogleMoney = Google.Type.Money`
- `SystemEnum = System.Enum` (vs protobuf enum types)
- `NewtonsoftJsonConvert` / `SystemTextJsonSerializer` — for JSON fallback serialization

**Constants**: Use `DefaultZero` constant (`"0"`) instead of string literals for default zero values.

---

## GoogleMoney Conversions

### Money → decimal

```csharp
// Nullable: returns 0m if null
public static decimal TryToClrDecimal(this GoogleMoney? input)
    => input?.DecimalValue ?? 0;
```

### decimal → Money

```csharp
// Non-nullable: always returns Money
public static GoogleMoney ToMoneyFromClrDecimal(this decimal input)
    => ToMoneyFromClrDecimal(input, "USD");

public static GoogleMoney ToMoneyFromClrDecimal(this decimal input, string currencyCode)
    => new GoogleMoney { CurrencyCode = currencyCode, DecimalValue = input };

// Nullable: returns null if input is null
public static GoogleMoney? TryToMoneyFromClrDecimal(this decimal? input)
    => input is null ? null : ToMoneyFromClrDecimal(input.Value, "USD");

// Nullable: returns null if zero
public static GoogleMoney? TryToMoneyFromClrDecimal(this decimal input)
    => input is decimal.Zero ? null : ToMoneyFromClrDecimal(input, "USD");
```

### string → Money

```csharp
// Parse string to Money (returns null if unparseable)
public static GoogleMoney? TryToMoneyFromClrDecimal(this string? input)
    => !decimal.TryParse(input, out var val) ? null : ToMoneyFromClrDecimal(val, "USD");

// Parse string to Money (defaults to 0 if unparseable)
public static GoogleMoney ToMoneyFromClrDecimal(this string input)
{
    if (!decimal.TryParse(input, out var val)) val = 0m;
    return ToMoneyFromClrDecimal(val, "USD");
}
```

**Convention**: Default currency is `"USD"`. All overloads accept an optional `currencyCode` parameter.

---

## GoogleDecimal Conversions

```csharp
// Nullable Google.Type.Decimal → string (DefaultZero if null)
public static string TryValue(this GoogleDecimal? input)
    => input?.Value ?? DefaultZero;

// Nullable Google.Type.Decimal → decimal (0m if null)
public static decimal TryToClrDecimal(this GoogleDecimal? input)
    => input?.ToClrDecimal() ?? decimal.Zero;
```

---

## String Helpers for Protobuf

Protobuf `string` fields do not support null — they default to empty string on the wire. These helpers handle the C#-to-proto boundary:

```csharp
// Returns empty string if null/whitespace (for proto string fields)
public static string TryValueOrDefaultEmptyString(this string? input)
    => string.IsNullOrWhiteSpace(input) ? string.Empty : input;

// Returns DefaultZero if null/whitespace (for fields that map to Money/Decimal)
public static string TryValueOrDefaultToZero(this string? input)
    => string.IsNullOrWhiteSpace(input) ? DefaultZero : input;
```

**When to use**:
- `TryValueOrDefaultEmptyString` — mapping nullable C# strings to proto `string` fields
- `TryValueOrDefaultToZero` — mapping nullable C# strings that will become `GoogleMoney` or `GoogleDecimal`

---

## RepeatedField Helpers

Protobuf `repeated` fields generate `RepeatedField<T>` in C#, which doesn't support assignment. Use these helpers:

```csharp
// Replace all items in a repeated field
public static void ClearAndAddRange<T>(this RepeatedField<T> list, IList<T> items)
{
    list.Clear();
    list.AddRange(items);
}

// Replace with a single item
public static void ClearAndAdd<T>(this RepeatedField<T> list, T item)
{
    list.Clear();
    list.Add(item);
}
```

**Why**: `RepeatedField<T>` has no setter — you can't assign `message.Items = newList`. You must clear and re-add.

---

## Value to CLR Type Conversions

`google.protobuf.Value` is a union type for dynamic/untyped data. These extensions convert back to C# types.

### Value → Struct (value types)

```csharp
public static TStruct ToStructFromProtoBufValue<TStruct>(this Value value)
    where TStruct : struct
{
    ArgumentNullException.ThrowIfNull(value);
    // Handles: bool, char, DateTime (from StringValue), all numeric types
    // Throws InvalidOperationException for unsupported conversions
}
```

**Supported mappings:**

| Value.KindCase | Target Type | Conversion |
|----------------|-------------|------------|
| `BoolValue` | `bool` | Direct cast |
| `StringValue` | `char` | First character |
| `StringValue` | `DateTime` | `DateTime.Parse` |
| `NumberValue` | `int`, `long`, `double`, `float`, `decimal`, `short`, `byte`, etc. | `Convert.ToXxx()` |

### Value → Class (reference types)

```csharp
public static TClass? ToClassFromProtoBufValue<TClass>(this Value value)
    where TClass : class
{
    ArgumentNullException.ThrowIfNull(value);
    // NullValue → null
    // StringValue + target is string → direct return
    // StructValue → JSON deserialize (System.Text.Json → Newtonsoft fallback)
    // ListValue → JSON deserialize to collection
}
```

**JSON deserialization strategy**: Tries `System.Text.Json` first, falls back to `Newtonsoft.Json`. Throws `InvalidOperationException` if both fail.

---

## CLR Type to Value Conversions

> **⚠️ Testing pitfall**: JSON test data files cannot populate `Value` fields — deserialized objects will have `KindCase.None`, causing silent data loss. In unit tests, construct CLR objects programmatically and convert with `.ToProtoBufValueFromClassInput()`. See [protobuf-value-testing.md](/docs/procedures/protobuf-value-testing.md) for patterns.

### Struct → Value

```csharp
public static Value ToProtoBufValueFromStructInput<T>(this T input)
{
    // null → Value.ForNull()
    // bool → Value.ForBool()
    // char → Value.ForString()
    // numeric → Value.ForNumber() (via double.TryParse)
}
```

### Class → Value

```csharp
public static Value ToProtoBufValueFromClassInput<T>(this T? input)
    where T : class
{
    // null → Value.ForNull()
    // string → Value.ForString()
    // IEnumerable (not string) → Value.ForList() via ListValue.Parser.ParseJson
    // other objects → Value.ForStruct() via Struct.Parser.ParseJson
    // Serialization: System.Text.Json first, Newtonsoft.Json fallback
}
```

### DateTime → Value

```csharp
public static Value ToProtoBufValueFromDateTimeInput(
    this DateTime input,
    [StringSyntax(StringSyntaxAttribute.DateTimeFormat)] string format = "yyyy-MM-dd'T'HH:mm:ss'Z'")
    => Value.ForString(input.ToString(format));
```

Default format is ISO 8601 UTC. Pass custom format string if needed.

---

## Enum Formatting

For enums that need custom string representations (e.g., API compatibility):

```csharp
public static string EnumToString<TEnum>(this TEnum input)
    where TEnum : System.Enum
{
    // Dispatch to domain-specific formatters
    if (input is TenderType t) return t.EnumToString();
    if (input is FulfillmentType f) return f.EnumToString();
    return input.ToString();
}

// Domain-specific formatters
private static string EnumToString(this TenderType input) => input switch
{
    TenderType.EbtWic => "ebt-wic",
    TenderType.EbtSnap => "ebt-snap",
    _ => input.ToString()
};

private static string EnumToString(this FulfillmentType input) => input switch
{
    FulfillmentType.Curbside => nameof(FulfillmentType.Pickup),  // Map aliases
    _ => input.ToString()
};
```

**Pattern**: Generic entry point dispatches to private domain-specific formatters via type checks.

---

## Creating Domain-Specific Extensions

When adding extensions for a new domain:

1. **Create** `Extensions/{Domain}Extensions.cs` in the Core project
2. **Mark** the class `[ExcludeFromCodeCoverage]` and `public static`
3. **Use type aliases** to avoid collisions (`GoogleMoney`, `GoogleDecimal`)
4. **Follow naming convention**: `TryXxx` for nullable-safe, `ToXxx` for non-nullable
5. **Provide overloads** for common defaults (e.g., USD currency)
6. **Add XML doc comments** with `<summary>`, `<param>`, `<returns>`, and `<example>` tags
