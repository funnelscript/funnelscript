"""Independent Phase 007E restart, integrity and exact accounting contracts."""

from dataclasses import replace
from decimal import Decimal as D
from hashlib import sha256
import json
import os
import subprocess
import sys

import pytest

from funnelscript.stdlib import marketing
from test_financial_consequence_provenance import operation, post, scenario
from test_transaction_provenance import policy, trial


def fixture(writeoff=False):
    population, sales, actions = scenario(writeoff=writeoff)
    return population, sales, actions, post(population, sales, actions)


def export(writeoff=False):
    population, _, _, linked = fixture(writeoff)
    return population, marketing.export_audit(population, policy(), linked)


def restore(data, population=None, *, anchor=None):
    return marketing.restore_audit(data, population or trial(), policy(), expected_sha256=anchor)


def test_phase007e_public_contract_is_available():
    for name in ("export_audit", "restore_audit", "replay_audit", "write_audit_checkpoint", "read_audit_checkpoint"):
        assert callable(getattr(marketing, name, None)), f"missing required financial audit behavior: {name}"


def test_oracle_restoration_and_deterministic_export():
    population, sales, actions, original = fixture()
    evidence = marketing.export_audit(population, policy(), original)
    assert evidence == marketing.export_audit(population, policy(), post(population, sales, tuple(reversed(actions))))
    recovered = restore(evidence, population)
    assert recovered == original
    assert marketing.export_audit(population, policy(), recovered) == evidence
    day1 = recovered.ledger.evaluate(until=1)
    day3 = recovered.ledger.evaluate()
    assert (day1.cash, day1.receivables, day1.recognized_revenue, day1.settled_receipts) == (D(75), D(60), D(60), D(0))
    assert (day3.cash, day3.receivables, day3.recognized_revenue, day3.settled_receipts, day3.profit) == (D(105), D(30), D(60), D(30), D(35))


def test_writeoff_recovery_and_idempotent_replay():
    population, sales, actions, original = fixture(True)
    evidence = marketing.export_audit(population, policy(), original)
    once = marketing.replay_audit(evidence, population, policy(), actions=actions)
    twice = marketing.replay_audit(evidence, population, policy(), actions=(*actions, *actions))
    assert once == twice == original
    snap = twice.ledger.evaluate()
    assert (snap.cash, snap.receivables, snap.profit, snap.writeoffs) == (D(105), D(25), D(30), D(5))
    assert len(twice.ledger.entries) == 9


@pytest.mark.parametrize("change", [
    lambda a: replace(a, entry=replace(a.entry, amount=D(11))),
    lambda a: replace(a, entry=replace(a.entry, kind="writeoff")),
    lambda a: replace(a, authorization_id="different-permit"),
    lambda a: replace(a, actor_id="different-actor"),
    lambda a: replace(a, entry=replace(a.entry, trial_id="foreign-trial")),
    lambda a: replace(a, entry=replace(a.entry, currency="USD")),
])
def test_replayed_conflicting_financial_identity_is_rejected(change):
    pop, _, actions, linked = fixture()
    data = marketing.export_audit(pop, policy(), linked)
    with pytest.raises(ValueError):
        marketing.replay_audit(data, pop, policy(), actions=(change(actions[2]),))


def test_authorization_conflict_and_new_transaction_extension():
    pop, _, actions, linked = fixture()
    data = marketing.export_audit(pop, policy(), linked)
    other = operation("new-cost", "other_cost", 0, "2.00", authorization=actions[0].authorization_id)
    with pytest.raises(ValueError, match="authorization"):
        marketing.replay_audit(data, pop, policy(), actions=(other,))
    valid = operation("new-cost", "other_cost", 0, "2.00")
    extended = marketing.replay_audit(data, pop, policy(), actions=(valid,))
    assert extended.ledger.evaluate().cash == D(103)
    assert restore(marketing.export_audit(pop, policy(), extended), pop) == extended


def test_reject_replay_with_invalid_source_or_horizon():
    pop, sales, _, linked = fixture()
    data = marketing.export_audit(pop, policy(), linked)
    for action in (
        operation("foreign-source", "settlement", 3, 1, source="unknown-sale"),
        operation("too-early", "settlement", 1, 1, source=sales[0].entry.tx_id),
        operation("too-much", "settlement", 3, 100, source=sales[0].entry.tx_id),
        operation("future", "ad_spend", 4, 1),
    ):
        with pytest.raises(ValueError):
            marketing.replay_audit(data, pop, policy(), actions=(action,))


def test_mismatched_world_trace_or_policy_is_rejected():
    pop, _, _, linked = fixture()
    data = marketing.export_audit(pop, policy(), linked)
    with pytest.raises(ValueError):
        restore(data, trial(trial_id="other-trial"))
    with pytest.raises(ValueError):
        restore(data, replace(pop, steps={}))
    with pytest.raises(ValueError):
        marketing.restore_audit(data, pop, replace(policy(), amount=D(22)))


@pytest.mark.parametrize("change", [
    lambda obj: obj["payload"]["entries"][0].update(amount_minor=99999),
    lambda obj: obj["payload"]["entries"].reverse(),
    lambda obj: obj["payload"]["actions"][0].update(authorization_id="forged"),
    lambda obj: obj["payload"]["sales"][0]["provenance"].update(agent_id="forged"),
    lambda obj: obj.update(schema="unsupported-v9"),
])
def test_modified_evidence_fails_integrity_or_schema(change):
    pop, data = export()
    obj = json.loads(data)
    change(obj)
    with pytest.raises(ValueError):
        restore(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode(), pop)


def test_noncanonical_reencoded_and_truncated_evidence_rejected():
    pop, data = export()
    for damaged in (data[:-3], data + b" ", data.replace(b'"payload"', b'"extra":42,"payload"', 1), b"{}"):
        with pytest.raises(ValueError):
            restore(damaged, pop)


def test_external_trusted_digest_detects_coordinated_rewrite():
    pop, data = export()
    manifest = sha256(data).hexdigest()
    assert restore(data, pop, anchor=manifest)
    obj = json.loads(data)
    obj["payload"]["actions"][0]["actor_id"] = "another-finance-actor"
    payload = json.dumps(obj["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    obj["sha256"] = sha256(b"funnelscript:financial-audit:v1\x00" + payload).hexdigest()
    forged = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    assert restore(forged, pop)  # integrity alone never proves authorization
    with pytest.raises(ValueError, match="anchor"):
        restore(forged, pop, anchor=manifest)


def test_atomic_checkpoint_and_restart_with_repeated_read(tmp_path):
    pop, data = export(True)
    path = tmp_path / "ledger.audit"
    marketing.write_audit_checkpoint(path, data)
    assert marketing.read_audit_checkpoint(path) == data
    for _ in range(3):
        assert restore(marketing.read_audit_checkpoint(path), pop).ledger.evaluate().cash == D(105)
    assert not list(tmp_path.glob("*.tmp"))


def test_interrupted_publication_retains_last_committed_record(tmp_path, monkeypatch):
    pop, data = export()
    path = tmp_path / "checkpoint.audit"
    marketing.write_audit_checkpoint(path, data)
    def fail_rename(*args):
        raise OSError("injected interruption before checkpoint commit")
    monkeypatch.setattr(os, "replace", fail_rename)
    with pytest.raises(OSError, match="injected"):
        marketing.write_audit_checkpoint(path, export(True)[1])
    assert marketing.read_audit_checkpoint(path) == data
    assert restore(marketing.read_audit_checkpoint(path), pop)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["checkpoint.audit"]


def test_corrupted_persisted_file_fails_closed(tmp_path):
    pop, data = export()
    path = tmp_path / "checkpoint.audit"
    path.write_bytes(data[:len(data) // 2])
    with pytest.raises(ValueError):
        restore(marketing.read_audit_checkpoint(path), pop)


def test_independent_process_hash_seed_audit_identity():
    _, data = export(True)
    script = "from funnelscript.stdlib import marketing; from test_financial_consequence_provenance import scenario,post; from test_transaction_provenance import policy; import hashlib; p,s,a=scenario(writeoff=True);print(hashlib.sha256(marketing.export_audit(p,policy(),post(p,s,a))).hexdigest())"
    results = []
    for seed in ("1", "1234"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)}
        output = subprocess.check_output([sys.executable, "-c", script], env=env, text=True)
        results.append(output.strip())
    assert results == [sha256(data).hexdigest()] * 2


def test_explicit_financial_operation_ownership_categories():
    _, data = export(True)
    raw = json.loads(data)
    assert {item["ownership"] for item in raw["payload"]["sales"]} == {"world_event"}
    assert {item["ownership"] for item in raw["payload"]["actions"]} == {"external_declaration"}


def test_committed_checkpoint_replacement_is_restorable(tmp_path):
    pop, original = export(False)
    _, updated = export(True)
    path = tmp_path / "committed.audit"
    marketing.write_audit_checkpoint(path, original)
    assert restore(marketing.read_audit_checkpoint(path), pop).ledger.evaluate().writeoffs == D(0)
    marketing.write_audit_checkpoint(path, updated)
    assert restore(marketing.read_audit_checkpoint(path), pop).ledger.evaluate().writeoffs == D(5)
    assert marketing.read_audit_checkpoint(path) == updated


def test_audit_records_the_exact_source_provenance_version():
    _, data = export()
    payload = json.loads(data)["payload"]
    assert payload["provenance_version"] == "world-event-sale-v1"
