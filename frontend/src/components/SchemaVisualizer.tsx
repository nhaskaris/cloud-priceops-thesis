import React, { useState, useCallback, useMemo } from 'react'
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
  type XYPosition,
} from 'reactflow'
import 'reactflow/dist/style.css'
import '../styles/SchemaVisualizer.css'

interface TableField {
  name: string
  type: string
  nullable?: boolean
  foreignKey?: string
}

interface TableSchema {
  name: string
  fields: TableField[]
  color?: string
}

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
  CloudProvider: { x: 0, y: 0 },
  CloudService: { x: -500, y: 300 },
  Region: { x: 500, y: 300 },
  PricingModel: { x: -500, y: 600 },
  Currency: { x: 500, y: 600 },
  NormalizedPricingData: { x: 0, y: 900 },
  RawPricingData: { x: 0, y: 1200 },
  APICallLog: { x: -700, y: 900 },
  MLEngine: { x: 700, y: 900 },
  ModelCoefficient: { x: 700, y: 1200 },
}

const TableNode: React.FC<{ data: { table: TableSchema; isSelected: boolean } }> = ({
  data: { table, isSelected },
}) => {
  return (
    <div
      className={`schema-node ${isSelected ? 'selected' : ''}`}
      style={{
        borderColor: table.color,
        boxShadow: isSelected ? `0 0 10px ${table.color}` : 'none',
      }}
    >
      <div className="node-header" style={{ backgroundColor: table.color }}>
        <h3>{table.name}</h3>
      </div>
      <div className="node-content">
        {table.fields.map((field) => (
          <div key={field.name} className="field">
            <span className="field-name">{field.name}</span>
            <span className={`field-type ${field.type === 'FK' ? 'foreign-key' : ''}`}>
              {field.type}
              {field.nullable ? '?' : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SchemaVisualizer() {
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [showMiniMap, setShowMiniMap] = useState(true)

  // Create nodes from schema
  const initialNodes: Node[] = useMemo(() => {
    return SCHEMA_DEFINITION.map((table) => ({
      id: table.name,
      data: { table, isSelected: table.name === selectedTable },
      position: TABLE_POSITIONS[table.name] || [0, 0],
      type: 'default',
    }))
  }, [selectedTable])

  // Create edges from relationships
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = []
    const edgeSet = new Set<string>()

    SCHEMA_DEFINITION.forEach((table) => {
      table.fields.forEach((field) => {
        if (field.foreignKey) {
          const edgeId = `${table.name}-${field.foreignKey}`
          if (!edgeSet.has(edgeId)) {
            edges.push({
              id: edgeId,
              source: field.foreignKey,
              target: table.name,
              markerEnd: { type: MarkerType.ArrowClosed },
              animated: table.name === selectedTable || field.foreignKey === selectedTable,
              style: {
                stroke:
                  table.name === selectedTable || field.foreignKey === selectedTable
                    ? '#FF6B6B'
                    : '#ccc',
                strokeWidth:
                  table.name === selectedTable || field.foreignKey === selectedTable ? 3 : 1.5,
              },
            })
            edgeSet.add(edgeId)
          }
        }
      })
    })

    return edges
  }, [selectedTable])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  React.useEffect(() => {
    setNodes(initialNodes)
  }, [selectedTable, setNodes, initialNodes])

  React.useEffect(() => {
    setEdges(initialEdges)
  }, [selectedTable, setEdges, initialEdges])

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  )

  const handleTableClick = (tableName: string) => {
    setSelectedTable(selectedTable === tableName ? null : tableName)
  }

  const getTableStats = (tableName: string) => {
    const table = SCHEMA_DEFINITION.find((t) => t.name === tableName)
    if (!table) return { fields: 0, fks: 0 }
    const fks = table.fields.filter((f) => f.type === 'FK').length
    return { fields: table.fields.length, fks }
  }

  return (
    <div className="schema-visualizer-container">
      <div className="visualizer-header">
        <h2>Database Schema Overview</h2>
        <div className="header-controls">
          <button
            className="control-btn"
            onClick={() => setShowMiniMap(!showMiniMap)}
            title="Toggle minimap"
          >
            🗺️ Minimap
          </button>
          <button className="control-btn" title="Reset view">
            ↺ Reset
          </button>
        </div>
      </div>

      <div className="visualizer-content">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={{ default: TableNode }}
          fitView
        >
          <Background color="#aaa" gap={16} />
          <Controls />
          {showMiniMap && <MiniMap />}
        </ReactFlow>
      </div>

      <div className="schema-sidebar">
        <h3>Tables ({SCHEMA_DEFINITION.length})</h3>
        <div className="table-list">
          {SCHEMA_DEFINITION.map((table) => {
            const stats = getTableStats(table.name)
            return (
              <div
                key={table.name}
                className={`table-item ${selectedTable === table.name ? 'active' : ''}`}
                onClick={() => handleTableClick(table.name)}
                style={{
                  borderLeftColor: table.color,
                }}
              >
                <div className="table-name">{table.name}</div>
                <div className="table-stats">
                  <span>{stats.fields} fields</span>
                  {stats.fks > 0 && <span>{stats.fks} FKs</span>}
                </div>
              </div>
            )
          })}
        </div>

        {selectedTable && (
          <div className="selected-table-info">
            <h4>Details: {selectedTable}</h4>
            <div className="table-details">
              {SCHEMA_DEFINITION.find((t) => t.name === selectedTable)?.fields.map((field) => (
                <div key={field.name} className="detail-row">
                  <span className="detail-name">{field.name}</span>
                  <span className={`detail-type ${field.type === 'FK' ? 'fk' : ''}`}>
                    {field.type}
                  </span>
                  {field.nullable && <span className="nullable">NULL</span>}
                  {field.foreignKey && (
                    <span className="fk-ref">→ {field.foreignKey}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
