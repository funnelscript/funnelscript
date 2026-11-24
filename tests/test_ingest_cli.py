"""Tests for FunnelScript Ingestion CLI Commands (`funnelscript ingest ...`).

Validates:
1. `funnelscript ingest stage --db ...`: prints staging status and DLQ depth.
2. `funnelscript ingest stage --drain-ledger`: drains pending records into ledger.
3. `funnelscript ingest replay`: generates synthetic discrete events and saves JSON playbook.
4. `funnelscript ingest poll`: rejects unsupported platforms with returncode 1.
"""

import json
import subprocess
import sys
from pathlib import Path

from funnelscript.connectors.models import CanonicalAdSpendRecord
from funnelscript.connectors.staging import SQLiteStagingBuffer


def test_cli_ingest_stage_inspect_and_drain(tmp_path: Path):
    db_file = tmp_path / "cli_stage.db"
    staging = SQLiteStagingBuffer(db_file)

    rec = CanonicalAdSpendRecord(
        platform="meta",
        account_id="act_cli",
        campaign_id="camp_cli",
        campaign_name="CLI Campaign",
        date="2026-11-20",
        spend_cents=10000,
        impressions=1000,
        clicks=50,
    )
    staging.enqueue(rec)
    staging.close()

    # 1. Run stage inspection
    res = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "ingest", "stage", "--db", str(db_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Pending:    1" in res.stdout
    assert "DLQ Depth:  0" in res.stdout

    # 2. Run stage draining into ledger
    res_drain = subprocess.run(
        [sys.executable, "-m", "funnelscript.cli", "ingest", "stage", "--db", str(db_file), "--drain-ledger"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_drain.returncode == 0
    assert "Drained 1 records into FinancialLedger" in res_drain.stdout


def test_cli_ingest_replay(tmp_path: Path):
    csv_file = tmp_path / "spend.csv"
    csv_file.write_text(
        "Date,Channel,Impressions,Clicks,Spend,Conversions,Revenue\n"
        "2026-10-01,meta_ads,10000,200,300.0,10,1200.0\n",
        encoding="utf-8",
    )
    playbook_out = tmp_path / "playbook.json"

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "funnelscript.cli",
            "ingest",
            "replay",
            str(csv_file),
            "--output",
            str(playbook_out),
            "--seed",
            "42",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Synthesized 200 discrete agent simulation events" in res.stdout
    assert playbook_out.exists()

    data = json.loads(playbook_out.read_text(encoding="utf-8"))
    assert data["total_events"] == 200
    assert data["events"][0]["event"] == "AdClick"


def test_cli_ingest_poll_unsupported_platform():
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "funnelscript.cli",
            "ingest",
            "poll",
            "--platform",
            "unknown_platform",
            "--account",
            "123",
            "--start",
            "2026-01-01",
            "--end",
            "2026-01-02",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # argparse should reject choice or command should fail
    assert res.returncode != 0
