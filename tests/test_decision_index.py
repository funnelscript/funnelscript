"""Decision-ledger integrity checks; does not assert cross-repository parity."""

import re
from pathlib import Path


DECISION_HEADER = re.compile(r"^### (DEC-\d{3}):", re.MULTILINE)
INDEX_ENTRY = re.compile(r"^\| \*\*(DEC-\d{3})\*\* \|", re.MULTILINE)


def test_every_detailed_decision_has_exactly_one_index_entry():
    ledger = Path(__file__).resolve().parents[1] / 'docs/DECISIONS.md'
    body = ledger.read_text(encoding="utf-8")
    index = body.split("## Decision Index", 1)[1].split(
        "## Detailed Architecture Decision Records", 1
    )[0]
    detailed = body.split("## Detailed Architecture Decision Records", 1)[1]

    indexed_ids = INDEX_ENTRY.findall(index)
    detailed_ids = DECISION_HEADER.findall(detailed)
    assert len(indexed_ids) == len(set(indexed_ids)), "Duplicate decision index IDs"
    assert len(detailed_ids) == len(set(detailed_ids)), "Duplicate detailed decision IDs"
    assert set(indexed_ids) == set(detailed_ids), (
        f"Unindexed: {sorted(set(detailed_ids) - set(indexed_ids))}; "
        f"missing details: {sorted(set(indexed_ids) - set(detailed_ids))}"
    )
