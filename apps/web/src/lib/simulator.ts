import type { StrategyAST, SimulationResult, MetricDistribution } from '../types';

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

export function runInBrowserSimulation(ast: StrategyAST, trialsCount = 50, agentsCount = 10000): SimulationResult {
  const timeframe = ast.simulation_engine.parameters.timeframe_days || 14;
  const totalBudget = ast.entities.budgets.total_budget;
  const maxCpc = ast.entities.budgets.max_cpc_limit;
  const initialCash = ast.entities.budgets.initial_cash || 10000;
  const settlementDelay = ast.entities.budgets.settlement_delay_days || 3;
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
  let totalCannibalized = 0;
  let totalConversionsGlobal = 0;

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
    let trialCannibalized = 0;
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
        const effectiveCpc = Math.min(maxCpc, baseCpc * (0.9 + Math.random() * 0.2));
        const numClicks = Math.floor(daySpend / effectiveCpc);
        const pBuy = Math.min(0.6, baseCr * (affinity / Math.max(0.1, priceSens)) * (1 + fomo * creativeScore * 0.15));
        const buys = Math.floor(numClicks * pBuy * (0.85 + Math.random() * 0.3));

        // Retargeting recovery
        const abandons = numClicks - buys;
        const discountPct = 0.15;
        const pRecover = Math.min(0.4, 0.05 * (affinity / (priceSens * (1 - discountPct))));
        const recovered = Math.floor(abandons * pRecover);

        const cannibalizedFromLoyal = affinity > 0.7 ? Math.floor(recovered * 0.6) : 0;
        trialCannibalized += cannibalizedFromLoyal;

        const dayTotalConv = buys + recovered;
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
    totalCannibalized += trialCannibalized;
    totalConversionsGlobal += trialConversions;

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

  const cannibalRate = totalConversionsGlobal > 0 ? totalCannibalized / totalConversionsGlobal : 0;

  return {
    strategy_name: ast.strategy_name,
    trials_count: trialsCount,
    agents_per_trial: agentsCount,
    timeframe_days: timeframe,
    roas: computeDist(roasTrials),
    cac: computeDist(cacTrials),
    spend: computeDist(spendTrials),
    revenue: computeDist(revTrials),
    probability_of_profit: roasTrials.filter((r) => r >= 1.0).length / trialsCount,
    cash_ruin_probability: Number((insolvencyCount / trialsCount).toFixed(3)),
    worst_case_drawdown: Math.max(...lossArr, 0),
    cannibalization_rate: Number(cannibalRate.toFixed(3)),
    var_95: Number(var95.toFixed(2)),
    cvar_95: Number(cvar95.toFixed(2)),
    daily_trajectories: trajectoryDays,
  };
}
