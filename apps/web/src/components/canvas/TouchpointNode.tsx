import { Handle, Position } from '@xyflow/react';
import { Megaphone, ShoppingCart, Mail } from 'lucide-react';

export const TouchpointNode = ({ data }: { data: any }) => {
  const isAd = data.touchpointType === 'paid_traffic';
  const isConversion = data.touchpointType === 'conversion_surface';
  const isRetargeting = data.touchpointType === 'retargeting_channel';

  const borderColor = isAd ? 'border-sky-500/50' : isConversion ? 'border-emerald-500/50' : 'border-amber-500/50';
  const textColor = isAd ? 'text-sky-400' : isConversion ? 'text-emerald-400' : 'text-amber-400';

  return (
    <div className={`bg-slate-900 border ${borderColor} rounded-lg p-4 shadow-xl w-60 text-xs font-mono`}>
      <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-3 !h-3" />
      <div className={`flex items-center space-x-2 ${textColor} font-bold mb-2 pb-1 border-b border-slate-800`}>
        {isAd && <Megaphone className="w-4 h-4" />}
        {isConversion && <ShoppingCart className="w-4 h-4" />}
        {isRetargeting && <Mail className="w-4 h-4" />}
        <span className="truncate">{data.label}</span>
      </div>
      <div className="space-y-1 text-slate-300">
        <div className="flex justify-between">
          <span className="text-slate-500">Platform:</span>
          <span>{data.platform}</span>
        </div>
        {isAd && (
          <div className="flex justify-between">
            <span className="text-slate-500">Base CPC:</span>
            <span>${Number(data.cpc).toFixed(2)}</span>
          </div>
        )}
        {isConversion && (
          <div className="flex justify-between">
            <span className="text-slate-500">Base CR:</span>
            <span>{(Number(data.cr) * 100).toFixed(1)}%</span>
          </div>
        )}
        {isRetargeting && (
          <div className="flex justify-between">
            <span className="text-slate-500">Open Rate:</span>
            <span>{(Number(data.openRate) * 100).toFixed(1)}%</span>
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-emerald-500 !w-3 !h-3" />
    </div>
  );
};
