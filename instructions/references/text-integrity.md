# Character encoding and text integrity

All Council members must preserve characters exactly in source, documentation, generated artifacts, tool output, and user-facing messages. Read and write text explicitly as UTF-8; preserve an existing BOM and line endings when editing. In PowerShell, use explicit UTF-8 encoding and a writer with the intended BOM behavior; never rely on legacy ANSI defaults or decode UTF-8 bytes as Windows-1252/Latin-1. Configure subprocess and console encoding explicitly when exchanging Unicode text. Prefer plain ASCII punctuation in newly authored Council prose when typography is unnecessary; preserve meaningful Unicode in existing content, names, and data.

Before completion, strictly decode changed text as UTF-8, inspect the saved diff and rendered/tool output, and check for mojibake and replacement characters (U+FFFD). Treat character corruption as a defect to fix before delivery. Diagnose the byte/decoding boundary and repair only confirmed corruption; do not blindly re-encode files or strip valid Unicode. A visually garbled console display alone does not prove the saved bytes are corrupt.

The canonical source audit enforces strict UTF-8, common mojibake signatures, replacement-character detection, and retired testing-framework references in active guidance. Run `node scripts/council-source.mjs audit` before refreshing the source lock. These checks complement inspection of saved and displayed text; they do not prove every possible encoding error is absent. Keep negative-test samples escaped.

When invoking Python tools on Windows, use `python -X utf8` (or the explicit interpreter path with `-X utf8`) so tools that omit an encoding argument do not fall back to Windows-1252. Keep explicit UTF-8 reads/writes in maintained code as well.
