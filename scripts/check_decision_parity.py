"""Compare accepted ADR index contracts against a research-owned source.

Usage: python3 scripts/check_decision_parity.py APP_LEDGER RESEARCH_LEDGER
Exit 0 on parity, 1 on contract drift, 2 on unreadable inputs.
"""

import re
import sys
from pathlib import Path


ENTRY = re.compile(
    r"^\| \*\*(DEC-\d{3})\*\* \| \[([^\]]+)\]\((#[^)]+)\) "
    r"\| (\d{4}-\d{2}-\d{2}) \| \*\*([A-Za-z ]+)\*\* \| [^|]+\|$"
)
DETAIL = re.compile(r"^### (DEC-\d{3}): (.+)$", re.MULTILINE)


def read_contract(path: Path) -> dict[str, tuple[str, str, str]]:
    body = path.read_text(encoding="utf-8")
    try:
        index = body.split("## Decision Index", 1)[1].split(
            "## Detailed Architecture Decision Records", 1
        )[0]
        details = body.split("## Detailed Architecture Decision Records", 1)[1]
    except IndexError as exc:
        raise ValueError(f"{path}: required decision section is missing") from exc

    entries: dict[str, tuple[str, str, str]] = {}
    for line in index.splitlines():
        if not line.startswith("| **DEC-"):
            continue
        match = ENTRY.fullmatch(line)
        if not match:
            raise ValueError(f"{path}: invalid accepted-decision index row: {line}")
        decision_id, title, _anchor, date, status = match.groups()
        if decision_id in entries:
            raise ValueError(f"{path}: duplicate index ID {decision_id}")
        entries[decision_id] = (title, date, status)

    if not entries:
        raise ValueError(f"{path}: empty accepted-decision index")

    detailed = DETAIL.findall(details)
    titles: dict[str, str] = {}
    for decision_id, title in detailed:
        if decision_id in titles:
            raise ValueError(f"{path}: duplicate detailed ID {decision_id}")
        titles[decision_id] = title

    if set(entries) != set(titles):
        missing = sorted(set(titles) - set(entries))
        dangling = sorted(set(entries) - set(titles))
        raise ValueError(f"{path}: unindexed details {missing}; missing details {dangling}")
    return entries


def compare_ledgers(app: Path, research: Path) -> int:
    try:
        app_decisions = read_contract(app)
        canonical_decisions = read_contract(research)
    except OSError as exc:
        print(f"ADR parity I/O failure: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ADR parity invalid ledger: {exc}", file=sys.stderr)
        return 1

    discrepancies = [
        f"{decision_id}: app={app_decisions.get(decision_id)!r}, "
        f"research={canonical_decisions.get(decision_id)!r}"
        for decision_id in sorted(app_decisions.keys() | canonical_decisions.keys())
        if app_decisions.get(decision_id) != canonical_decisions.get(decision_id)
    ]
    if discrepancies:
        print("ADR parity mismatch:\n" + "\n".join(discrepancies), file=sys.stderr)
        return 1
    print(f"ADR parity OK: {len(canonical_decisions)} indexed decisions")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: check_decision_parity.py APP_LEDGER RESEARCH_LEDGER", file=sys.stderr)
        sys.exit(2)
    sys.exit(compare_ledgers(Path(sys.argv[1]), Path(sys.argv[2])))
