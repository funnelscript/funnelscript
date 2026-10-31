import { type Node, type Edge, MarkerType } from '@xyflow/react';
import type { StrategyAST, TriggerTrafficStep, ConditionalBranchStep } from '../types';

export function funnelScriptToGraph(ast: StrategyAST): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const yOffset = 100;

  // 1. Audience Nodes
  ast.entities.audiences.forEach((aud, i) => {
    nodes.push({
      id: aud.id,
      type: 'audienceNode',
      position: { x: 100, y: yOffset + i * 160 },
      data: {
        label: aud.name,
        type: aud.type,
        size: aud.estimated_size,
        affinity: aud.attributes.brand_affinity,
        price_sens: aud.attributes.price_sensitivity,
        fomo: aud.attributes.fomo_index,
      },
    });
  });

  // 2. Touchpoint Nodes
  const tpXMap: Record<string, number> = {
    paid_traffic: 450,
    conversion_surface: 800,
    retargeting_channel: 800,
  };

  const tpYCounts: Record<string, number> = {
    paid_traffic: 0,
    conversion_surface: 0,
    retargeting_channel: 0,
  };

  ast.entities.touchpoints.forEach((tp) => {
    const colX = tpXMap[tp.type] || 600;
    const yIdx = tpYCounts[tp.type] || 0;
    const yPos = 80 + yIdx * 180 + (tp.type === 'retargeting_channel' ? 220 : 0);
    tpYCounts[tp.type] = yIdx + 1;

    nodes.push({
      id: tp.id,
      type: 'touchpointNode',
      position: { x: colX, y: yPos },
      data: {
        id: tp.id,
        label: tp.id.replace('tp_', '').toUpperCase(),
        touchpointType: tp.type,
        platform: tp.platform || tp.medium || 'Direct',
        cpc: tp.base_cpc,
        cr: tp.base_conversion_rate,
        openRate: tp.base_open_rate,
      },
    });
  });

  // 3. Logic Flow -> Edges & Decision Branches
  let edgeCounter = 0;
  ast.logic_flow.forEach((step) => {
    if ('action' in step && step.action === 'TriggerTraffic') {
      const traffic = step as TriggerTrafficStep;
      // Edge from Audience to Ad Touchpoint
      edges.push({
        id: `e-${edgeCounter++}`,
        source: traffic.source,
        target: traffic.via,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#3b82f6', strokeWidth: 2 },
      });
      // Edge from Ad Touchpoint to Conversion Landing Page
      edges.push({
        id: `e-${edgeCounter++}`,
        source: traffic.via,
        target: traffic.destination,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#10b981', strokeWidth: 2 },
      });
    } else if ('type' in step && step.type === 'ConditionalBranch') {
      const branch = step as ConditionalBranchStep;
      const branchId = `node_cond_${step.step}`;
      // Add a Conditional Decision Node
      nodes.push({
        id: branchId,
        type: 'conditionalNode',
        position: { x: 500, y: 350 },
        data: {
          action: branch.condition.user_action,
          time: branch.condition.time_elapsed || 'Immediate',
        },
      });

      branch.true_branch.forEach((tb) => {
        if (tb.action === 'ExecuteRetargeting') {
          edges.push({
            id: `e-${edgeCounter++}`,
            source: branchId,
            target: tb.channel,
            label: `${tb.payload.discount_percentage}% Off`,
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: '#f59e0b', strokeWidth: 2 },
          });
        }
      });
    }
  });

  return { nodes, edges };
}

export function graphToFunnelScript(
  nodes: Node[],
  _edges: Edge[],
  baseAst: StrategyAST
): StrategyAST {
  const updated = structuredClone(baseAst);

  // Synchronize audiences
  const audienceNodes = nodes.filter((n) => n.type === 'audienceNode');
  if (audienceNodes.length > 0) {
    updated.entities.audiences = audienceNodes.map((n) => ({
      id: n.id,
      name: String(n.data.label || n.id),
      type: (n.data.type as any) || 'cold',
      estimated_size: Number(n.data.size) || 100000,
      attributes: {
        brand_affinity: Number(n.data.affinity ?? 0.5),
        price_sensitivity: Number(n.data.price_sens ?? 0.5),
        fomo_index: Number(n.data.fomo ?? 0.5),
      },
    }));
  }

  // Synchronize touchpoints
  const tpNodes = nodes.filter((n) => n.type === 'touchpointNode');
  if (tpNodes.length > 0) {
    updated.entities.touchpoints = tpNodes.map((n) => ({
      id: n.id,
      type: (n.data.touchpointType as any) || 'paid_traffic',
      platform: String(n.data.platform || 'Meta'),
      base_cpc: n.data.cpc !== undefined ? Number(n.data.cpc) : undefined,
      base_conversion_rate: n.data.cr !== undefined ? Number(n.data.cr) : undefined,
      base_open_rate: n.data.openRate !== undefined ? Number(n.data.openRate) : undefined,
    }));
  }

  return updated;
}
