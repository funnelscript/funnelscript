"""FunnelScript Durable SQLite Staging Buffer & Dead-Letter Queue (DLQ).

Implements:
- Local SQLite database in write-ahead logging (WAL) mode for high-concurrency ingestion.
- Idempotent deduplication: duplicate webhooks or pagination replays are safely no-ops.
- Dead-Letter Queue (DLQ) routing for corrupted, invalid, or schema-violating payloads.
- Direct draining of staged settlement and ad spend records into FinancialLedger.
- Auditable logging of attribution restatements.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from funnelscript.connectors.models import (
    CanonicalAdSpendRecord,
    CanonicalConversionEvent,
    CanonicalSettlementEvent,
    RestatementDelta,
)
from funnelscript.ledger import FinancialLedger


class SQLiteStagingBuffer:
    """High-reliability staging buffer backed by SQLite in WAL mode."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path) if db_path is not None else ":memory:"
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self._conn.cursor()
        # Enable WAL mode for high concurrent throughput (if not in-memory)
        if self.db_path != ":memory:":
            cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS staging_records (
                idempotency_key TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                record_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                ingested_at REAL NOT NULL,
                processed_at REAL,
                retry_count INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                dlq_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                raw_payload TEXT NOT NULL,
                error_code TEXT NOT NULL,
                error_message TEXT NOT NULL,
                failed_at REAL NOT NULL,
                resolved INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS restatement_audit (
                delta_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                campaign_id TEXT NOT NULL,
                date TEXT NOT NULL,
                metric TEXT NOT NULL,
                original_val REAL NOT NULL,
                restated_val REAL NOT NULL,
                delta REAL NOT NULL,
                audit_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        self._conn.commit()

    def enqueue(
        self,
        record: CanonicalAdSpendRecord | CanonicalConversionEvent | CanonicalSettlementEvent,
    ) -> bool:
        """Enqueues a canonical record. Returns True if inserted, False if duplicate."""
        if isinstance(record, CanonicalAdSpendRecord):
            rec_type = "spend"
        elif isinstance(record, CanonicalConversionEvent):
            rec_type = "conversion"
        elif isinstance(record, CanonicalSettlementEvent):
            rec_type = "settlement"
        else:
            raise TypeError(f"Unsupported record type: {type(record)}")

        payload_json = record.model_dump_json()
        now = time.time()

        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO staging_records (
                    idempotency_key, platform, record_type, payload_json, payload_sha256, status, ingested_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?);
                """,
                (
                    record.idempotency_key,
                    getattr(record, "platform", getattr(record, "gateway", "unknown")),
                    rec_type,
                    payload_json,
                    record.raw_payload_sha256,
                    now,
                ),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate idempotency_key detected; safely ignore
            return False

    def enqueue_batch(
        self,
        records: Sequence[CanonicalAdSpendRecord | CanonicalConversionEvent | CanonicalSettlementEvent],
    ) -> tuple[int, int]:
        """Enqueues a sequence of records. Returns (enqueued_count, duplicate_count)."""
        enqueued = 0
        duplicates = 0
        for rec in records:
            if self.enqueue(rec):
                enqueued += 1
            else:
                duplicates += 1
        return enqueued, duplicates

    def route_to_dlq(
        self,
        platform: str,
        raw_payload: str | dict[str, Any] | bytes,
        error_code: str,
        error_message: str,
    ) -> str:
        """Stores a malformed or rejected payload into the Dead-Letter Queue."""
        dlq_id = f"dlq_{uuid.uuid4().hex[:12]}"
        now = time.time()

        if isinstance(raw_payload, bytes):
            payload_str = raw_payload.decode("utf-8", errors="replace")
        elif isinstance(raw_payload, dict):
            payload_str = json.dumps(raw_payload, default=str)
        else:
            payload_str = str(raw_payload)

        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO dead_letter_queue (
                dlq_id, platform, raw_payload, error_code, error_message, failed_at, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (dlq_id, platform, payload_str, error_code, error_message, now),
        )
        self._conn.commit()
        return dlq_id

    def record_restatement_delta(self, delta: RestatementDelta) -> str:
        """Logs an attribution restatement delta for audit and ledger reconciliation."""
        now = time.time()
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO restatement_audit (
                delta_id, platform, campaign_id, date, metric, original_val, restated_val, delta, audit_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                delta.idempotency_key,
                delta.platform,
                delta.campaign_id,
                delta.date,
                delta.metric_name,
                delta.original_value,
                delta.restated_value,
                delta.delta_value,
                delta.audit_hash,
                now,
            ),
        )
        self._conn.commit()
        return delta.idempotency_key

    def get_pending(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieves pending records from the staging queue."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT idempotency_key, platform, record_type, payload_json, payload_sha256, ingested_at, retry_count
            FROM staging_records
            WHERE status = 'pending'
            ORDER BY ingested_at ASC
            LIMIT ?;
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_processed(self, idempotency_key: str) -> None:
        """Marks a staged record as successfully processed."""
        now = time.time()
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE staging_records
            SET status = 'processed', processed_at = ?
            WHERE idempotency_key = ?;
            """,
            (now, idempotency_key),
        )
        self._conn.commit()

    def drain_to_ledger(
        self,
        ledger: FinancialLedger,
        account_map: dict[str, str] | None = None,
        limit: int = 500,
    ) -> int:
        """Processes pending staging events into the double-entry FinancialLedger.

        Settlement records post:
          - Debit: Cash / Settlement Receivable
          - Credit: Revenue
          - Debit: Gateway Fees
        Spend records post:
          - Debit: Marketing Ad Spend
          - Credit: Accounts Payable / Clearing
        """
        acc = {
            "cash": "Bank_Cash",
            "revenue": "Gross_Revenue",
            "fees": "Merchant_Fees",
            "reserves": "Rolling_Reserve",
            "ad_spend": "Ad_Spend_Expense",
            "ad_payable": "Ad_Spend_Payable",
        }
        if account_map:
            acc.update(account_map)

        # Ensure accounts exist in the ledger
        declared = ledger.accounts
        for acc_name in acc.values():
            if acc_name not in declared:
                ledger.declare_account(acc_name, currency="USD")

        pending = self.get_pending(limit=limit)
        posted_count = 0

        for item in pending:
            key = item["idempotency_key"]
            rec_type = item["record_type"]
            payload = json.loads(item["payload_json"])
            curr = payload.get("currency", "USD")

            # Ensure account for this currency exists
            for acc_name in acc.values():
                if acc_name not in ledger.accounts:
                    ledger.declare_account(acc_name, currency=curr)

            ts = float(item["ingested_at"])

            if rec_type == "settlement":
                gross_dollars = payload["gross_cents"] / 100.0
                fees_dollars = payload.get("fee_cents", 0) / 100.0
                reserve_dollars = payload.get("reserve_hold_cents", 0) / 100.0
                net_dollars = payload["net_cash_cents"] / 100.0
                tx_id = f"tx_stl_{key[:16]}"

                if payload.get("status") == "settled":
                    postings: list[tuple[str, str, float]] = [
                        (acc["cash"], "debit", net_dollars),
                        (acc["revenue"], "credit", gross_dollars),
                    ]
                    if fees_dollars > 0:
                        postings.append((acc["fees"], "debit", fees_dollars))
                    if reserve_dollars > 0:
                        postings.append((acc["reserves"], "debit", reserve_dollars))

                    ledger.post(
                        tx_id=tx_id,
                        timestamp=ts,
                        postings=postings,  # type: ignore[arg-type]
                        description=f"Settlement {payload['settlement_id']} from {payload['gateway']}",
                        idempotency_key=f"tx:{key}",
                    )
                    posted_count += 1
                elif payload.get("status") == "refunded":
                    ledger.post(
                        tx_id=tx_id,
                        timestamp=ts,
                        postings=[
                            (acc["revenue"], "debit", gross_dollars),
                            (acc["cash"], "credit", gross_dollars),
                        ],  # type: ignore[arg-type]
                        description=f"Refund {payload['settlement_id']}",
                        idempotency_key=f"tx:{key}",
                    )
                    posted_count += 1

            elif rec_type == "spend":
                spend_dollars = payload["spend_cents"] / 100.0
                if spend_dollars > 0:
                    tx_id = f"tx_sp_{key[:16]}"
                    ledger.post(
                        tx_id=tx_id,
                        timestamp=ts,
                        postings=[
                            (acc["ad_spend"], "debit", spend_dollars),
                            (acc["ad_payable"], "credit", spend_dollars),
                        ],  # type: ignore[arg-type]
                        description=f"Ad spend {payload['campaign_id']} on {payload['platform']}",
                        idempotency_key=f"tx:{key}",
                    )
                    posted_count += 1

            self.mark_processed(key)

        return posted_count

    def list_dlq(self, resolved: bool | None = False, limit: int = 100) -> list[dict[str, Any]]:
        """Lists records in the dead-letter queue."""
        cursor = self._conn.cursor()
        if resolved is None:
            cursor.execute(
                "SELECT dlq_id, platform, raw_payload, error_code, error_message, failed_at, resolved FROM dead_letter_queue ORDER BY failed_at DESC LIMIT ?;",
                (limit,),
            )
        else:
            cursor.execute(
                "SELECT dlq_id, platform, raw_payload, error_code, error_message, failed_at, resolved FROM dead_letter_queue WHERE resolved = ? ORDER BY failed_at DESC LIMIT ?;",
                (1 if resolved else 0, limit),
            )
        return [dict(row) for row in cursor.fetchall()]

    def reprocess_dlq(self, dlq_id: str) -> bool:
        """Marks a DLQ record as resolved."""
        cursor = self._conn.cursor()
        cursor.execute("UPDATE dead_letter_queue SET resolved = 1 WHERE dlq_id = ?;", (dlq_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def count_staging(self) -> dict[str, int]:
        """Returns count of staging records grouped by status."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT status, count(*) FROM staging_records GROUP BY status;")
        counts = {"pending": 0, "processed": 0, "failed": 0}
        for status, count in cursor.fetchall():
            counts[status] = count
        return counts

    def count_dlq(self) -> int:
        """Returns total count of unresolved DLQ records."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT count(*) FROM dead_letter_queue WHERE resolved = 0;")
        return cursor.fetchone()[0]

    def close(self) -> None:
        self._conn.close()
