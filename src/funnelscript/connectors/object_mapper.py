"""Declarative data-to-object mapping and provenance tracking layer.

Implements the Ingestable Trait contract:
- Explicit, auditable mapping.toml bindings (Anti-Pattern 3 Guardrail).
- Cryptographic provenance tracking (source_file_hash, row_id, idempotency_key).
- Dead-Letter Queue (DLQ) routing for malformed or dirty data (Gate G5).
- Replay idempotency guaranteeing zero duplicate ledger postings.
- Draft schema suggestion for CLI command 'funnelscript map inspect'.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from funnelscript.compiler.world_ast import EntityDefinition, WorldAST
from funnelscript.ledger import FinancialLedger

_ISO_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class ProvenanceMetadata:
    """Cryptographic provenance trail for an ingested entity instance."""
    source_file_hash: str
    row_id: int
    idempotency_key: str
    schema_hash: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class HydratedEntity:
    """A validated, typed entity instance hydrated from external data."""
    entity_name: str
    fields: dict[str, Any]
    provenance: ProvenanceMetadata

    def get(self, key: str, default: Any = None) -> Any:
        return self.fields.get(key, default)


@dataclass(frozen=True)
class DLQRecord:
    """Dead-Letter Queue record capturing malformed rows and routing diagnostics."""
    row_id: int
    raw_data: dict[str, Any]
    error_code: str
    error_message: str
    source_file_hash: str


@dataclass
class IngestionResult:
    """Result of an ingestion run containing hydrated objects and DLQ records."""
    hydrated: list[HydratedEntity]
    dlq: list[DLQRecord]
    duplicate_count: int
    total_processed: int
    source_file_hash: str
    schema_hash: str

    @property
    def success_count(self) -> int:
        return len(self.hydrated)

    @property
    def dlq_count(self) -> int:
        return len(self.dlq)


@dataclass(frozen=True)
class FieldMapping:
    """Mapping rules for a single target entity field."""
    source_col: str
    target_type: str = "string"
    required: bool = True
    default: Any = None


@dataclass
class MappingConfig:
    """Configuration loaded from mapping.toml."""
    target_entity: str
    idempotency_field: str | None = None
    default_currency: str = "USD"
    fields: dict[str, FieldMapping] = field(default_factory=dict)
    schema_hash: str = ""

    @classmethod
    def from_toml(cls, toml_str_or_path: str | Path) -> MappingConfig:
        if isinstance(toml_str_or_path, Path) or (isinstance(toml_str_or_path, str) and "\n" not in toml_str_or_path and Path(toml_str_or_path).is_file()):
            path = Path(toml_str_or_path)
            content = path.read_text(encoding="utf-8")
        else:
            content = str(toml_str_or_path)

        schema_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        data = tomllib.loads(content)

        mapping_section = data.get("mapping", {})
        target = mapping_section.get("target") or mapping_section.get("target_entity", "Entity")
        idempotency_field = mapping_section.get("idempotency_key") or mapping_section.get("idempotency_field")
        default_currency = mapping_section.get("currency") or mapping_section.get("default_currency", "USD")

        field_mappings: dict[str, FieldMapping] = {}
        fields_section = data.get("fields", {})
        for field_name, spec in fields_section.items():
            if isinstance(spec, str):
                field_mappings[field_name] = FieldMapping(source_col=spec, target_type="string")
            elif isinstance(spec, dict):
                field_mappings[field_name] = FieldMapping(
                    source_col=spec.get("source") or spec.get("column", field_name),
                    target_type=spec.get("type", "string"),
                    required=spec.get("required", True),
                    default=spec.get("default", None),
                )

        return cls(
            target_entity=target,
            idempotency_field=idempotency_field,
            default_currency=default_currency,
            fields=field_mappings,
            schema_hash=schema_hash,
        )


class ObjectMapper:
    """Hydrates typed entity instances from raw external records via mapping.toml."""

    def __init__(
        self,
        config: MappingConfig | Path | str,
        target_entity: EntityDefinition | None = None,
    ) -> None:
        if isinstance(config, MappingConfig):
            self.config = config
        else:
            self.config = MappingConfig.from_toml(config)
        self.target_entity = target_entity
        self.seen_idempotency_keys: set[str] = set()

    def reset_idempotency(self) -> None:
        """Clear observed idempotency keys."""
        self.seen_idempotency_keys.clear()

    @staticmethod
    def compute_file_hash(file_path: Path | str) -> str:
        """Calculate SHA-256 hash of a file for provenance auditability."""
        path = Path(file_path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def ingest_file(self, file_path: Path | str) -> IngestionResult:
        """Ingest records from a CSV, JSON, or JSONL file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        file_hash = self.compute_file_hash(path)
        records: list[dict[str, Any]] = []

        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                records = list(reader)
        elif path.suffix.lower() == ".json":
            content = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(content, list):
                records = content
            elif isinstance(content, dict) and "data" in content and isinstance(content["data"], list):
                records = content["data"]
            else:
                records = [content]
        elif path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        return self.ingest_records(records, source_file_hash=file_hash)

    def ingest_records(
        self,
        records: Sequence[dict[str, Any]],
        source_file_hash: str = "memory",
    ) -> IngestionResult:
        """Hydrate entity instances, enforce constraints, and route errors to DLQ."""
        hydrated: list[HydratedEntity] = []
        dlq: list[DLQRecord] = []
        duplicates = 0

        for row_idx, row in enumerate(records, start=1):
            # Compute idempotency key
            if self.config.idempotency_field and self.config.idempotency_field in row:
                raw_key = str(row[self.config.idempotency_field]).strip()
                idempotency_key = f"{self.config.target_entity}:{raw_key}"
            else:
                idempotency_key = f"{source_file_hash}:{row_idx}"

            # Check duplicate replay
            if idempotency_key in self.seen_idempotency_keys:
                duplicates += 1
                continue

            # Validate and convert fields
            converted_fields: dict[str, Any] = {}
            error_code: str | None = None
            error_msg: str | None = None

            for field_name, fmap in self.config.fields.items():
                val = row.get(fmap.source_col)
                if val is None or val == "":
                    if fmap.required and fmap.default is None:
                        error_code = "DLQ-001"
                        error_msg = f"Missing required field '{fmap.source_col}' for entity field '{field_name}'"
                        break
                    val = fmap.default

                # Parse and type-check
                parsed_val, err = self._coerce_field(val, fmap.target_type, field_name)
                if err:
                    error_code, error_msg = err
                    break
                converted_fields[field_name] = parsed_val

            if error_code:
                dlq.append(
                    DLQRecord(
                        row_id=row_idx,
                        raw_data=dict(row),
                        error_code=error_code,
                        error_message=error_msg or "Validation error",
                        source_file_hash=source_file_hash,
                    )
                )
            else:
                provenance = ProvenanceMetadata(
                    source_file_hash=source_file_hash,
                    row_id=row_idx,
                    idempotency_key=idempotency_key,
                    schema_hash=self.config.schema_hash,
                )
                hydrated.append(
                    HydratedEntity(
                        entity_name=self.config.target_entity,
                        fields=converted_fields,
                        provenance=provenance,
                    )
                )
                self.seen_idempotency_keys.add(idempotency_key)

        return IngestionResult(
            hydrated=hydrated,
            dlq=dlq,
            duplicate_count=duplicates,
            total_processed=len(records),
            source_file_hash=source_file_hash,
            schema_hash=self.config.schema_hash,
        )

    def _coerce_field(
        self, val: Any, target_type: str, field_name: str
    ) -> tuple[Any, tuple[str, str] | None]:
        """Strictly convert and validate a field value against dimensional types."""
        if val is None:
            return None, None

        clean_type = target_type.strip()

        # 1. Currency types: e.g. Currency<USD>, Currency<EGP>, Currency
        if "Currency" in clean_type:
            # Check ISO code if specified in parameter
            match = re.search(r"Currency<([A-Z]{3})>", clean_type)
            expected_iso = match.group(1) if match else self.config.default_currency
            if expected_iso and not _ISO_CURRENCY_PATTERN.match(expected_iso):
                return None, ("DLQ-004", f"Invalid ISO currency code '{expected_iso}' on field '{field_name}'")

            try:
                num = float(val)
            except (ValueError, TypeError):
                return None, ("DLQ-002", f"Cannot convert '{val}' to currency amount on field '{field_name}'")
            if num < 0:
                return None, ("DLQ-003", f"Negative currency amount {num} not permitted on field '{field_name}'")
            return round(num, 2), None

        # 2. Duration types: Duration<day>, Duration<hour>, Duration
        if "Duration" in clean_type:
            try:
                num = float(val)
            except (ValueError, TypeError):
                return None, ("DLQ-002", f"Cannot convert '{val}' to duration on field '{field_name}'")
            if num < 0:
                return None, ("DLQ-003", f"Negative duration {num} not permitted on field '{field_name}'")
            return int(num) if num.is_integer() else num, None

        # 3. Numeric primitives: int, float, Pool, Rate, Prob, Metric
        if clean_type in ("int", "Pool", "Count") or clean_type.startswith(("Pool<", "Count<")):
            try:
                num = int(float(val))
            except (ValueError, TypeError):
                return None, ("DLQ-002", f"Cannot convert '{val}' to integer on field '{field_name}'")
            if (clean_type.startswith("Pool") or clean_type == "Count") and num < 0:
                return None, ("DLQ-003", f"Stock or count pool cannot be negative: {num}")
            return num, None

        if clean_type in ("float", "Rate", "Prob", "Scalar", "Metric"):
            try:
                num = float(val)
            except (ValueError, TypeError):
                return None, ("DLQ-002", f"Cannot convert '{val}' to float on field '{field_name}'")
            if clean_type == "Prob" and not (0.0 <= num <= 1.0):
                return None, ("DLQ-003", f"Probability value {num} must be between 0.0 and 1.0 on field '{field_name}'")
            return num, None

        # 4. Boolean
        if clean_type == "bool":
            if isinstance(val, bool):
                return val, None
            s = str(val).strip().lower()
            if s in ("true", "1", "yes", "y", "t"):
                return True, None
            if s in ("false", "0", "no", "n", "f"):
                return False, None
            return None, ("DLQ-002", f"Cannot convert '{val}' to boolean on field '{field_name}'")

        # 5. String / Attribute
        return str(val).strip(), None

    def post_to_ledger(
        self,
        entity: HydratedEntity,
        ledger: FinancialLedger,
        *,
        debit_account: str,
        credit_account: str,
        amount_field: str = "value",
        currency: str | None = None,
    ) -> str:
        """Execute double-entry ledger postings with attached cryptographic provenance."""
        amount = entity.get(amount_field)
        if amount is None:
            raise ValueError(f"Entity missing amount field '{amount_field}'")

        curr = currency or self.config.default_currency
        for acct_name in (debit_account, credit_account):
            if acct_name not in ledger._accounts:
                ledger.declare_account(acct_name, curr)

        tx_id = f"tx_{entity.provenance.idempotency_key}"

        # If already recorded in ledger, avoid duplicate
        if ledger.has_transaction(tx_id):
            return tx_id

        ledger.post(
            tx_id=tx_id,
            timestamp=entity.provenance.timestamp,
            postings=[
                (debit_account, "debit", amount),
                (credit_account, "credit", amount),
            ],
            description=f"Ingested {entity.entity_name} {entity.provenance.idempotency_key}",
            metadata={
                "idempotency_key": entity.provenance.idempotency_key,
                "source_file_hash": entity.provenance.source_file_hash,
                "row_id": str(entity.provenance.row_id),
            },
        )
        return tx_id

    @classmethod
    def inspect_file(
        cls,
        file_path: Path | str,
        target_entity_name: str | None = None,
        world_ast: WorldAST | None = None,
    ) -> str:
        """Inspect a raw dataset and generate an auditable draft mapping.toml for human review."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        headers: list[str] = []
        sample_rows: list[dict[str, Any]] = []

        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                for idx, row in enumerate(reader):
                    if idx >= 5:
                        break
                    sample_rows.append(row)
        elif path.suffix.lower() in (".json", ".jsonl"):
            # Load first few items
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                records = data if isinstance(data, list) else data.get("data", [data])
            else:
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][:5]
            if records and isinstance(records[0], dict):
                headers = list(records[0].keys())
                sample_rows = records[:5]

        # Infer target entity fields from AST if provided
        target_name = target_entity_name or "CustomEntity"
        entity_fields: dict[str, str] = {}
        if world_ast:
            for decl in world_ast.declarations:
                if isinstance(decl, EntityDefinition) and (decl.name == target_name or target_name.endswith(f".{decl.name}")):
                    for s in decl.states:
                        entity_fields[s.name] = s.type_name
                    for p in decl.primitives:
                        entity_fields[p.name] = p.type_spec

        # Determine idempotency field candidates
        idempotency_candidate = next(
            (h for h in headers if any(k in h.lower() for k in ("id", "key", "number", "uuid"))),
            headers[0] if headers else "row_id",
        )

        lines: list[str] = [
            "# FunnelScript Declarative Data Mapping Specification",
            "# Generated via 'funnelscript map inspect' for explicit human audit",
            "",
            "[mapping]",
            f'target = "{target_name}"',
            f'idempotency_key = "{idempotency_candidate}"',
            'currency = "USD"',
            "",
            "[fields]",
        ]

        if entity_fields:
            for field_name, ftype in entity_fields.items():
                matched_header = next(
                    (h for h in headers if h.lower() == field_name.lower() or field_name.lower() in h.lower()),
                    headers[0] if headers else "unknown",
                )
                lines.append(f'{field_name} = {{ column = "{matched_header}", type = "{ftype}", required = true }}')
        else:
            for h in headers:
                clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", h).lower()
                # Infer type from samples
                sample_vals = [r.get(h) for r in sample_rows if r.get(h) is not None]
                inferred_type = "string"
                if sample_vals:
                    first = sample_vals[0]
                    try:
                        int(first)
                        inferred_type = "int"
                    except (ValueError, TypeError):
                        try:
                            float(first)
                            inferred_type = "float"
                        except (ValueError, TypeError):
                            inferred_type = "string"
                lines.append(f'{clean_name} = {{ column = "{h}", type = "{inferred_type}" }}')

        return "\n".join(lines) + "\n"
