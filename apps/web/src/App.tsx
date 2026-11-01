import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
} from '@xyflow/react';

import type { StrategyAST, SimulationResult } from './types';
import { funnelScriptToGraph } from './lib/transpiler';
import { runInBrowserSimulation } from './lib/simulator';
import { AudienceNode } from './components/canvas/AudienceNode';
import { TouchpointNode } from './components/canvas/TouchpointNode';
import { ConditionalNode } from './components/canvas/ConditionalNode';
import { DistributionCards } from './components/telemetry/DistributionCards';
import { CashRunwayChart } from './components/telemetry/CashRunwayChart';
import { CodeDrawer } from './components/CodeDrawer';
import { Play, Sliders, Code, ShieldAlert } from 'lucide-react';

const INITIAL_STRATEGY: StrategyAST = {
  $schema: 'https://marketing-lang.org',
  strategy_name: 'ECommerce_Black_Friday_2026',
  metadata: {
    author: 'Marketing Systems Engineer',
    industry: 'Consumer Electronics',
    currency: 'USD',
  },
  environment: {
    market_volatility: 'high',
    competitor_activity: 'aggressive',
  },
  entities: {
    budgets: {
      total_budget: 25000,
      max_cpc_limit: 1.2,
      initial_cash: 12000,
      settlement_delay_days: 3,
    },
    audiences: [
      {
        id: 'aud_01',
        name: 'Tech Enthusiasts',
        type: 'cold',
        estimated_size: 500000,
        attributes: {
          brand_affinity: 0.65,
          price_sensitivity: 0.4,
          fomo_index: 0.75,
        },
      },
    ],
    touchpoints: [
      {
        id: 'tp_meta_ads',
        type: 'paid_traffic',
        platform: 'Meta',
        base_cpc: 0.45,
        ad_creative_score: 0.85,
      },
      {
        id: 'tp_landing_page',
        type: 'conversion_surface',
        base_conversion_rate: 0.045,
      },
      {
        id: 'tp_cart_email',
        type: 'retargeting_channel',
        medium: 'Email',
        base_open_rate: 0.28,
      },
    ],
  },
  logic_flow: [
    {
      step: 1,
      action: 'TriggerTraffic',
      source: 'aud_01',
      via: 'tp_meta_ads',
      destination: 'tp_landing_page',
    },
    {
      step: 2,
      type: 'ConditionalBranch',
      condition: {
        user_action: 'AbandonCart',
        time_elapsed: '2h',
      },
      true_branch: [
        {
          action: 'ExecuteRetargeting',
          channel: 'tp_cart_email',
          payload: {
            offer_type: 'Scarcity_With_Discount',
            discount_percentage: 15,
          },
          expected_impact: {
            conversion_boost: 0.021,
          },
        },
      ],
      false_branch: [
        {
          action: 'DoNothing',
        },
      ],
    },
  ],
  simulation_engine: {
    engine_type: 'Agent-Based_Monte_Carlo',
    parameters: {
      virtual_agents_count: 50000,
      timeframe_days: 14,
      randomness_factor_sigma: 0.15,
    },
    output_metrics_requested: ['ROAS_Distribution', 'CAC_Distribution', 'Working_Capital_Ruin_Probability'],
  },
};

export default function App() {
  const [ast, setAst] = useState<StrategyAST>(INITIAL_STRATEGY);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [showCode, setShowCode] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  const nodeTypes = useMemo(
    () => ({
      audienceNode: AudienceNode,
      touchpointNode: TouchpointNode,
      conditionalNode: ConditionalNode,
    }),
    []
  );

  const runSimulation = useCallback((currentAst: StrategyAST) => {
    setIsSimulating(true);
    setTimeout(() => {
      const res = runInBrowserSimulation(currentAst, 100, currentAst.simulation_engine.parameters.virtual_agents_count);
      setSimulationResult(res);
      setIsSimulating(false);
    }, 50);
  }, []);

  // Initialize graph and run simulation
  useEffect(() => {
    const { nodes: initNodes, edges: initEdges } = funnelScriptToGraph(ast);
    setNodes(initNodes);
    setEdges(initEdges);
    runSimulation(ast);
  }, [runSimulation]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds));
    },
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds));
    },
    []
  );

  const handleUpdateAst = (newAst: StrategyAST) => {
    setAst(newAst);
    const { nodes: newNodes, edges: newEdges } = funnelScriptToGraph(newAst);
    setNodes(newNodes);
    setEdges(newEdges);
    runSimulation(newAst);
  };

  const handleBudgetChange = (field: keyof StrategyAST['entities']['budgets'], value: number) => {
    const updated = {
      ...ast,
      entities: {
        ...ast.entities,
        budgets: {
          ...ast.entities.budgets,
          [field]: value,
        },
      },
    };
    setAst(updated);
    runSimulation(updated);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#121525] text-slate-100 overflow-hidden font-sans">
      {/* Top Navbar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/80 backdrop-blur px-4 flex items-center justify-between z-30">
        <div className="flex items-center space-x-3">
          <img src="/funnelscript-icon.svg" alt="FunnelScript" className="w-8 h-8 shrink-0" />
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm tracking-wide text-white">FunnelScript</span>
              <span className="text-[10px] bg-[#211C45] text-[#C8BEFF] px-1.5 py-0.5 rounded border border-[#463C88]">
                Experimental Studio
              </span>
            </div>
            <span className="text-[11px] text-slate-400">
              {ast.strategy_name} · {ast.entities.audiences.length} Audiences · {ast.entities.touchpoints.length} Touchpoints
            </span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowControls(!showControls)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-xs font-medium transition border ${
              showControls ? 'bg-slate-800 border-brand text-[#B5A9FF]' : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Sensitivity Controls</span>
          </button>

          <button
            onClick={() => setShowCode(!showCode)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-xs font-medium transition border ${
              showCode ? 'bg-slate-800 border-brand text-[#B5A9FF]' : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            <span>JSON AST</span>
          </button>

          <button
            onClick={() => runSimulation(ast)}
            disabled={isSimulating}
            className="flex items-center space-x-1.5 px-4 py-1.5 rounded bg-brandStrong hover:bg-[#6248E6] text-white font-semibold text-xs transition shadow-lg shadow-[#725CFF]/20 disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${isSimulating ? 'animate-spin' : ''}`} />
            <span>{isSimulating ? 'Simulating...' : 'Run Simulation'}</span>
          </button>
        </div>
      </header>

      {/* Sensitivity Controls Bar (collapsible) */}
      {showControls && (
        <div className="bg-slate-900 border-b border-slate-800 px-6 py-2 flex items-center space-x-8 text-xs font-mono z-20">
          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Max CPC:</span>
            <input
              type="range"
              min="0.2"
              max="3.0"
              step="0.05"
              value={ast.entities.budgets.max_cpc_limit}
              onChange={(e) => handleBudgetChange('max_cpc_limit', parseFloat(e.target.value))}
              className="w-24 accent-brand cursor-pointer"
            />
            <span className="text-[#B5A9FF] font-bold">${ast.entities.budgets.max_cpc_limit.toFixed(2)}</span>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Initial Cash:</span>
            <input
              type="range"
              min="500"
              max="30000"
              step="500"
              value={ast.entities.budgets.initial_cash}
              onChange={(e) => handleBudgetChange('initial_cash', parseFloat(e.target.value))}
              className="w-28 accent-brand cursor-pointer"
            />
            <span className="text-emerald-400 font-bold">${ast.entities.budgets.initial_cash.toLocaleString()}</span>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Settlement Delay (Δ_settle):</span>
            <input
              type="range"
              min="0"
              max="10"
              step="1"
              value={ast.entities.budgets.settlement_delay_days}
              onChange={(e) => handleBudgetChange('settlement_delay_days', parseInt(e.target.value, 10))}
              className="w-20 accent-brand cursor-pointer"
            />
            <span className={`font-bold ${ast.entities.budgets.settlement_delay_days > 4 ? 'text-red-400' : 'text-slate-200'}`}>
              {ast.entities.budgets.settlement_delay_days} days
            </span>
          </div>

          <div className="text-[11px] text-slate-500 flex items-center space-x-1 ml-auto">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span>Interactive Stress-Test Mode (H_5.2: &lt;350ms)</span>
          </div>
        </div>
      )}

      {/* Main Workspace: Canvas + Drawer */}
      <div className="flex-1 flex relative overflow-hidden">
        {/* Canvas Area */}
        <div className="flex-1 h-full relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} size={1} color="#1e293b" />
            <Controls className="!bg-slate-900 !border-slate-800 !text-slate-200" />
          </ReactFlow>

          {/* Floating Live Telemetry Cards Overlay */}
          <div className="absolute bottom-4 left-4 right-4 z-10 pointer-events-none">
            <div className="max-w-6xl mx-auto space-y-2 pointer-events-auto">
              <DistributionCards result={simulationResult} />
              <CashRunwayChart result={simulationResult} />
            </div>
          </div>
        </div>

        {/* Code Drawer (collapsible) */}
        {showCode && (
          <div className="w-[450px] h-full shadow-2xl z-20">
            <CodeDrawer ast={ast} onUpdateAst={handleUpdateAst} />
          </div>
        )}
      </div>
    </div>
  );
}
