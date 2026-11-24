"""Tests verifying Suite 5: Declarative Data-to-Object Mapping & Provenance (Gate G5).

Verifies:
- Hydration of custom entities from raw CSV and Stripe/Segment JSON via mapping.toml.
- Dirty data rejection and Dead-Letter Queue (DLQ) routing (never silent coercion).
- Idempotent replay preventing duplicate entity instantiations or ledger postings.
- End-to-end cryptographic provenance (source_file_hash, row_id, idempotency_key).
- CLI command 'funnelscript map inspect' scaffolding explicit mapping.toml.
"""

import json
import subprocess
import sys
from pathlib import Path

from funnelscript.connectors.object_mapper import (
    DLQRecord,
    HydratedEntity,
    MappingConfig,
    ObjectMapper,
)
from funnelscript.ledger import FinancialLedger

SAMPLE_MAPPING_TOML = """[mapping]
target = "CODParcel"
idempotency_key = "order_id"
currency = "EGP"

[fields]
value = { column = "amount_egp", type = "Currency<EGP>", required = true }
shipping_cost = { column = "delivery_fee", type = "Currency<EGP>", required = false, default = 0.0 }
transit_delay = { column = "transit_days", type = "Duration<day>", required = true }
customer_id = { column = "customer_ref", type = "string", required = true }
"""


SAMPLE_CSV_CONTENT = """order_id,amount_egp,delivery_fee,transit_days,customer_ref
ORD-1001,450.50,50.00,3,CUST-901
ORD-1002,1200.00,75.00,5,CUST-902
ORD-1003,300.00,40.00,2,CUST-903
"""


DIRTY_CSV_CONTENT = """order_id,amount_egp,delivery_fee,transit_days,customer_ref
ORD-2001,500.00,50.00,3,CUST-001
ORD-2002,,50.00,4,CUST-002
ORD-2003,NOT_A_NUMBER,50.00,2,CUST-003
ORD-2004,-150.00,50.00,3,CUST-004
ORD-2005,800.00,50.00,-1,CUST-005
ORD-2006,950.00,60.00,2,
ORD-2007,600.00,40.00,1,CUST-007
"""


STRIPE_JSON_PAYLOAD = [
    {
        "id": "ch_3Nabc1",
        "amount": 250.00,
        "currency": "USD",
        "status": "succeeded",
        "created": 1690000000,
        "customer": "cus_999",
    },
    {
        "id": "ch_3Nabc2",
        "amount": 420.00,
        "currency": "USD",
        "status": "succeeded",
        "created": 1690000100,
        "customer": "cus_888",
    },
]


def test_clean_csv_hydration_and_provenance(tmp_path: Path) -> None:
    """Task 4.1: Clean CSV hydrates typed entities with intact cryptographic provenance."""
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")

    mapping_file = tmp_path / "mapping.toml"
    mapping_file.write_text(SAMPLE_MAPPING_TOML, encoding="utf-8")

    mapper = ObjectMapper(mapping_file)
    res = mapper.ingest_file(csv_file)

    assert res.total_processed == 3
    assert res.success_count == 3
    assert res.dlq_count == 0
    assert res.duplicate_count == 0

    first = res.hydrated[0]
    assert isinstance(first, HydratedEntity)
    assert first.entity_name == "CODParcel"
    assert first.fields["value"] == 450.50
    assert first.fields["shipping_cost"] == 50.00
    assert first.fields["transit_delay"] == 3
    assert first.fields["customer_id"] == "CUST-901"

    # Verify provenance metadata
    prov = first.provenance
    assert len(prov.source_file_hash) == 64
    assert prov.row_id == 1
    assert prov.idempotency_key == "CODParcel:ORD-1001"
    assert len(prov.schema_hash) == 64


def test_dirty_data_rejection_and_dlq_routing(tmp_path: Path) -> None:
    """Task 4.2 & Gate G5: Dirty data routes to DLQ with exact error codes; 0 silent coercions."""
    dirty_file = tmp_path / "dirty_orders.csv"
    dirty_file.write_text(DIRTY_CSV_CONTENT, encoding="utf-8")

    mapping_file = tmp_path / "mapping.toml"
    mapping_file.write_text(SAMPLE_MAPPING_TOML, encoding="utf-8")

    mapper = ObjectMapper(mapping_file)
    res = mapper.ingest_file(dirty_file)

    assert res.total_processed == 7
    assert res.success_count == 2  # ORD-2001 and ORD-2007 are clean
    assert res.dlq_count == 5      # 5 dirty rows routed to DLQ

    dlq_by_row = {d.row_id: d for d in res.dlq}

    # Row 2 (ORD-2002): Missing required amount_egp
    assert 2 in dlq_by_row
    assert dlq_by_row[2].error_code == "DLQ-001"
    assert "Missing required field" in dlq_by_row[2].error_message

    # Row 3 (ORD-2003): Non-numeric string in amount_egp
    assert 3 in dlq_by_row
    assert dlq_by_row[3].error_code == "DLQ-002"
    assert "Cannot convert 'NOT_A_NUMBER' to currency" in dlq_by_row[3].error_message

    # Row 4 (ORD-2004): Negative currency amount
    assert 4 in dlq_by_row
    assert dlq_by_row[4].error_code == "DLQ-003"
    assert "Negative currency amount" in dlq_by_row[4].error_message

    # Row 5 (ORD-2005): Negative duration
    assert 5 in dlq_by_row
    assert dlq_by_row[5].error_code == "DLQ-003"
    assert "Negative duration" in dlq_by_row[5].error_message

    # Row 6 (ORD-2006): Missing required customer_ref
    assert 6 in dlq_by_row
    assert dlq_by_row[6].error_code == "DLQ-001"

    # All DLQ records retain raw data and source file hash
    for dlq_item in res.dlq:
        assert isinstance(dlq_item, DLQRecord)
        assert len(dlq_item.source_file_hash) == 64
        assert len(dlq_item.raw_data) > 0


def test_idempotent_replay_deduplication(tmp_path: Path) -> None:
    """Gate G5: Re-ingesting identical dataset yields zero duplicate entities."""
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")

    mapping_file = tmp_path / "mapping.toml"
    mapping_file.write_text(SAMPLE_MAPPING_TOML, encoding="utf-8")

    mapper = ObjectMapper(mapping_file)

    # First pass: 3 hydrated entities
    res_1 = mapper.ingest_file(csv_file)
    assert res_1.success_count == 3
    assert res_1.duplicate_count == 0

    # Second pass: Replay identical file
    res_2 = mapper.ingest_file(csv_file)
    assert res_2.success_count == 0
    assert res_2.duplicate_count == 3
    assert res_2.dlq_count == 0


def test_json_ingestion_and_stripe_hydration(tmp_path: Path) -> None:
    """Task 4.1: Ingesting Stripe payment records via JSON format."""
    json_file = tmp_path / "stripe_charges.json"
    json_file.write_text(json.dumps(STRIPE_JSON_PAYLOAD), encoding="utf-8")

    stripe_mapping_toml = """[mapping]
target = "StripeCharge"
idempotency_key = "id"
currency = "USD"

[fields]
amount = { column = "amount", type = "Currency<USD>", required = true }
customer = { column = "customer", type = "string", required = true }
created = { column = "created", type = "int", required = true }
status = { column = "status", type = "string", required = true }
"""
    mapping_file = tmp_path / "stripe_mapping.toml"
    mapping_file.write_text(stripe_mapping_toml, encoding="utf-8")

    mapper = ObjectMapper(mapping_file)
    res = mapper.ingest_file(json_file)

    assert res.success_count == 2
    assert res.dlq_count == 0
    assert res.hydrated[0].fields["amount"] == 250.00
    assert res.hydrated[1].fields["amount"] == 420.00
    assert res.hydrated[0].provenance.idempotency_key == "StripeCharge:ch_3Nabc1"


def test_double_entry_ledger_provenance_integration(tmp_path: Path) -> None:
    """Task 4.2 & Gate G5: Hydrated entity posts to ledger with audit provenance."""
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")
    mapping_file = tmp_path / "mapping.toml"
    mapping_file.write_text(SAMPLE_MAPPING_TOML, encoding="utf-8")

    mapper = ObjectMapper(mapping_file)
    res = mapper.ingest_file(csv_file)

    ledger = FinancialLedger()
    ledger.declare_account("clearing", currency="EGP")
    ledger.declare_account("bank_cash", currency="EGP")

    tx_ids: list[str] = []
    for entity in res.hydrated:
        tx_id = mapper.post_to_ledger(
            entity,
            ledger,
            debit_account="clearing",
            credit_account="bank_cash",
            amount_field="value",
            currency="EGP",
        )
        tx_ids.append(tx_id)

    assert len(tx_ids) == 3
    assert ledger.total_imbalance_cents("EGP") == 0
    total_posted = sum(e.fields["value"] for e in res.hydrated)
    assert ledger.balance_cents("clearing") == int(total_posted * 100)
    assert ledger.balance_cents("bank_cash") == -int(total_posted * 100)

    # Replaying same entity to ledger is idempotently ignored
    replay_tx = mapper.post_to_ledger(
        res.hydrated[0],
        ledger,
        debit_account="clearing",
        credit_account="bank_cash",
        amount_field="value",
        currency="EGP",
    )
    assert replay_tx == tx_ids[0]
    # Balance remains unchanged
    assert ledger.balance_cents("clearing") == int(total_posted * 100)


def test_cli_map_inspect_subcommand(tmp_path: Path) -> None:
    """Task 4.3: CLI 'funnelscript map inspect' generates valid mapping.toml."""
    csv_file = tmp_path / "input_data.csv"
    csv_file.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")
    output_toml = tmp_path / "generated_mapping.toml"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "funnelscript.cli",
            "map",
            "inspect",
            str(csv_file),
            "--target",
            "CODParcel",
            "--output",
            str(output_toml),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.returncode == 0
    assert output_toml.is_file()

    content = output_toml.read_text(encoding="utf-8")
    assert "[mapping]" in content
    assert 'target = "CODParcel"' in content
    assert "amount_egp" in content
    assert "delivery_fee" in content

    # The generated TOML must be readable by MappingConfig
    config = MappingConfig.from_toml(output_toml)
    assert config.target_entity == "CODParcel"
