import { Handle, Position } from '@xyflow/react';
import { Users } from 'lucide-react';

export const AudienceNode = ({ data }: { data: any }) => {
  return (
    <div className="bg-slate-900 border border-blue-500/50 rounded-lg p-4 shadow-xl w-64 text-xs font-mono">
      <div className="flex items-center space-x-2 text-blue-400 font-bold mb-2 pb-1 border-b border-slate-800">
        <Users className="w-4 h-4" />
        <span className="truncate">{data.label}</span>
      </div>
      <div className="space-y-1 text-slate-300">
        <div className="flex justify-between">
          <span className="text-slate-500">Cohort Type:</span>
          <span className="uppercase text-blue-300 font-semibold">{data.type}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Est. TAM:</span>
          <span>{Number(data.size).toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Affinity (α):</span>
          <span>{(data.affinity * 100).toFixed(0)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Price Sens (β):</span>
          <span>{(data.price_sens * 100).toFixed(0)}%</span>
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-blue-500 !w-3 !h-3" />
    </div>
  );
};
