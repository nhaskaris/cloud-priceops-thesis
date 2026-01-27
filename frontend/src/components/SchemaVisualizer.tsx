import { useState, useCallback, useMemo, useEffect } from 'react';
import ReactFlow, {
  type Node,
  type Edge,
  Background,
  Controls,
  MiniMap,
  addEdge,
  type Connection,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  type XYPosition,
} from 'reactflow';
import 'reactflow/dist/style.css';

// --- Interfaces ---
interface TableField {
  name: string;
  type: string;
  nullable?: boolean;
  foreignKey?: string;
}

interface TableSchema {
  name: string;
  fields: TableField[];
  color?: string;
}

// --- Schema Data ---
const SCHEMA_DEFINITION: TableSchema[] = [
  {
    name: 'CloudProvider',
    color: '#FF6B6B',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'name', type: 'VARCHAR(50)', nullable: false },
      { name: 'display_name', type: 'VARCHAR(100)', nullable: false },
      { name: 'api_endpoint', type: 'URL', nullable: true },
      { name: 'is_active', type: 'BOOL', nullable: false },
      { name: 'uses_infracost', type: 'BOOL', nullable: false },
      { name: 'created_at', type: 'DATETIME', nullable: false },
      { name: 'updated_at', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'CloudService',
    color: '#4ECDC4',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'provider_id', type: 'FK', nullable: false, foreignKey: 'CloudProvider' },
      { name: 'name', type: 'VARCHAR(100)', nullable: false },
      { name: 'is_active', type: 'BOOL', nullable: false },
      { name: 'created_at', type: 'DATETIME', nullable: false },
      { name: 'updated_at', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'Region',
    color: '#45B7D1',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'provider_id', type: 'FK', nullable: false, foreignKey: 'CloudProvider' },
      { name: 'name', type: 'VARCHAR(100)', nullable: false },
      { name: 'is_active', type: 'BOOL', nullable: false },
      { name: 'created_at', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'PricingModel',
    color: '#FFA502',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'name', type: 'VARCHAR(100)', nullable: false },
    ],
  },
  {
    name: 'Currency',
    color: '#95E1D3',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'code', type: 'VARCHAR(10)', nullable: false },
      { name: 'name', type: 'VARCHAR(100)', nullable: false },
      { name: 'symbol', type: 'VARCHAR(10)', nullable: false },
      { name: 'exchange_rate_to_usd', type: 'DECIMAL', nullable: true },
      { name: 'last_updated', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'NormalizedPricingData',
    color: '#F38181',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'provider_id', type: 'FK', nullable: false, foreignKey: 'CloudProvider' },
      { name: 'service_id', type: 'FK', nullable: false, foreignKey: 'CloudService' },
      { name: 'region_id', type: 'FK', nullable: false, foreignKey: 'Region' },
      { name: 'pricing_model_id', type: 'FK', nullable: true, foreignKey: 'PricingModel' },
      { name: 'currency_id', type: 'FK', nullable: false, foreignKey: 'Currency' },
      { name: 'raw_entry', type: 'FK', nullable: true, foreignKey: 'RawPricingData' },
      { name: 'product_family', type: 'VARCHAR(100)', nullable: true },
      { name: 'instance_type', type: 'VARCHAR(100)', nullable: true },
      { name: 'vcpu_count', type: 'INT', nullable: true },
      { name: 'memory_gb', type: 'DECIMAL', nullable: true },
      { name: 'price_per_unit', type: 'DECIMAL', nullable: true },
      { name: 'effective_price_per_hour', type: 'DECIMAL', nullable: true },
      { name: 'effective_date', type: 'DATETIME', nullable: true },
      { name: 'is_active', type: 'BOOL', nullable: false },
      { name: 'created_at', type: 'DATETIME', nullable: false },
      { name: 'updated_at', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'APICallLog',
    color: '#AA96DA',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'api_endpoint', type: 'URL', nullable: true },
      { name: 'status_code', type: 'INT', nullable: true },
      { name: 'duration_seconds', type: 'DECIMAL', nullable: true },
      { name: 'records_processed', type: 'INT', nullable: false },
      { name: 'records_updated', type: 'INT', nullable: false },
      { name: 'records_inserted', type: 'INT', nullable: false },
      { name: 'records_failed', type: 'INT', nullable: false },
      { name: 'normalization_success_rate', type: 'DECIMAL', nullable: true },
      { name: 'called_at', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'MLEngine',
    color: '#FCBAD3',
    fields: [
      { name: 'id', type: 'UUID', nullable: false },
      { name: 'name', type: 'VARCHAR(255)', nullable: false },
      { name: 'model_type', type: 'VARCHAR(100)', nullable: false },
      { name: 'version', type: 'VARCHAR(50)', nullable: false },
      { name: 'model_binary', type: 'FILE', nullable: false },
      { name: 'encoder_binary', type: 'FILE', nullable: true },
      { name: 'feature_names', type: 'JSON', nullable: false },
      { name: 'r_squared', type: 'FLOAT', nullable: true },
      { name: 'mape', type: 'FLOAT', nullable: false },
      { name: 'is_active', type: 'BOOL', nullable: false },
      { name: 'created_at', type: 'DATETIME', nullable: false },
      { name: 'updated_at', type: 'DATETIME', nullable: false },
    ],
  },
  {
    name: 'ModelCoefficient',
    color: '#A8E6CF',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'engine_id', type: 'FK', nullable: false, foreignKey: 'MLEngine' },
      { name: 'feature_name', type: 'VARCHAR(255)', nullable: false },
      { name: 'value', type: 'FLOAT', nullable: false },
      { name: 'p_value', type: 'FLOAT', nullable: true },
    ],
  },
  {
    name: 'RawPricingData',
    color: '#FFD3B6',
    fields: [
      { name: 'id', type: 'INT', nullable: false },
      { name: 'provider_id', type: 'FK', nullable: false, foreignKey: 'CloudProvider' },
      { name: 'raw_json', type: 'JSON', nullable: false },
      { name: 'digest', type: 'VARCHAR(64)', nullable: true },
      { name: 'is_duplicate', type: 'BOOL', nullable: false },
      { name: 'ingested_at', type: 'DATETIME', nullable: false },
    ],
  },
]

const TABLE_POSITIONS: { [key: string]: XYPosition } = {
  CloudProvider: { x: 500, y: 0 },
  PricingModel: { x: 100, y: 50 },
  Currency: { x: 900, y: 50 },
  
  CloudService: { x: 200, y: 250 },
  Region: { x: 800, y: 250 },
  
  APICallLog: { x: 100, y: 500 },
  NormalizedPricingData: { x: 500, y: 550 },
  RawPricingData: { x: 900, y: 500 },
  
  MLEngine: { x: 300, y: 850 },
  ModelCoefficient: { x: 700, y: 850 },
};

// --- Custom Node Component ---
const TableNode = ({ data }: { data: { table: TableSchema; isSelected: boolean } }) => {
  const { table, isSelected } = data;
  return (
    <div
      className={`schema-node ${isSelected ? 'selected' : ''}`}
      style={{
        background: '#fff',
        border: `2px solid ${table.color}`,
        borderRadius: '8px',
        minWidth: '220px',
        boxShadow: isSelected ? `0 0 15px ${table.color}` : '0 4px 6px rgba(0,0,0,0.1)',
        fontFamily: 'monospace',
      }}
    >
      {/* Target on Left, Source on Right to prevent overlap loops */}
      <Handle type="target" position={Position.Left} style={{ background: '#555' }} />
      <Handle type="source" position={Position.Right} style={{ background: '#555' }} />

      <div
        style={{
          backgroundColor: table.color,
          padding: '8px 12px',
          color: '#fff',
          fontWeight: 'bold',
          borderTopLeftRadius: '6px',
          borderTopRightRadius: '6px',
          fontSize: '14px',
          textAlign: 'center',
        }}
      >
        {table.name}
      </div>
      <div style={{ padding: '8px' }}>
        {table.fields.map((field) => (
          <div
            key={field.name}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '2px 0',
              fontSize: '11px',
              borderBottom: '1px solid #eee',
            }}
          >
            <span style={{ fontWeight: field.type === 'FK' ? 'bold' : 'normal' }}>
              {field.name}
            </span>
            <span style={{ color: field.type === 'FK' ? '#2563eb' : '#666' }}>
              {field.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Define node types outside component to prevent re-renders
const nodeTypes = { tableNode: TableNode };

export default function SchemaVisualizer() {
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  // Generate Nodes
  const initialNodes: Node[] = useMemo(() => {
    return SCHEMA_DEFINITION.map((table) => ({
      id: table.name,
      type: 'tableNode', // Critical: Use the custom type
      data: { table, isSelected: table.name === selectedTable },
      position: TABLE_POSITIONS[table.name] || { x: 0, y: 0 },
    }));
  }, [selectedTable]);

  // Generate Edges
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    SCHEMA_DEFINITION.forEach((table) => {
      table.fields.forEach((field) => {
        if (field.foreignKey && field.foreignKey !== table.name) {
          const isActive = table.name === selectedTable || field.foreignKey === selectedTable;
          
          edges.push({
            id: `e-${field.foreignKey}-${table.name}-${field.name}`,
            source: field.foreignKey, // Arrows point FROM referenced table
            target: table.name,      // TO the table with the FK
            type: 'step',            // Cleaner ERD style
            label: field.name,
            animated: isActive,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: isActive ? '#2563eb' : '#94a3b8',
            },
            style: {
              stroke: isActive ? '#2563eb' : '#cbd5e1',
              strokeWidth: isActive ? 3 : 1.5,
            },
            labelStyle: { fontSize: 10, fill: '#334155', fontWeight: 600 },
          });
        }
      });
    });
    return edges;
  }, [selectedTable]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync state when selection changes
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [selectedTable, initialNodes, initialEdges, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div style={{ width: '100%', height: '800px', background: '#f8fafc' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => setSelectedTable(node.id)}
        onPaneClick={() => setSelectedTable(null)}
        fitView
      >
        <Background color="#e2e8f0" gap={20} />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}