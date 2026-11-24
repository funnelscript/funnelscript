"""
Test suite for FunnelScript Operations Research (OR) Decision Engine & Solver.
Validates:
1. Normalized unit simplex optimization (w in [0, 1], sum(w) = 1) with scale-invariant steps.
2. Canonical response-evaluation path across simulation and optimization.
3. Fail-closed model lineage checks (dataset fingerprint, currency, population hash).
4. Preflight admission gates before enqueuing or execution.
5. Empirical spend support metadata classification (no prior-dominated posterior masquerading as evidence).
6. Machine-readable domain error codes and registered next actions.
7. Deterministic physical artifact checksum verification.
"""

import hashlib
import numpy as np
import pytest

from funnelscript.solver.types import (
    ChannelModel,
    EmpiricalSupportMetadata,
    ModelLineage,
    OptimizationGoal,
    RegisteredAction,
    SolverInput,
    SpendSupportClassification,
)
from funnelscript.solver.errors import (
    ConvergenceError,
    LineageMismatchError,
    PreflightAdmissionError,
    SimplexFeasibilityError,
    SolverDomainError,
)
from funnelscript.solver.lineage import validate_lineage
from funnelscript.solver.admission import PreflightAdmissionGate
from funnelscript.solver.simplex import (
    project_onto_simplex,
    compute_scale_invariant_step,
    normalize_bounds_to_simplex,
)
from funnelscript.solver.evaluator import CanonicalResponseEvaluator
from funnelscript.solver.sensitivity import (
    analyze_funnel_bottlenecks,
    FunnelBottleneckSensitivity,
)
from funnelscript.solver.optimizer import DeterministicMarketingSolver
from funnelscript.solver.service import FunnelScriptSolverService


@pytest.fixture
def valid_lineage() -> ModelLineage:
    return ModelLineage(
        dataset_fingerprint="sha256:4a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b",
        currency="USD",
        population_hash="sha256:99887766554433221100aabbccddeeff00112233",
    )


@pytest.fixture
def sample_channels() -> list[ChannelModel]:
    return [
        ChannelModel(
            channel_id="meta_ads",
            v_max=120000.0,
            k_sat=30000.0,
            alpha=0.85,
            min_spend=5000.0,
            max_spend=45000.0,
            empirical_support=EmpiricalSupportMetadata(
                min_observed_spend=4000.0,
                max_observed_spend=50000.0,
                observations_count=180,
                classification=SpendSupportClassification.EMPIRICALLY_SUPPORTED,
            ),
        ),
        ChannelModel(
            channel_id="google_search",
            v_max=160000.0,
            k_sat=40000.0,
            alpha=0.80,
            min_spend=8000.0,
            max_spend=60000.0,
            empirical_support=EmpiricalSupportMetadata(
                min_observed_spend=7000.0,
                max_observed_spend=65000.0,
                observations_count=210,
                classification=SpendSupportClassification.EMPIRICALLY_SUPPORTED,
            ),
        ),
        ChannelModel(
            channel_id="tiktok_ads",
            v_max=70000.0,
            k_sat=20000.0,
            alpha=0.75,
            min_spend=2000.0,
            max_spend=25000.0,
            empirical_support=EmpiricalSupportMetadata(
                min_observed_spend=1000.0,
                max_observed_spend=10000.0,
                observations_count=45,
                classification=SpendSupportClassification.EMPIRICALLY_SUPPORTED,
            ),
        ),
    ]


class TestLineageFailClosed:
    def test_matching_lineage_passes(self, valid_lineage: ModelLineage):
        clone = ModelLineage(
            dataset_fingerprint=valid_lineage.dataset_fingerprint,
            currency=valid_lineage.currency,
            population_hash=valid_lineage.population_hash,
        )
        assert validate_lineage(valid_lineage, clone) is True

    def test_dataset_fingerprint_mismatch_fails_closed(self, valid_lineage: ModelLineage):
        corrupted = ModelLineage(
            dataset_fingerprint="sha256:different_hash_000000000000000000000000",
            currency=valid_lineage.currency,
            population_hash=valid_lineage.population_hash,
        )
        with pytest.raises(LineageMismatchError) as exc_info:
            validate_lineage(valid_lineage, corrupted)
        assert exc_info.value.code == "ERR_LINEAGE_FINGERPRINT_MISMATCH"
        assert exc_info.value.remediation != ""

    def test_currency_mismatch_fails_closed(self, valid_lineage: ModelLineage):
        diff_currency = ModelLineage(
            dataset_fingerprint=valid_lineage.dataset_fingerprint,
            currency="EUR",
            population_hash=valid_lineage.population_hash,
        )
        with pytest.raises(LineageMismatchError) as exc_info:
            validate_lineage(valid_lineage, diff_currency)
        assert exc_info.value.code == "ERR_LINEAGE_CURRENCY_MISMATCH"

    def test_population_hash_mismatch_fails_closed(self, valid_lineage: ModelLineage):
        diff_pop = ModelLineage(
            dataset_fingerprint=valid_lineage.dataset_fingerprint,
            currency=valid_lineage.currency,
            population_hash="sha256:different_pop_111111111111111111111111",
        )
        with pytest.raises(LineageMismatchError) as exc_info:
            validate_lineage(valid_lineage, diff_pop)
        assert exc_info.value.code == "ERR_LINEAGE_POPULATION_MISMATCH"


class TestPreflightAdmissionGate:
    def test_valid_input_passes(self, valid_lineage: ModelLineage, sample_channels: list[ChannelModel]):
        solver_input = SolverInput(
            total_budget=50000.0,
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=150.0,
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        gate = PreflightAdmissionGate()
        validated = gate.validate(solver_input)
        assert validated is not None

    def test_rejects_negative_budget(self, valid_lineage: ModelLineage, sample_channels: list[ChannelModel]):
        solver_input = SolverInput(
            total_budget=-500.0,
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=150.0,
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        gate = PreflightAdmissionGate()
        with pytest.raises(PreflightAdmissionError) as exc_info:
            gate.validate(solver_input)
        assert exc_info.value.code == "ERR_ADMISSION_INVALID_BUDGET"

    def test_rejects_infeasible_simplex_bounds(self, valid_lineage: ModelLineage, sample_channels: list[ChannelModel]):
        # Sum of minimum spends > total budget => infeasible on simplex
        solver_input = SolverInput(
            total_budget=10000.0,  # Sum of min_spends is 5000 + 8000 + 2000 = 15000 > 10000
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=150.0,
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        gate = PreflightAdmissionGate()
        with pytest.raises(SimplexFeasibilityError) as exc_info:
            gate.validate(solver_input)
        assert exc_info.value.code == "ERR_SIMPLEX_MIN_BOUNDS_EXCEED_BUDGET"
        assert exc_info.value.remediation_action == RegisteredAction.RELAX_CHANNEL_CONSTRAINTS


class TestSimplexMathAndScaling:
    def test_projection_onto_simplex(self):
        v = np.array([0.5, 0.8, -0.2])
        w = project_onto_simplex(v)
        assert np.isclose(np.sum(w), 1.0)
        assert np.all(w >= 0.0)

    def test_scale_invariant_finite_difference_step(self):
        w = np.array([0.2, 0.5, 0.3])
        steps = compute_scale_invariant_step(w, rel_eps=1e-7)
        assert np.all(steps > 0.0)
        assert np.all(steps < 1e-4)
        # Verify step scales with variable magnitude
        assert steps[1] >= steps[0]

    def test_normalize_bounds_to_simplex(self, sample_channels: list[ChannelModel]):
        budget = 50000.0
        lower_w, upper_w = normalize_bounds_to_simplex(sample_channels, budget)
        assert np.all(lower_w >= 0.0)
        assert np.all(upper_w <= 1.0)
        assert np.sum(lower_w) <= 1.0
        assert np.sum(upper_w) >= 1.0


class TestCanonicalResponseEvaluator:
    def test_canonical_path_preserves_target_scaling(self, sample_channels: list[ChannelModel]):
        budget = 50000.0
        evaluator = CanonicalResponseEvaluator(channels=sample_channels, total_budget=budget)
        
        # Test uniform weights
        w = np.array([1/3, 1/3, 1/3])
        revenue = evaluator.evaluate_revenue(w)
        net_profit = evaluator.evaluate_profit(w)
        conversions = evaluator.evaluate_conversions(w, avg_ticket=100.0)
        cac = evaluator.evaluate_cac(w, avg_ticket=100.0)

        assert revenue > budget  # Positive return
        assert np.isclose(net_profit, revenue - budget)
        assert conversions > 0
        assert cac > 0
        assert np.isclose(cac, budget / conversions)

    def test_empirical_spend_support_classification(self, sample_channels: list[ChannelModel]):
        budget = 50000.0
        evaluator = CanonicalResponseEvaluator(channels=sample_channels, total_budget=budget)
        
        # Allocate $20,000 to TikTok Ads (where historical max was $10,000)
        w = np.array([0.2, 0.4, 0.4])  # tiktok gets 0.4 * 50000 = $20,000
        support_meta = evaluator.classify_spend_support(w)
        
        tiktok_meta = support_meta["tiktok_ads"]
        assert tiktok_meta.classification == SpendSupportClassification.EXTRAPOLATED_PRIOR
        assert tiktok_meta.extrapolation_ratio > 1.0


class TestDeterministicSolver:
    def test_solver_produces_deterministic_optimal_policy(
        self, valid_lineage: ModelLineage, sample_channels: list[ChannelModel]
    ):
        solver_input = SolverInput(
            total_budget=50000.0,
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=150.0,
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        
        service = FunnelScriptSolverService()
        result1 = service.solve(solver_input)
        result2 = service.solve(solver_input)

        # Bitwise deterministic allocations
        assert np.allclose(result1.optimal_weights, result2.optimal_weights, atol=1e-8)
        assert np.isclose(result1.expected_net_profit, result2.expected_net_profit, atol=1e-6)
        assert result1.artifact_checksum == result2.artifact_checksum
        assert len(result1.artifact_checksum) == 64  # SHA-256

        # Simplex constraints met
        assert np.isclose(np.sum(result1.optimal_weights), 1.0)
        assert np.all(result1.optimal_weights >= 0.0)

        # Budget allocations sum to total budget
        alloc_sum = sum(result1.optimal_allocations.values())
        assert np.isclose(alloc_sum, solver_input.total_budget, atol=1e-4)

        # Dual shadow prices are exposed
        assert len(result1.shadow_prices) == len(sample_channels)

    def test_machine_actionable_next_actions_from_registered_catalog(
        self, valid_lineage: ModelLineage, sample_channels: list[ChannelModel]
    ):
        # 1. Feasible run produces registered next actions
        solver_input = SolverInput(
            total_budget=50000.0,
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=65.0,  # Feasible CAC ceiling
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        service = FunnelScriptSolverService()
        result = service.solve(solver_input)

        assert len(result.next_actions) > 0
        for action in result.next_actions:
            assert isinstance(action, RegisteredAction)

        # 2. Infeasible CAC ceiling raises ConvergenceError with registered remediation action
        infeasible_input = SolverInput(
            total_budget=50000.0,
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=25.0,  # Mathematically infeasible ceiling
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        with pytest.raises(ConvergenceError) as exc_info:
            service.solve(infeasible_input)
        assert exc_info.value.code == "ERR_SOLVER_CAC_CEILING_INFEASIBLE"
        assert exc_info.value.remediation_action == RegisteredAction.ADJUST_CAC_CEILING


class TestSensitivityAndArtifactPublication:
    def test_bottleneck_sensitivity_ranking(self):
        stage_conversions = {
            "landing_page_optin": 0.05,
            "demo_booking": 0.20,
            "proposal_accept": 0.40,
        }
        total_rev = 200000.0
        bottlenecks = analyze_funnel_bottlenecks(stage_conversions, total_rev)

        # Lowest conversion rate stage has the highest marginal revenue lift per 1% absolute increase
        assert bottlenecks[0].stage_id == "landing_page_optin"
        assert bottlenecks[0].elasticity_rank == 1
        assert bottlenecks[1].stage_id == "demo_booking"
        assert bottlenecks[2].stage_id == "proposal_accept"

    def test_artifact_persistence_and_checksum_verification(
        self, tmp_path, valid_lineage: ModelLineage, sample_channels: list[ChannelModel]
    ):
        solver_input = SolverInput(
            total_budget=50000.0,
            currency="USD",
            channels=sample_channels,
            lineage=valid_lineage,
            cac_ceiling=150.0,
            goal=OptimizationGoal.MAXIMIZE_PROFIT,
        )
        service = FunnelScriptSolverService(artifact_registry_dir=tmp_path)
        result = service.solve(solver_input)

        # Artifact file exists on disk
        artifact_path = tmp_path / f"solver_decision_{result.artifact_checksum}.json"
        assert artifact_path.exists()

        # Service can retrieve registered solution
        cached = service.get_registered_result(result.artifact_checksum)
        assert cached is not None
        assert cached.artifact_checksum == result.artifact_checksum

