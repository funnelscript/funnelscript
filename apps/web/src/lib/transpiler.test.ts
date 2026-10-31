import { test, expect } from 'bun:test';
import { funnelScriptToGraph, graphToFunnelScript } from './transpiler';
import type { StrategyAST } from '../types';

const SAMPLE_AST: StrategyAST = {
  $schema: 'https://marketing-lang.org',
  strategy_name: 'Test_Strategy',
  metadata: { author: 'Engineer', industry: 'E-Comm', currency: 'USD' },
  environment: { market_volatility: 'low', competitor_activity: 'moderate' },
  entities: {
    budgets: { total_budget: 10000, max_cpc_limit: 1.0, initial_cash: 5000, settlement_delay_days: 2 },
    audiences: [
      {
        id: 'aud_1',
        name: 'Shoppers',
        type: 'cold',
        estimated_size: 50000,
        attributes: { brand_affinity: 0.6, price_sensitivity: 0.4, fomo_index: 0.5 },
      },
    ],
    touchpoints: [
      { id: 'tp_ad', type: 'paid_traffic', platform: 'Meta', base_cpc: 0.4, ad_creative_score: 0.8 },
      { id: 'tp_shop', type: 'conversion_surface', base_conversion_rate: 0.05 },
    ],
  },
  logic_flow: [
    { step: 1, action: 'TriggerTraffic', source: 'aud_1', via: 'tp_ad', destination: 'tp_shop' },
  ],
  simulation_engine: {
    engine_type: 'Agent-Based_Monte_Carlo',
    parameters: { virtual_agents_count: 10000, timeframe_days: 14, randomness_factor_sigma: 0.1 },
    output_metrics_requested: ['ROAS'],
  },
};

test('H_{5.1}: Bi-directional graph transpilation preserves topology and attributes', () => {
  const { nodes, edges } = funnelScriptToGraph(SAMPLE_AST);
  expect(nodes.length).toBe(3); // 1 audience + 2 touchpoints
  expect(edges.length).toBe(2); // aud -> ad -> shop

  const roundtripped = graphToFunnelScript(nodes, edges, SAMPLE_AST);
  expect(roundtripped.entities.audiences[0].id).toBe('aud_1');
  expect(roundtripped.entities.touchpoints.length).toBe(2);
});
