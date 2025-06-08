import { useCallback, useState, useEffect } from 'react'
import '@xyflow/react/dist/style.css'
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  MarkerType,
  NodeProps,
  Handle,
  Position,
  NodeChange,
  applyNodeChanges,
  EdgeChange,
  applyEdgeChanges,
  Connection,
  addEdge,
} from '@xyflow/react'
import { Layout, Component as ComponentIcon } from 'lucide-react'

// Define custom node types following React Flow v12 pattern
type PageNodeData = {
  label: string;
  type: string;
  route: string;
  components: number;
};

type ServiceNodeData = {
  label: string;
  type: string;
};

// Define union type for all custom nodes
type CustomNodeTypes = Node<PageNodeData, 'page'> | Node<ServiceNodeData, 'service'>;

// Custom node components
const PageNode = ({ data }: NodeProps) => {
  const pageData = data as PageNodeData;
  return (
    <div className="relative group">
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-cyan-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(34,211,238,0.6)]"
      />
      <div className="p-4 rounded-lg bg-[#1a2c3b]/80 border border-cyan-500/30 min-w-[200px] backdrop-blur-sm transition-all duration-300 group-hover:border-cyan-500/70 group-hover:shadow-[0_5px_15px_rgba(34,211,238,0.15)]">
        <div className="flex items-center gap-2 mb-2">
          <Layout className="w-4 h-4 text-cyan-400" />
          <div className="text-sm font-bold text-cyan-400">{pageData.label}</div>
        </div>
        <div className="text-xs text-gray-400">{pageData.type}</div>
        <div className="mt-2 text-xs text-gray-500">
          <div>Route: {pageData.route}</div>
          <div>Components: {pageData.components}</div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-cyan-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(34,211,238,0.6)]"
      />
    </div>
  );
};

const ServiceNode = ({ data }: NodeProps) => {
  const serviceData = data as ServiceNodeData;
  return (
    <div className="relative group">
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-fuchsia-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(217,70,239,0.6)]"
      />
      <div className="p-4 rounded-lg bg-[#2d1a3b]/80 border border-fuchsia-500/30 min-w-[200px] backdrop-blur-sm transition-all duration-300 group-hover:border-fuchsia-500/70 group-hover:shadow-[0_5px_15px_rgba(217,70,239,0.15)]">
        <div className="flex items-center gap-2 mb-2">
          <ComponentIcon className="w-4 h-4 text-fuchsia-400" />
          <div className="text-sm font-bold text-fuchsia-400">{serviceData.label}</div>
        </div>
        <div className="text-xs text-gray-400">{serviceData.type}</div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-fuchsia-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(217,70,239,0.6)]"
      />
    </div>
  );
};

const nodeTypes = {
  page: PageNode,
  service: ServiceNode,
}

// Default/fallback nodes for when project has no features data
const defaultNodes: Node[] = [
  {
    id: 'start',
    type: 'page',
    data: {
      label: 'Start App',
      type: 'Entry Point',
      route: '/',
      components: 3,
    },
    position: {
      x: 400,
      y: 0,
    },
  },
  {
    id: 'home',
    type: 'page',
    data: {
      label: 'Homepage',
      type: 'Main View',
      route: '/home',
      components: 6,
    },
    position: {
      x: 400,
      y: 150,
    },
  },
];

// Default/fallback edges
const defaultEdges: Edge[] = [
  {
    id: 'start-home',
    source: 'start',
    target: 'home',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
];

interface FeaturesTabProps {
  project?: {
    id: string;
    title: string;
    features?: any[];
  } | null;
}

export const FeaturesTab = ({ project }: FeaturesTabProps) => {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [loading, setLoading] = useState(true)

  // Load features from project or show empty state
  useEffect(() => {
    if (project?.features && Array.isArray(project.features) && project.features.length > 0) {
      // Use project features data
      setNodes(project.features)
      // Generate edges based on the flow (simplified logic)
      const generatedEdges = generateEdgesFromNodes(project.features)
      setEdges(generatedEdges)
    } else {
      // Show empty state - no nodes or edges
      setNodes([])
      setEdges([])
    }
    setLoading(false)
  }, [project])

  // Helper function to generate edges based on node positioning and types
  const generateEdgesFromNodes = (nodes: Node[]): Edge[] => {
    const edges: Edge[] = []
    
    // Sort nodes by y position to create a logical flow
    const sortedNodes = [...nodes].sort((a, b) => a.position.y - b.position.y)
    
    for (let i = 0; i < sortedNodes.length - 1; i++) {
      const currentNode = sortedNodes[i]
      const nextNode = sortedNodes[i + 1]
      
      // Connect sequential nodes with appropriate styling
      const edgeStyle = currentNode.type === 'service' ? '#d946ef' : '#22d3ee'
      
      edges.push({
        id: `${currentNode.id}-${nextNode.id}`,
        source: currentNode.id,
        target: nextNode.id,
        animated: true,
        style: {
          stroke: edgeStyle,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeStyle,
        },
      })
    }
    
    return edges
  }

  const onNodesChange = useCallback(
    (changes: NodeChange[]) =>
      setNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  )
  
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )
  
  const onConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((node) => node.id === connection.source)
      // Set edge color based on source node type
      const edgeStyle =
        sourceNode?.type === 'service'
          ? {
              stroke: '#d946ef',
            }
          : // Fuchsia for service nodes
            {
              stroke: '#22d3ee',
            } // Cyan for page nodes
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            animated: true,
            style: edgeStyle,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: edgeStyle.stroke,
            },
          },
          eds,
        ),
      )
    },
    [nodes],
  )

  const addPageNode = () => {
    const newNode: Node = {
      id: `page-${Date.now()}`,
      type: 'page',
      data: {
        label: `New Page`,
        type: 'Page Component',
        route: '/new-page',
        components: 0,
      },
      position: {
        x: 250,
        y: 200,
      },
    }
    setNodes([...nodes, newNode])
  }

  const addServiceNode = () => {
    const newNode: Node = {
      id: `service-${Date.now()}`,
      type: 'service',
      data: {
        label: 'New Service',
        type: 'Service Component',
      },
      position: {
        x: 250,
        y: 200,
      },
    }
    setNodes([...nodes, newNode])
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading features...</div>
      </div>
    )
  }

  return (
    <div className="relative">
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(to_right,rgba(0,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(0,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]" />
      <div className="relative z-10">
        <div className="flex justify-between items-center mb-4">
          <div className="text-lg text-cyan-400 font-mono flex items-center">
            <span className="w-2 h-2 rounded-full bg-cyan-400 mr-2 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
            Feature Planner {project?.features ? `(${project.features.length} features)` : '(Default)'}
          </div>
          <div className="flex gap-2">
            <button
              onClick={addPageNode}
              className="px-3 py-1.5 rounded-lg bg-cyan-900/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-900/30 hover:border-cyan-500/50 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)] transition-all duration-300 flex items-center gap-2 relative overflow-hidden group"
            >
              <span className="absolute inset-0 bg-cyan-500/10 opacity-0 group-hover:opacity-100 transition-opacity"></span>
              <Layout className="w-4 h-4 relative z-10" />
              <span className="text-xs relative z-10">Add Page</span>
            </button>
            <button
              onClick={addServiceNode}
              className="px-3 py-1.5 rounded-lg bg-fuchsia-900/20 border border-fuchsia-500/30 text-fuchsia-400 hover:bg-fuchsia-900/30 hover:border-fuchsia-500/50 hover:shadow-[0_0_15px_rgba(217,70,239,0.3)] transition-all duration-300 flex items-center gap-2 relative overflow-hidden group"
            >
              <span className="absolute inset-0 bg-fuchsia-500/10 opacity-0 group-hover:opacity-100 transition-opacity"></span>
              <ComponentIcon className="w-4 h-4 relative z-10" />
              <span className="text-xs relative z-10">Add Service</span>
            </button>
          </div>
        </div>
        <div className="h-[70vh] relative">
          {/* Subtle neon glow at the top */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-cyan-500/30 shadow-[0_0_10px_rgba(34,211,238,0.2)] z-10"></div>
          {nodes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Layout className="w-16 h-16 mb-4 opacity-50" />
              <p className="text-lg mb-2">No features defined</p>
              <p className="text-sm">Add pages and services to get started</p>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              fitView
              attributionPosition="bottom-right"
            >
              <Controls className="!bg-white/70 dark:!bg-black/70 !border-gray-300 dark:!border-gray-800" />
            </ReactFlow>
          )}
        </div>
      </div>
    </div>
  )
}
