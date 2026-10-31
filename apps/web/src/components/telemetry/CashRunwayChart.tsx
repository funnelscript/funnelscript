import React from 'react';
import type { SimulationResult } from '../../types';

export const CashRunwayChart: React.FC<{ result: SimulationResult | null }> = ({ result }) => {
  if (!result || !result.daily_trajectories || result.daily_trajectories.length === 0) return null;

  const maxCash = Math.max(...result.daily_trajectories.map((d) => d.liquid_cash), 1000);
  const minCash = Math.min(...result.daily_trajectories.map((d) => d.liquid_cash), 0);
  const range = maxCash - Math.min(0, minCash) || 1;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 text-xs font-mono">
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-slate-300">Daily Cash Runway & Settlement Influx</span>
        <span className="text-[10px] text-slate-500">Working Capital C(t) vs Payout Delay Δ_settle</span>
      </div>

      <div className="h-28 flex items-end space-x-1 pt-4 pb-2 border-b border-slate-800">
        {result.daily_trajectories.map((d) => {
          const heightPct = Math.max(8, Math.min(100, ((d.liquid_cash - Math.min(0, minCash)) / range) * 100));
          const isDanger = d.liquid_cash < 100;

          return (
            <div key={d.day} className="flex-1 flex flex-col items-center group relative">
              {/* Tooltip */}
              <div className="absolute -top-8 bg-slate-950 border border-slate-700 px-1.5 py-0.5 rounded text-[9px] hidden group-hover:block whitespace-nowrap z-20">
                Day {d.day}: ${d.liquid_cash.toLocaleString()}
              </div>
              <div
                style={{ height: `${heightPct}%` }}
                className={`w-full rounded-t transition-all duration-300 ${
                  isDanger ? 'bg-red-500/80 hover:bg-red-400' : 'bg-blue-600/70 hover:bg-blue-500'
                }`}
              />
              <span className="text-[9px] text-slate-500 mt-1">D{d.day}</span>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between items-center text-[10px] text-slate-500 pt-2 font-mono">
        <div>VaR-95: <span className="text-amber-400">${result.var_95.toLocaleString()}</span></div>
        <div>CVaR-95: <span className="text-red-400">${result.cvar_95.toLocaleString()}</span></div>
        <div>Max Drawdown: <span className="text-red-400">${result.worst_case_drawdown.toLocaleString()}</span></div>
      </div>
    </div>
  );
};
