import { describe, expect, test } from 'bun:test';
import type { StrategyAST } from '../types';
import { runInBrowserSimulation } from './simulator';

const BASE: StrategyAST = {
  $schema: 'https://marketing-lang.org',
  strategy_name: 'Single_Path',
  metadata: { author: 'Test', industry: 'Synthetic', currency: 'USD' },
  environment: { market_volatility: 'low', competitor_activity: 'passive' },
  entities: {
    budgets: { total_budget: 10000, max_cpc_limit: 2, initial_cash: 20000, settlement_delay_days: 2 },
    audiences: [{
      id: 'aud', name: 'Test cohort', type: 'cold', estimated_size: 5000,
      attributes: { brand_affinity: 0.7, price_sensitivity: 0.5, fomo_index: 0.3 },
    }],
    touchpoints: [
      { id: 'ad', type: 'paid_traffic', base_cpc: 0.8, ad_creative_score: 0.75 },
      { id: 'landing', type: 'conversion_surface', base_conversion_rate: 0.05 },
    ],
  },
  logic_flow: [{ step: 1, action: 'TriggerTraffic', source: 'aud', via: 'ad', destination: 'landing' }],
  simulation_engine: {
    engine_type: 'Agent-Based_Monte_Carlo',
    parameters: { virtual_agents_count: 50000, timeframe_days: 7, randomness_factor_sigma: 0.1 },
    output_metrics_requested: ['ROAS'],
  },
};

const input = (): StrategyAST => structuredClone(BASE);

describe('browser preview is explicitly illustrative, not a World simulation', () => {
  test('supported single-path scenario is a typed illustrative result', () => {
    const result = runInBrowserSimulation(input(), 8, 12345);
    expect(result.status).toBe('illustrative');
    if (result.status !== 'illustrative') return;
    expect(result.metrics.roas.mean).toBeGreaterThan(0);
    expect(result.limitations).toContain('virtual_agents_count');
    expect(result.metrics).not.toHaveProperty('agents_per_trial');
  });

  test('conditional branches are unsupported instead of silently ignored', () => {
    const ast = input();
    ast.logic_flow.push({
      step: 2, type: 'ConditionalBranch', condition: { user_action: 'AbandonCart' },
      true_branch: [{ action: 'DoNothing' }], false_branch: [{ action: 'DoNothing' }],
    });
    const result = runInBrowserSimulation(ast, 8, 12345);
    expect(result.status).toBe('unsupported');
    expect(result).not.toHaveProperty('metrics');
  });

  test('multiple audiences cannot be silently reduced to the first cohort', () => {
    const ast = input();
    ast.entities.audiences.push({ ...ast.entities.audiences[0], id: 'aud2' });
    expect(runInBrowserSimulation(ast).status).toBe('unsupported');
  });

  test('broken graph references and missing conversion nodes are rejected', () => {
    const disconnected = input();
    if ('action' in disconnected.logic_flow[0]) disconnected.logic_flow[0].destination = 'nonexistent';
    expect(runInBrowserSimulation(disconnected).status).toBe('unsupported');
    const missing = input();
    missing.entities.touchpoints.pop();
    expect(runInBrowserSimulation(missing).status).toBe('unsupported');
  });

  test('repeated seed and input have identical metrics; distinct seed affects results', () => {
    const a = runInBrowserSimulation(input(), 20, 31);
    const b = runInBrowserSimulation(input(), 20, 31);
    const c = runInBrowserSimulation(input(), 20, 750000);
    expect(a).toEqual(b);
    expect(a.status).toBe('illustrative');
    expect(c.status).toBe('illustrative');
    if (a.status !== 'illustrative' || c.status !== 'illustrative') return;
    expect(a.metrics.revenue).not.toEqual(c.metrics.revenue);
  });

  test('changing modeled conversion probability changes the estimate', () => {
    const baseline = runInBrowserSimulation(input(), 10, 11);
    const highConversion = input();
    highConversion.entities.touchpoints[1].base_conversion_rate = 0.20;
    const changed = runInBrowserSimulation(highConversion, 10, 11);
    expect(baseline.status).toBe('illustrative');
    expect(changed.status).toBe('illustrative');
    if (baseline.status !== 'illustrative' || changed.status !== 'illustrative') return;
    expect(changed.metrics.revenue.mean).toBeGreaterThan(baseline.metrics.revenue.mean);
  });

  test('virtual population is not modeled and does not become an invented result count', () => {
    const ast = input();
    const baseline = runInBrowserSimulation(ast, 5, 19);
    ast.simulation_engine.parameters.virtual_agents_count = 5;
    const changed = runInBrowserSimulation(ast, 5, 19);
    expect(baseline).toEqual(changed);
  });

  test('malformed strategy AST fails closed without leaking a runtime exception', () => {
    expect(runInBrowserSimulation({} as StrategyAST).status).toBe('unsupported');
  });

  test('rejects unsafe input sizes and invalid financial parameters', () => {
    expect(runInBrowserSimulation(input(), 1000000, 2).status).toBe('unsupported');
    const ast = input();
    ast.simulation_engine.parameters.timeframe_days = 1000000;
    expect(runInBrowserSimulation(ast, 5, 2).status).toBe('unsupported');
    ast.simulation_engine.parameters.timeframe_days = 7;
    ast.entities.budgets.max_cpc_limit = 0;
    expect(runInBrowserSimulation(ast, 5, 2).status).toBe('unsupported');
  });
});
