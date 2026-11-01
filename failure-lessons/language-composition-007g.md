# Phase 007G — Compatibility and bounded parsing

Source forms formerly expected to fail (e.g., arithmetic chaining and a payload reference with an operator) must become positive value-oracle assertions when the new grammar intentionally enables them. Keep malformed trailing operators, unknown names, strict types, snapshot semantics, and exception tests intact. Resolve imported owner names without shadowing the enclosing World name. Reuse event decoding and the existing calendar; never duplicate event scheduling logic in the CLI.
