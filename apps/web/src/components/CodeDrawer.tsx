import React, { useState } from 'react';
import type { StrategyAST } from '../types';
import { Code2, Copy, Check, RefreshCw } from 'lucide-react';

export const CodeDrawer: React.FC<{
  ast: StrategyAST;
  onUpdateAst: (newAst: StrategyAST) => void;
}> = ({ ast, onUpdateAst }) => {
  const [copied, setCopied] = useState(false);
  const [rawText, setRawText] = useState(JSON.stringify(ast, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  // Sync when prop updates
  React.useEffect(() => {
    setRawText(JSON.stringify(ast, null, 2));
    setParseError(null);
  }, [ast]);

  const handleCopy = () => {
    navigator.clipboard.writeText(rawText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleApply = () => {
    try {
      const parsed = JSON.parse(rawText);
      onUpdateAst(parsed);
      setParseError(null);
    } catch (e: any) {
      setParseError(e.message);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 border-l border-slate-800 text-xs font-mono">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-800 bg-slate-900/60">
        <div className="flex items-center space-x-2 text-slate-300 font-semibold">
          <Code2 className="w-4 h-4 text-blue-400" />
          <span>FunnelScript JSON AST</span>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={handleCopy}
            className="flex items-center space-x-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <button
            onClick={handleApply}
            className="flex items-center space-x-1 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Apply</span>
          </button>
        </div>
      </div>

      {parseError && (
        <div className="p-2 bg-red-950/80 border-b border-red-800 text-red-300 text-[11px]">
          Syntax Error: {parseError}
        </div>
      )}

      {/* Editor Body */}
      <textarea
        value={rawText}
        onChange={(e) => setRawText(e.target.value)}
        className="flex-1 w-full p-4 bg-slate-950 text-slate-200 outline-none resize-none font-mono text-[11px] leading-relaxed selection:bg-blue-800"
        spellCheck={false}
      />
    </div>
  );
};
