import React from 'react';
import type { SimulationResult } from '../../types';
import { TrendingUp, DollarSign, AlertTriangle, ShieldCheck } from 'lucide-react';

export const DistributionCards: React.FC<{ result: SimulationResult | null }> = ({ result }) => {
  if (!result) return null;

  const isRuinHigh = result.cash_ruin_probability > 0.05;
  const isCannibalHigh = result.cannibalization_rate > 0.10;

  return (
    <div className="grid grid-cols-4 gap-3">
      {/* ROAS Distribution */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3">
        <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>ROAS Distribution</span>
          <TrendingUp className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-xl font-bold text-emerald-400 font-mono">{result.roas.median}x</div>
        <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-2 pt-1 border-t border-slate-800">
          <span>P10: {result.roas.p10}x</span>
          <span>Mean: {result.roas.mean}x</span>
          <span>P90: {result.roas.p90}x</span>
        </div>
      </div>

      {/* CAC Distribution */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3">
        <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>CAC Distribution</span>
          <DollarSign className="w-4 h-4 text-sky-400" />
        </div>
        <div className="text-xl font-bold text-sky-400 font-mono">${result.cac.median}</div>
        <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-2 pt-1 border-t border-slate-800">
          <span>P10: ${result.cac.p10}</span>
          <span>Mean: ${result.cac.mean}</span>
          <span>P90: ${result.cac.p90}</span>
        </div>
      </div>

      {/* Cash Ruin Probability */}
      <div className={`bg-slate-900/90 border ${isRuinHigh ? 'border-red-500/50' : 'border-slate-800'} rounded-lg p-3`}>
        <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>P(Insolvency) Ruin</span>
          {isRuinHigh ? <AlertTriangle className="w-4 h-4 text-red-500" /> : <ShieldCheck className="w-4 h-4 text-emerald-500" />}
        </div>
        <div className={`text-xl font-bold font-mono ${isRuinHigh ? 'text-red-400' : 'text-emerald-400'}`}>
          {(result.cash_ruin_probability * 100).toFixed(1)}%
        </div>
        <div className="text-[10px] text-slate-500 mt-2 pt-1 border-t border-slate-800 truncate">
          Settlement lag starvation risk
        </div>
      </div>

      {/* Cannibalization & VaR */}
      <div className={`bg-slate-900/90 border ${isCannibalHigh ? 'border-amber-500/50' : 'border-slate-800'} rounded-lg p-3`}>
        <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>Discount Cannibalization</span>
          <AlertTriangle className={`w-4 h-4 ${isCannibalHigh ? 'text-amber-400' : 'text-slate-600'}`} />
        </div>
        <div className={`text-xl font-bold font-mono ${isCannibalHigh ? 'text-amber-400' : 'text-slate-300'}`}>
          {(result.cannibalization_rate * 100).toFixed(1)}%
        </div>
        <div className="text-[10px] text-slate-500 mt-2 pt-1 border-t border-slate-800 truncate">
          Loyal buyers (α &gt; 0.75) with coupons
        </div>
      </div>
    </div>
  );
};
