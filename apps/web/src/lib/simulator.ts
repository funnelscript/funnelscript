import type { StrategyAST, BrowserPreviewResult, SimulationResult, MetricDistribution } from '../types';

const LIMITATIONS = 'Single paid-traffic path only. Fixed illustrative order value ($120), simplified click/conversion and settlement assumptions. Not a calibrated forecast or Python World result. Audience estimated_size, environment, virtual_agents_count and randomness_factor_sigma are not modeled. No retargeting, multi-audience interaction or canvas-edge simulation.';

function unsupportedReason(ast: StrategyAST, trialsCount: number, seed: number): string | null {
  if (!Number.isInteger(trialsCount) || trialsCount < 1 || trialsCount > 500) {
    return 'Trial count must be an integer between 1 and 500.';
  }
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) {
    return 'The illustration requires a 32-bit unsigned seed.';
  }
  if (!ast?.entities?.budgets || !Array.isArray(ast.entities.audiences) ||
      !Array.isArray(ast.entities.touchpoints) || !Array.isArray(ast.logic_flow) ||
      !ast.simulation_engine?.parameters) {
    return 'The StrategyAST is missing required scenario fields.';
  }
  const { audiences, touchpoints, budgets } = ast.entities;
  const steps = ast.logic_flow;
  if (audiences.length !== 1 || touchpoints.length !== 2 || steps.length !== 1) {
    return 'Only one audience, one paid touchpoint, one conversion surface, and one traffic step are supported. Conditional branches and retargeting are not modeled.';
  }
  if (!audiences[0]?.attributes || !steps[0] || touchpoints.some((t) => !t)) {
    return 'The declared audience, traffic step, or touchpoint is incomplete.';
  }
  const step = steps[0];
  const ad = touchpoints.find((t) => t.type === 'paid_traffic');
  const landing = touchpoints.find((t) => t.type === 'conversion_surface');
  if (!('action' in step) || step.action !== 'TriggerTraffic' ||
      !ad || !landing || step.source !== audiences[0].id ||
      step.via !== ad.id || step.destination !== landing.id) {
    return 'Traffic edges must connect the declared audience, paid touchpoint, and conversion surface.';
  }
  const days = ast.simulation_engine.parameters.timeframe_days;
  if (!Number.isInteger(days) || days < 1 || days > 365 ||
      !Number.isInteger(budgets.settlement_delay_days) ||
      budgets.settlement_delay_days < 0 || budgets.settlement_delay_days > 365) {
    return 'Timeframe and settlement delay must be bounded whole-day values (1–365 and 0–365).';
  }
  if (![budgets.total_budget, budgets.initial_cash].every((n) => Number.isFinite(n) && n >= 0) ||
      !Number.isFinite(budgets.max_cpc_limit) || budgets.max_cpc_limit <= 0) {
    return 'Budgets and cash must be finite and nonnegative; maximum CPC must be positive.';
  }
  const { brand_affinity, price_sensitivity, fomo_index } = audiences[0].attributes;
  const bounded = (n: number) => Number.isFinite(n) && n >= 0 && n <= 1;
  if (![brand_affinity, price_sensitivity, fomo_index, ad.ad_creative_score, landing.base_conversion_rate].every(
    (n) => n !== undefined && bounded(n)
  ) || !Number.isFinite(ad.base_cpc) || ad.base_cpc! <= 0) {
    return 'Illustrative audience, ad creative and landing rates must be explicit and bounded; ad CPC must be positive.';
  }
  return null;
}

function createSeededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function computeDist(arr: number[]): MetricDistribution {
  if (arr.length === 0) return { mean: 0, median: 0, p10: 0, p90: 0 };
  const sorted = [...arr].sort((a, b) => a - b);
  const p10 = sorted[Math.floor(sorted.length * 0.1)] || 0;
  const p50 = sorted[Math.floor(sorted.length * 0.5)] || 0;
  const p90 = sorted[Math.floor(sorted.length * 0.9)] || 0;
  const sum = arr.reduce((acc, val) => acc + val, 0);
  return {
    mean: Number((sum / arr.length).toFixed(2)),
    median: Number(p50.toFixed(2)),
    p10: Number(p10.toFixed(2)),
    p90: Number(p90.toFixed(2)),
  };
}

export function runInBrowserSimulation(ast: StrategyAST, trialsCount = 50, seed = 12345): BrowserPreviewResult {
  const reason = unsupportedReason(ast, trialsCount, seed);
  if (reason) return { status: 'unsupported', reason };
  const random = createSeededRandom(seed);
  const timeframe = ast.simulation_engine.parameters.timeframe_days;
  const totalBudget = ast.entities.budgets.total_budget;
  const maxCpc = ast.entities.budgets.max_cpc_limit;
  const initialCash = ast.entities.budgets.initial_cash;
  const settlementDelay = ast.entities.budgets.settlement_delay_days;
  const dailyBudget = totalBudget / timeframe;
  const aov = 120.0;

  const aud = ast.entities.audiences[0];
  const affinity = aud?.attributes.brand_affinity ?? 0.5;
  const priceSens = aud?.attributes.price_sensitivity ?? 0.45;
  const fomo = aud?.attributes.fomo_index ?? 0.6;

  const adTouchpoint = ast.entities.touchpoints.find((t) => t.type === 'paid_traffic');
  const baseCpc = adTouchpoint?.base_cpc ?? 0.5;
  const creativeScore = adTouchpoint?.ad_creative_score ?? 0.8;

  const landingTouchpoint = ast.entities.touchpoints.find((t) => t.type === 'conversion_surface');
  const baseCr = landingTouchpoint?.base_conversion_rate ?? 0.045;

  const roasTrials: number[] = [];
  const cacTrials: number[] = [];
  const spendTrials: number[] = [];
  const revTrials: number[] = [];
  let insolvencyCount = 0;

  const trajectoryDays = Array.from({ length: timeframe }, (_, i) => ({
    day: i + 1,
    spend: 0,
    revenue: 0,
    liquid_cash: 0,
  }));

  for (let trial = 0; trial < trialsCount; trial++) {
    let liquidCash = initialCash;
    let trialSpend = 0;
    let trialClicks = 0;
    let trialConversions = 0;
    let insolvencyTriggered = false;

    const receivables = new Array(timeframe + settlementDelay + 5).fill(0);

    for (let day = 0; day < timeframe; day++) {
      // Collect settled cash
      liquidCash += receivables[day] || 0;

      // Minimum operating reserve check
      if (liquidCash < 50) {
        insolvencyTriggered = true;
      }

      const daySpend = Math.min(dailyBudget, Math.max(0, liquidCash - 50));
      if (daySpend < dailyBudget * 0.5 && trialSpend < totalBudget) {
        insolvencyTriggered = true;
      }

      let dayConversions = 0;

      if (daySpend > 0) {
        const effectiveCpc = Math.min(maxCpc, baseCpc * (0.9 + random() * 0.2));
        const numClicks = Math.floor(daySpend / effectiveCpc);
        const pBuy = Math.min(0.6, baseCr * (affinity / Math.max(0.1, priceSens)) * (1 + fomo * creativeScore * 0.15));
        const dayTotalConv = Math.floor(numClicks * pBuy * (0.85 + random() * 0.3));
        dayConversions += dayTotalConv;
        trialClicks += numClicks;
        trialSpend += daySpend;
        liquidCash -= daySpend;

        // Schedule settlement
        const payoutDay = day + settlementDelay;
        if (payoutDay < receivables.length) {
          receivables[payoutDay] += dayTotalConv * aov * 0.971;
        }
      }

      trialConversions += dayConversions;

      if (trial === 0) {
        trajectoryDays[day].spend += daySpend;
        trajectoryDays[day].revenue += dayConversions * aov;
        trajectoryDays[day].liquid_cash += liquidCash;
      }
    }

    if (insolvencyTriggered) insolvencyCount++;

    const rev = trialConversions * aov;
    const roas = trialSpend > 0 ? rev / trialSpend : 0;
    const cac = trialConversions > 0 ? trialSpend / trialConversions : 0;

    roasTrials.push(roas);
    cacTrials.push(cac);
    spendTrials.push(trialSpend);
    revTrials.push(rev);
  }

  const lossArr = spendTrials.map((s, i) => Math.max(0, s - revTrials[i]));
  const sortedLosses = [...lossArr].sort((a, b) => a - b);
  const var95 = sortedLosses[Math.floor(sortedLosses.length * 0.95)] || 0;
  const tail = sortedLosses.filter((l) => l >= var95);
  const cvar95 = tail.length > 0 ? tail.reduce((a, b) => a + b, 0) / tail.length : var95;

  const metrics: SimulationResult = {
    strategy_name: ast.strategy_name,
    trials_count: trialsCount,
    timeframe_days: timeframe,
    roas: computeDist(roasTrials),
    cac: computeDist(cacTrials),
    spend: computeDist(spendTrials),
    revenue: computeDist(revTrials),
    probability_of_profit: roasTrials.filter((r) => r >= 1.0).length / trialsCount,
    cash_ruin_probability: Number((insolvencyCount / trialsCount).toFixed(3)),
    worst_case_drawdown: Math.max(...lossArr, 0),
    var_95: Number(var95.toFixed(2)),
    cvar_95: Number(cvar95.toFixed(2)),
    daily_trajectories: trajectoryDays,
  };
  return { status: 'illustrative', metrics, limitations: LIMITATIONS };
}
