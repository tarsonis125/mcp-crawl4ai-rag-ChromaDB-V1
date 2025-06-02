import React, { useCallback, useState } from 'react';
import '@xyflow/react/dist/style.css';
import { ReactFlow, Node, Edge, Background, Controls, MarkerType, NodeChange, applyNodeChanges, EdgeChange, applyEdgeChanges, ConnectionLineType, addEdge, Connection, Handle, Position } from '@xyflow/react';
import { Database } from 'lucide-react';
// Custom node types
const nodeTypes = {
  table: ({
    data
  }: any) => <div className="p-3 rounded-lg bg-gradient-to-r from-cyan-900/40 to-cyan-800/30 backdrop-blur-md border border-cyan-500/50 min-w-[220px] transition-all duration-300 hover:border-cyan-500/70 hover:shadow-[0_0_15px_rgba(34,211,238,0.2)] group">
      <div className="flex items-center gap-2 mb-2">
        <Database className="w-4 h-4 text-cyan-400" />
        <div className="text-sm font-bold text-white border-b border-gray-600 pb-2">
          {data.label}
        </div>
      </div>
      <div className="text-xs text-left text-cyan-600">
        {data.columns.map((col: string, i: number) => {
        const isPK = col.includes('PK');
        const isFK = col.includes('FK');
        return <div key={i} className={`py-1 relative ${isPK ? 'text-cyan-400 font-bold' : ''} ${isFK ? 'text-fuchsia-400 italic' : ''}`}>
              {col}
              {isPK && <Handle type="source" position={Position.Right} id={`${data.label}-${col.split(' ')[0]}`} className="w-2 h-2 !bg-cyan-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(34,211,238,0.6)]" style={{
            right: -10
          }} />}
              {isFK && <Handle type="target" position={Position.Left} id={`${data.label}-${col.split(' ')[0]}`} className="w-2 h-2 !bg-fuchsia-400 transition-all duration-300 !opacity-60 group-hover:!opacity-100 group-hover:!shadow-[0_0_8px_rgba(217,70,239,0.6)]" style={{
            left: -10
          }} />}
            </div>;
      })}
      </div>
    </div>
};
const createTableNode = (id: string, label: string, columns: string[], x: number, y: number): Node => ({
  id,
  type: 'table',
  data: {
    label,
    columns
  },
  position: {
    x,
    y
  }
});
const initialNodes: Node[] = [createTableNode('users', 'Users', ['id (PK) - UUID', 'email - VARCHAR(255)', 'password - VARCHAR(255)', 'firstName - VARCHAR(100)', 'lastName - VARCHAR(100)', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 150, 100), createTableNode('products', 'Products', ['id (PK) - UUID', 'name - VARCHAR(255)', 'description - TEXT', 'price - DECIMAL(10,2)', 'inventory - INTEGER', 'categoryId (FK) - UUID', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 500, 100), createTableNode('categories', 'Categories', ['id (PK) - UUID', 'name - VARCHAR(100)', 'description - TEXT', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 850, 100), createTableNode('orders', 'Orders', ['id (PK) - UUID', 'userId (FK) - UUID', 'status - VARCHAR(50)', 'totalAmount - DECIMAL(10,2)', 'shippingAddress - TEXT', 'paymentMethod - VARCHAR(50)', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 150, 400), createTableNode('orderItems', 'Order Items', ['id (PK) - UUID', 'orderId (FK) - UUID', 'productId (FK) - UUID', 'quantity - INTEGER', 'price - DECIMAL(10,2)', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 500, 400), createTableNode('reviews', 'Reviews', ['id (PK) - UUID', 'userId (FK) - UUID', 'productId (FK) - UUID', 'rating - INTEGER', 'comment - TEXT', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 850, 400)];
const initialEdges: Edge[] = [{
  id: 'products-categories',
  source: 'products',
  target: 'categories',
  sourceHandle: 'Products-categoryId',
  targetHandle: 'Categories-id',
  animated: true,
  style: {
    stroke: '#d946ef'
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#d946ef'
  }
}, {
  id: 'orders-users',
  source: 'users',
  target: 'orders',
  sourceHandle: 'Users-id',
  targetHandle: 'Orders-userId',
  animated: true,
  style: {
    stroke: '#d946ef'
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#d946ef'
  }
}, {
  id: 'orderItems-orders',
  source: 'orders',
  target: 'orderItems',
  sourceHandle: 'Orders-id',
  targetHandle: 'Order Items-orderId',
  animated: true,
  style: {
    stroke: '#d946ef'
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#d946ef'
  }
}, {
  id: 'orderItems-products',
  source: 'products',
  target: 'orderItems',
  sourceHandle: 'Products-id',
  targetHandle: 'Order Items-productId',
  animated: true,
  style: {
    stroke: '#d946ef'
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#d946ef'
  }
}, {
  id: 'reviews-users',
  source: 'users',
  target: 'reviews',
  sourceHandle: 'Users-id',
  targetHandle: 'Reviews-userId',
  animated: true,
  style: {
    stroke: '#d946ef'
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#d946ef'
  }
}, {
  id: 'reviews-products',
  source: 'products',
  target: 'reviews',
  sourceHandle: 'Products-id',
  targetHandle: 'Reviews-productId',
  animated: true,
  style: {
    stroke: '#d946ef'
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#d946ef'
  }
}];
export const DataTab = () => {
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const onNodesChange = useCallback((changes: NodeChange[]) => setNodes(nds => applyNodeChanges(changes, nds)), []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => setEdges(eds => applyEdgeChanges(changes, eds)), []);
  const onConnect = useCallback((connection: Connection) => {
    setEdges(eds => addEdge({
      ...connection,
      animated: true,
      style: {
        stroke: '#22d3ee'
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#22d3ee'
      },
      label: 'relates to',
      labelStyle: {
        fill: '#e94560',
        fontWeight: 500
      },
      labelBgStyle: {
        fill: 'rgba(0, 0, 0, 0.7)'
      }
    }, eds));
  }, []);
  const addTableNode = () => {
    const newNodeId = `table-${Date.now()}`;
    const newNode = createTableNode(newNodeId, `New Table ${nodes.length + 1}`, ['id (PK) - UUID', 'name - VARCHAR(255)', 'description - TEXT', 'createdAt - TIMESTAMP', 'updatedAt - TIMESTAMP'], 400, 300);
    setNodes([...nodes, newNode]);
  };
  return <div className="relative">
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(to_right,rgba(0,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(0,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]"></div>
      <div className="relative z-10">
        <div className="flex justify-between items-center mb-4">
          <div className="text-lg text-cyan-400 font-mono flex items-center">
            <span className="w-2 h-2 rounded-full bg-cyan-400 mr-2 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
            Data Relationships
          </div>
        </div>
        <div className="mb-4">
          <button onClick={addTableNode} className="p-2 rounded-lg bg-cyan-900/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-900/30 hover:border-cyan-500/50 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)] transition-all duration-300 flex items-center justify-center gap-2 w-full md:w-auto relative overflow-hidden group">
            <span className="absolute inset-0 bg-cyan-500/10 opacity-0 group-hover:opacity-100 transition-opacity"></span>
            <Database className="w-4 h-4 relative z-10" />
            <span className="text-xs relative z-10">Add Table</span>
          </button>
        </div>
        <div className="h-[70vh] relative">
          {/* Subtle neon glow at the top */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-cyan-500/30 shadow-[0_0_10px_rgba(34,211,238,0.2)] z-10"></div>
          <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} nodeTypes={nodeTypes} connectionLineType={ConnectionLineType.Step} defaultEdgeOptions={{
          type: 'step',
          style: {
            stroke: '#d946ef'
          },
          animated: true,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#d946ef'
          }
        }} fitView>
            <Controls className="!bg-white/70 dark:!bg-black/70 !border-gray-300 dark:!border-gray-800" />
          </ReactFlow>
        </div>
      </div>
    </div>;
};