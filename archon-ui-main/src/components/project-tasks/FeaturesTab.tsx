import React, { useCallback, useState, Component } from 'react'
import '@xyflow/react/dist/style.css'
import {
  ReactFlow,
  Node,
  Edge,
  Background,
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
import { Layout, Component } from 'lucide-react'
// Custom node components
const PageNode = ({ data }: NodeProps) => (
  <div className="relative group">
    <Handle
      type="target"
      position={Position.Top}
      className="w-3 h-3 !bg-cyan-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(34,211,238,0.6)]"
    />
    <div className="p-4 rounded-lg bg-[#1a2c3b]/80 border border-cyan-500/30 min-w-[200px] backdrop-blur-sm transition-all duration-300 group-hover:border-cyan-500/70 group-hover:shadow-[0_5px_15px_rgba(34,211,238,0.15)]">
      <div className="flex items-center gap-2 mb-2">
        <Layout className="w-4 h-4 text-cyan-400" />
        <div className="text-sm font-bold text-cyan-400">{data.label}</div>
      </div>
      <div className="text-xs text-gray-400">{data.type}</div>
      <div className="mt-2 text-xs text-gray-500">
        <div>Route: {data.route}</div>
        <div>Components: {data.components}</div>
      </div>
    </div>
    <Handle
      type="source"
      position={Position.Bottom}
      className="w-3 h-3 !bg-cyan-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(34,211,238,0.6)]"
    />
  </div>
)
const ServiceNode = ({ data }: NodeProps) => (
  <div className="relative group">
    <Handle
      type="target"
      position={Position.Top}
      className="w-3 h-3 !bg-fuchsia-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(217,70,239,0.6)]"
    />
    <div className="p-4 rounded-lg bg-[#2d1a3b]/80 border border-fuchsia-500/30 min-w-[200px] backdrop-blur-sm transition-all duration-300 group-hover:border-fuchsia-500/70 group-hover:shadow-[0_5px_15px_rgba(217,70,239,0.15)]">
      <div className="flex items-center gap-2 mb-2">
        <Component className="w-4 h-4 text-fuchsia-400" />
        <div className="text-sm font-bold text-fuchsia-400">{data.label}</div>
      </div>
      <div className="text-xs text-gray-400">{data.type}</div>
    </div>
    <Handle
      type="source"
      position={Position.Bottom}
      className="w-3 h-3 !bg-fuchsia-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(217,70,239,0.6)]"
    />
  </div>
)
const nodeTypes = {
  page: PageNode,
  service: ServiceNode,
}
const initialNodes: Node[] = [
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
    id: 'splash',
    type: 'page',
    data: {
      label: 'Splashscreen',
      type: 'Loading Screen',
      route: '/splash',
      components: 2,
    },
    position: {
      x: 400,
      y: 150,
    },
  },
  {
    id: 'login',
    type: 'page',
    data: {
      label: 'Login Page',
      type: 'Authentication',
      route: '/login',
      components: 4,
    },
    position: {
      x: 400,
      y: 300,
    },
  },
  {
    id: 'auth',
    type: 'service',
    data: {
      label: 'Authentication',
      type: 'Service Component',
    },
    position: {
      x: 800,
      y: 300,
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
      y: 450,
    },
  },
  {
    id: 'products',
    type: 'page',
    data: {
      label: 'Product Catalog',
      type: 'Listing Page',
      route: '/products',
      components: 5,
    },
    position: {
      x: 100,
      y: 600,
    },
  },
  {
    id: 'cart',
    type: 'page',
    data: {
      label: 'Shopping Cart',
      type: 'Cart View',
      route: '/cart',
      components: 4,
    },
    position: {
      x: 400,
      y: 600,
    },
  },
  {
    id: 'checkout',
    type: 'page',
    data: {
      label: 'Checkout Page',
      type: 'Payment Flow',
      route: '/checkout',
      components: 5,
    },
    position: {
      x: 700,
      y: 600,
    },
  },
  {
    id: 'payment',
    type: 'service',
    data: {
      label: 'Payment Processing',
      type: 'Service Component',
    },
    position: {
      x: 700,
      y: 750,
    },
  },
  {
    id: 'confirmation',
    type: 'page',
    data: {
      label: 'Order Confirmation',
      type: 'Success Page',
      route: '/confirmation',
      components: 3,
    },
    position: {
      x: 700,
      y: 900,
    },
  },
  {
    id: 'profile',
    type: 'page',
    data: {
      label: 'User Profile',
      type: 'Account Page',
      route: '/profile',
      components: 4,
    },
    position: {
      x: 1000,
      y: 450,
    },
  },
  {
    id: 'orders',
    type: 'page',
    data: {
      label: 'Order History',
      type: 'Account Sub-page',
      route: '/orders',
      components: 3,
    },
    position: {
      x: 1000,
      y: 600,
    },
  },
]
const initialEdges: Edge[] = [
  {
    id: 'start-splash',
    source: 'start',
    target: 'splash',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'splash-login',
    source: 'splash',
    target: 'login',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'login-auth',
    source: 'login',
    target: 'auth',
    animated: true,
    style: {
      stroke: '#d946ef',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#d946ef',
    },
  },
  {
    id: 'login-home',
    source: 'login',
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
  {
    id: 'home-products',
    source: 'home',
    target: 'products',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'home-cart',
    source: 'home',
    target: 'cart',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'home-profile',
    source: 'home',
    target: 'profile',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'cart-checkout',
    source: 'cart',
    target: 'checkout',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'checkout-payment',
    source: 'checkout',
    target: 'payment',
    animated: true,
    style: {
      stroke: '#d946ef',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#d946ef',
    },
  },
  {
    id: 'payment-confirmation',
    source: 'payment',
    target: 'confirmation',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
  {
    id: 'profile-orders',
    source: 'profile',
    target: 'orders',
    animated: true,
    style: {
      stroke: '#22d3ee',
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#22d3ee',
    },
  },
]
export const FeaturesTab = () => {
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)
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
  return (
    <div className="relative">
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(to_right,rgba(0,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(0,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]" />
      <div className="relative z-10">
        <div className="flex justify-between items-center mb-4">
          <div className="text-lg text-cyan-400 font-mono flex items-center">
            <span className="w-2 h-2 rounded-full bg-cyan-400 mr-2 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
            Feature Planner
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
              <Component className="w-4 h-4 relative z-10" />
              <span className="text-xs relative z-10">Add Service</span>
            </button>
          </div>
        </div>
        <div className="h-[70vh] relative">
          {/* Subtle neon glow at the top */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-cyan-500/30 shadow-[0_0_10px_rgba(34,211,238,0.2)] z-10"></div>
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
        </div>
      </div>
    </div>
  )
}
