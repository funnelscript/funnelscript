export interface PsychographicAttributes {
  brand_affinity: number; // [0, 1]
  price_sensitivity: number; // [0, 1]
  fomo_index: number; // [0, 1]
}

export interface Audience {
  id: string;
  name: string;
  type: 'cold' | 'warm' | 'retargeting';
  estimated_size: number;
  attributes: PsychographicAttributes;
}

export interface Touchpoint {
  id: string;
  type: 'paid_traffic' | 'conversion_surface' | 'retargeting_channel';
  platform?: string;
  medium?: string;
  base_cpc?: number;
  ad_creative_score?: number;
  base_conversion_rate?: number;
  base_open_rate?: number;
}

export interface Budgets {
  total_budget: number;
  max_cpc_limit: number;
  initial_cash: number;
  settlement_delay_days: number;
}

export interface TriggerTrafficStep {
  step: number;
  action: 'TriggerTraffic';
  source: string;
  via: string;
  destination: string;
}

export interface RetargetingAction {
  action: 'ExecuteRetargeting';
  channel: string;
  payload: {
    offer_type: string;
    discount_percentage: number;
  };
  expected_impact?: {
    conversion_boost?: number;
  };
}

export interface DoNothingAction {
  action: 'DoNothing';
}

export interface ConditionalBranchStep {
  step: number;
  type: 'ConditionalBranch';
  condition: {
    user_action: string;
    time_elapsed?: string;
  };
  true_branch: (RetargetingAction | DoNothingAction)[];
  false_branch: (RetargetingAction | DoNothingAction)[];
}

export type LogicStep = TriggerTrafficStep | ConditionalBranchStep;

export interface StrategyAST {
  $schema: string;
  strategy_name: string;
  metadata: {
    author: string;
    industry: string;
    currency: string;
  };
  environment: {
    market_volatility: 'low' | 'moderate' | 'high';
    competitor_activity: 'passive' | 'moderate' | 'aggressive';
  };
  entities: {
    budgets: Budgets;
    audiences: Audience[];
    touchpoints: Touchpoint[];
  };
  logic_flow: LogicStep[];
  simulation_engine: {
    engine_type: string;
    parameters: {
      virtual_agents_count: number;
      timeframe_days: number;
      randomness_factor_sigma: number;
    };
    output_metrics_requested: string[];
  };
}

export interface MetricDistribution {
  mean: number;
  median: number;
  p10: number;
  p90: number;
}

export interface SimulationResult {
  strategy_name: string;
  trials_count: number;
  agents_per_trial: number;
  timeframe_days: number;
  roas: MetricDistribution;
  cac: MetricDistribution;
  spend: MetricDistribution;
  revenue: MetricDistribution;
  probability_of_profit: number;
  cash_ruin_probability: number;
  worst_case_drawdown: number;
  cannibalization_rate: number;
  var_95: number;
  cvar_95: number;
  daily_trajectories: {
    day: number;
    spend: number;
    revenue: number;
    liquid_cash: number;
  }[];
}
