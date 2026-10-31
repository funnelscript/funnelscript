from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from funnelscript.models import StrategyAST


def generate_json_schema() -> dict[str, Any]:
    """Generates the official JSON Schema Draft 2020-12 for FunnelScript."""
    schema = StrategyAST.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "FunnelScript Strategy Specification"
    schema["description"] = "Formal declarative schema for marketing systems engineering and discrete-event simulation."
    return schema


def export_json_schema(target_path: str | Path | None = None) -> str:
    """Exports and saves the JSON Schema to file."""
    schema = generate_json_schema()
    json_str = json.dumps(schema, indent=2)
    if target_path:
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str, encoding="utf-8")
    return json_str
