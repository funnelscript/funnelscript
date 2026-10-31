import { Handle, Position } from '@xyflow/react';
import { GitFork } from 'lucide-react';

export const ConditionalNode = ({ data }: { data: any }) => {
  return (
    <div className="bg-slate-900 border border-purple-500/50 rounded-lg p-3 shadow-xl w-52 text-xs font-mono">
      <Handle type="target" position={Position.Left} className="!bg-purple-500 !w-3 !h-3" />
      <div className="flex items-center space-x-2 text-purple-400 font-bold mb-1 pb-1 border-b border-slate-800">
        <GitFork className="w-4 h-4" />
        <span className="truncate">{data.action}</span>
      </div>
      <div className="flex justify-between text-slate-400">
        <span>Delay Window:</span>
        <span className="text-purple-300 font-semibold">{data.time}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-purple-500 !w-3 !h-3" />
    </div>
  );
};
