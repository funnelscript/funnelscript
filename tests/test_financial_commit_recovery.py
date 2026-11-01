"""Phase 007F black-box commit and receipt behavior against the existing oracle."""

from dataclasses import replace
from decimal import Decimal as D
from hashlib import sha256
import os
import subprocess
import sys

import pytest

from funnelscript.stdlib import marketing
from test_financial_consequence_provenance import operation, post, scenario
from test_transaction_provenance import policy


def case(writeoff=False):
    population, sales, actions = scenario(writeoff=writeoff)
    return population, actions, post(population, sales, actions)


def test_commit_receipt_public_contract(tmp_path):
    population, actions, linked = case()
    path = tmp_path / "financial.audit"
    receipt = marketing.commit_financial_checkpoint(path, population, policy(), linked)
    assert receipt.trial_id == population.trial_id
    assert receipt.audit_sha256 == sha256(path.read_bytes()).hexdigest()
    assert marketing.verify_financial_receipt(path, population, policy(), receipt) == linked
    assert marketing.recover_financial_checkpoint(path, population, policy())[1] == receipt
    assert marketing.FinancialCommitReceipt.from_bytes(receipt.to_bytes()) == receipt
    snapshot = marketing.recover_financial_checkpoint(path, population, policy())[0].ledger.evaluate()
    assert (snapshot.cash, snapshot.receivables, snapshot.profit) == (D(105), D(30), D(35))


def test_second_commit_idempotent_settlement_writeoff_and_independent_oracle(tmp_path):
    population, actions, first = case()
    path = tmp_path / "state.audit"
    one = marketing.commit_financial_checkpoint(path, population, policy(), first)
    assert marketing.commit_financial_checkpoint(path, population, policy(), first) == one
    _, _, second = case(writeoff=True)
    two = marketing.commit_financial_checkpoint(
        path, population, policy(), second, expected_receipt=one)
    assert two != one
    assert two.commit_id != one.commit_id
    assert marketing.commit_financial_checkpoint(
        path, population, policy(), second, expected_receipt=two) == two
    recovered, current = marketing.recover_financial_checkpoint(
        path, population, policy(), expected_receipt=two)
    assert current == two
    day1, day3 = recovered.ledger.evaluate(until=1), recovered.ledger.evaluate()
    assert (day1.cash, day1.receivables, day1.recognized_revenue,
            day1.settled_receipts) == (D(75), D(60), D(60), D(0))
    assert (day3.cash, day3.receivables, day3.recognized_revenue,
            day3.settled_receipts, day3.writeoffs, day3.profit) == (
                D(105), D(25), D(60), D(30), D(5), D(30))
    assert marketing.replay_audit(path.read_bytes(), population, policy(),
                                  actions=(*actions, *second.financial_actions)) == second


def test_changed_state_without_trusted_previous_anchor_fails_closed(tmp_path):
    population, _, first = case()
    path = tmp_path / "state.audit"
    one = marketing.commit_financial_checkpoint(path, population, policy(), first)
    _, _, second = case(writeoff=True)
    with pytest.raises(ValueError, match="previous receipt"):
        marketing.commit_financial_checkpoint(path, population, policy(), second)
    assert marketing.recover_financial_checkpoint(path, population, policy())[1] == one


def test_outdated_anchor_and_valid_old_checkpoint_substitution_are_detected(tmp_path):
    population, _, first = case()
    path = tmp_path / "state.audit"
    one = marketing.commit_financial_checkpoint(path, population, policy(), first)
    old_image = path.read_bytes()
    _, _, second = case(writeoff=True)
    two = marketing.commit_financial_checkpoint(
        path, population, policy(), second, expected_receipt=one)
    with pytest.raises(ValueError, match="stale"):
        marketing.verify_financial_receipt(path, population, policy(), one)
    path.write_bytes(old_image)  # valid older content, not a broken hash
    with pytest.raises(ValueError, match="stale"):
        marketing.recover_financial_checkpoint(
            path, population, policy(), expected_receipt=two)


@pytest.mark.parametrize("mutator", [
    lambda a: replace(a, entry=replace(a.entry, amount=D(12))),
    lambda a: replace(a, entry=replace(a.entry, kind="writeoff")),
    lambda a: replace(a, actor_id="different-actor"),
    lambda a: replace(a, authorization_id="different-permit"),
    lambda a: replace(a, entry=replace(a.entry, currency="USD")),
    lambda a: replace(a, entry=replace(a.entry, trial_id="foreign")),
])
def test_conflicting_candidate_never_replaces_checkpoint(tmp_path, mutator):
    population, _, first = case()
    path = tmp_path / "state.audit"
    receipt = marketing.commit_financial_checkpoint(path, population, policy(), first)
    before = path.read_bytes()
    bad_actions = list(first.financial_actions)
    bad_actions[-1] = mutator(bad_actions[-1])
    with pytest.raises((TypeError, ValueError)):
        invalid = marketing.post_authorized_trial(
            population, first.sales, policy(), actions=bad_actions,
            cash_initial=D(100), settlement_delay=2, horizon=3)
        marketing.commit_financial_checkpoint(
            path, population, policy(), invalid, expected_receipt=receipt)
    assert path.read_bytes() == before


def test_reused_authorization_and_removed_old_action_fail_before_publish(tmp_path):
    population, _, original = case()
    path = tmp_path / "state.audit"
    receipt = marketing.commit_financial_checkpoint(path, population, policy(), original)
    before = path.read_bytes()
    _, _, updated = case(writeoff=True)
    reused = replace(updated.financial_actions[-1],
                     authorization_id=original.financial_actions[0].authorization_id)
    with pytest.raises(ValueError, match="authorization"):
        marketing.post_authorized_trial(
            population, updated.sales, policy(),
            actions=(*updated.financial_actions[:-1], reused),
            cash_initial=D(100), settlement_delay=2, horizon=3)
    with pytest.raises(ValueError, match="discard"):
        removed = post(population, original.sales, original.financial_actions[:-1])
        marketing.commit_financial_checkpoint(
            path, population, policy(), removed, expected_receipt=receipt)
    assert path.read_bytes() == before


def test_receipt_mutations_wrong_trial_world_policy_and_damage_fail_closed(tmp_path):
    population, _, original = case()
    path = tmp_path / "state.audit"
    receipt = marketing.commit_financial_checkpoint(path, population, policy(), original)
    for changed in (
        replace(receipt, audit_sha256="0" * 64),
        replace(receipt, commit_id="f" * 64),
        replace(receipt, trial_id="wrong"),
        replace(receipt, state_sha256="a" * 64),
        replace(receipt, transaction_ids=receipt.transaction_ids[:-1]),
    ):
        with pytest.raises(ValueError, match="mismatch"):
            marketing.verify_financial_receipt(path, population, policy(), changed)
    from test_transaction_provenance import trial
    with pytest.raises(ValueError):
        marketing.verify_financial_receipt(path, trial(trial_id="another"), policy(), receipt)
    with pytest.raises(ValueError):
        marketing.verify_financial_receipt(path, replace(population, steps={}), policy(), receipt)
    with pytest.raises(ValueError):
        marketing.verify_financial_receipt(path, population, replace(policy(), amount=D(12)), receipt)
    for bad in (b"{}", receipt.to_bytes()[:-1], receipt.to_bytes() + b" ",
                receipt.to_bytes().replace(b"receipt-v1", b"receipt-v9")):
        with pytest.raises(ValueError):
            marketing.FinancialCommitReceipt.from_bytes(bad)
    path.write_bytes(path.read_bytes()[:10])
    with pytest.raises(ValueError):
        marketing.recover_financial_checkpoint(path, population, policy())


@pytest.mark.parametrize("failure_point", ["temporary_create", "file_sync", "rename", "dir_sync"])
def test_publication_failure_never_returns_success_ack(tmp_path, monkeypatch, failure_point):
    population, _, first = case()
    path = tmp_path / "state.audit"
    one = marketing.commit_financial_checkpoint(path, population, policy(), first)
    _, _, second = case(writeoff=True)
    if failure_point == "temporary_create":
        import tempfile
        def fail(*args, **kwargs):
            raise OSError("injected before temporary write")
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail)
    elif failure_point in ("file_sync", "dir_sync"):
        original_fsync = os.fsync
        calls = []
        def fail_sync(fd):
            calls.append(fd)
            if (failure_point == "file_sync" and len(calls) == 1 or
                    failure_point == "dir_sync" and len(calls) == 2):
                raise OSError("injected synchronization failure")
            return original_fsync(fd)
        monkeypatch.setattr(os, "fsync", fail_sync)
    else:
        def fail_rename(*args):
            raise OSError("injected rename failure")
        monkeypatch.setattr(os, "replace", fail_rename)
    with pytest.raises(marketing.CommitOutcomeUncertain):
        marketing.commit_financial_checkpoint(
            path, population, policy(), second, expected_receipt=one)
    recovered, observed = marketing.recover_financial_checkpoint(path, population, policy())
    if failure_point == "dir_sync":
        assert recovered == second
        assert observed != one
    else:
        assert recovered == first
        assert observed == one


def test_ambiguous_post_rename_commit_resolved_by_restart_recovery(tmp_path, monkeypatch):
    population, _, first = case()
    path = tmp_path / "state.audit"
    one = marketing.commit_financial_checkpoint(path, population, policy(), first)
    _, _, second = case(writeoff=True)
    normal_fsync = os.fsync
    calls = 0
    def disrupt_directory_sync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("ack lost after namespace replacement")
        return normal_fsync(fd)
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "fsync", disrupt_directory_sync)
        with pytest.raises(marketing.CommitOutcomeUncertain):
            marketing.commit_financial_checkpoint(
                path, population, policy(), second, expected_receipt=one)
    recovered, two = marketing.recover_financial_checkpoint(path, population, policy())
    assert recovered == second
    assert marketing.commit_financial_checkpoint(
        path, population, policy(), second, expected_receipt=two) == two
    assert len(recovered.ledger.entries) == len(second.ledger.entries)


def test_cross_process_receipt_determinism_and_recovery(tmp_path):
    population, _, linked = case(writeoff=True)
    path = tmp_path / "state.audit"
    receipt = marketing.commit_financial_checkpoint(path, population, policy(), linked)
    script = (
        "from funnelscript.stdlib import marketing; "
        "from test_financial_consequence_provenance import scenario; "
        "from test_transaction_provenance import policy; "
        "import sys; p,_,_=scenario(writeoff=True); "
        "linked,r=marketing.recover_financial_checkpoint(sys.argv[1],p,policy()); "
        "print(r.commit_id,linked.ledger.evaluate().cash)"
    )
    for seed in ("1", "777"):
        env = {**os.environ, "PYTHONHASHSEED": seed,
               "PYTHONPATH": os.pathsep.join(sys.path)}
        output = subprocess.check_output(
            [sys.executable, "-c", script, str(path)], env=env, text=True)
        assert output.strip() == f"{receipt.commit_id} 105.00"


def test_idempotent_retry_must_not_ack_when_durability_sync_fails(tmp_path, monkeypatch):
    population, _, linked = case()
    path = tmp_path / "state.audit"
    receipt = marketing.commit_financial_checkpoint(path, population, policy(), linked)
    def fail_sync(fd):
        raise OSError("injected filesystem sync failure on retry")
    monkeypatch.setattr(os, "fsync", fail_sync)
    with pytest.raises(marketing.CommitOutcomeUncertain):
        marketing.commit_financial_checkpoint(
            path, population, policy(), linked, expected_receipt=receipt)
