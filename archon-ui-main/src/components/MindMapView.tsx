import React, { useCallback } from 'react';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, Panel, NodeProps, Handle, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { KnowledgeItem } from '../types/knowledge';
import { LinkIcon, Upload, Brain, BoxIcon } from 'lucide-react';
interface MindMapProps {
  items: KnowledgeItem[];
}
const CustomNode = ({
  data
}: NodeProps) => {
  // Get the type icon
  const TypeIcon = data.knowledgeType === 'technical' ? BoxIcon : Brain;
  const typeIconColor = data.knowledgeType === 'technical' ? 'text-cyan-400' : 'text-fuchsia-400';
  return <div className="group relative bg-black/70 border border-gray-800 rounded-lg p-4 hover:border-cyan-400/30 transition-all duration-300 min-w-[200px]">
      <Handle type="target" position={Position.Top} className="!bg-cyan-400" />
      <Handle type="source" position={Position.Bottom} className="!bg-fuchsia-400" />
      <div className="flex items-center gap-2 mb-2">
        {/* Source type icon */}
        {data.sourceType === 'url' ? <LinkIcon className="w-4 h-4 text-cyan-400" /> : <Upload className="w-4 h-4 text-fuchsia-400" />}
        {/* Knowledge type icon */}
        <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
        <h3 className="text-white font-medium">{data.title}</h3>
      </div>
      <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <p className="text-gray-400 text-sm mb-2">{data.description}</p>
        <div className="flex flex-wrap gap-2">
          {data.tags.map(tag => <span key={tag} className="px-2 py-1 bg-fuchsia-500/10 border border-fuchsia-500/20 rounded-md text-fuchsia-400 text-xs">
              {tag}
            </span>)}
        </div>
      </div>
    </div>;
};
export const MindMapView = ({
  items
}: MindMapProps) => {
  // Convert items to nodes
  const initialNodes = items.map((item, index) => ({
    id: item.id,
    type: 'custom',
    position: {
      x: index * 300,
      y: index % 2 === 0 ? 0 : 100
    },
    data: item
  }));
  // Create edges between nodes based on shared tags
  const initialEdges = items.flatMap((item, i) => items.slice(i + 1).map(otherItem => {
    const sharedTags = item.tags.filter(tag => otherItem.tags.includes(tag));
    if (sharedTags.length > 0) {
      return {
        id: `${item.id}-${otherItem.id}`,
        source: item.id,
        target: otherItem.id,
        style: {
          stroke: 'url(#edge-gradient)',
          strokeWidth: 2
        }
      };
    }
    return null;
  }).filter(Boolean));
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const nodeTypes = {
    custom: CustomNode
  };
  return <div className="w-full h-[calc(100vh-12rem)]">
      <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} nodeTypes={nodeTypes} fitView className="bg-black/20">
        <Background className="!bg-black/5" />
        <Controls className="!bg-black/50 !border-gray-800" />
        <MiniMap className="!bg-black/50 !border-gray-800" nodeColor="#0891b2" maskColor="rgba(0, 0, 0, 0.8)" />
        <Panel position="bottom-center">
          <svg width="0" height="0">
            <defs>
              <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgb(6, 182, 212)" />
                <stop offset="100%" stopColor="rgb(219, 39, 119)" />
              </linearGradient>
            </defs>
          </svg>
        </Panel>
      </ReactFlow>
    </div>;
};