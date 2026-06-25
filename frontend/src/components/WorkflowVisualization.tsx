import ReactFlow, {
  Node,
  Edge,
  Handle,
  Position,
  NodeProps,
  MarkerType,
  Background,
  BackgroundVariant,
  Controls,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  FileUp, ClipboardList, BarChart2, FileEdit, MessageSquare, Trophy,
  CheckCircle2, XCircle,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type WorkflowStatus = 'pending' | 'running' | 'completed' | 'error'

interface ColorClasses {
  bg: string
  border: string
  icon: string
  text: string
}

interface WorkflowNodeData {
  label: string
  icon: React.ComponentType<{ className?: string }>
  status: WorkflowStatus
  colorClasses: ColorClasses
  score?: number
}

export interface WorkflowVisualizationProps {
  currentStep?: string
  completedSteps?: string[]
  scores?: { match?: number }
  showControls?: boolean
  interactive?: boolean
}

// ---------------------------------------------------------------------------
// Status indicator
// ---------------------------------------------------------------------------

function StatusDot({ status }: { status: WorkflowStatus }) {
  if (status === 'completed') return <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
  if (status === 'error')     return <XCircle      className="h-3.5 w-3.5 text-red-500  shrink-0" />
  if (status === 'running') {
    return <div className="h-2.5 w-2.5 shrink-0 rounded-full bg-yellow-400 animate-pulse" />
  }
  return <div className="h-2.5 w-2.5 shrink-0 rounded-full bg-gray-300" />
}

// ---------------------------------------------------------------------------
// Custom node
// ---------------------------------------------------------------------------

function WorkflowNode({ data }: NodeProps<WorkflowNodeData>) {
  const { label, icon: Icon, status, colorClasses, score } = data
  const isActive = status === 'running' || status === 'completed'

  const bgCls     = status === 'error' ? 'bg-red-50'    : isActive ? colorClasses.bg     : 'bg-white'
  const borderCls = status === 'error' ? 'border-red-300' : isActive ? colorClasses.border : 'border-gray-200'
  const iconCls   = isActive ? colorClasses.icon : 'text-gray-400'
  const textCls   = isActive ? colorClasses.text : 'text-gray-500'

  return (
    <div
      className={`rounded-xl border-2 shadow-sm select-none transition-colors ${bgCls} ${borderCls}`}
      style={{ width: 156, padding: '10px 14px' }}
    >
      {/* Handles — invisible but functional for edge routing */}
      <Handle type="target" position={Position.Top}  style={{ opacity: 0, width: 4, height: 4 }} />
      <Handle type="target" position={Position.Left} id="left" style={{ opacity: 0, width: 4, height: 4 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, width: 4, height: 4 }} />
      <Handle type="source" position={Position.Left}   id="left-out" style={{ opacity: 0, width: 4, height: 4, top: '70%' }} />

      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 shrink-0 ${iconCls}`} />
        <div className="flex-1 min-w-0">
          <p className={`text-xs font-semibold leading-tight truncate ${textCls}`}>{label}</p>
          {score !== undefined && (
            <p className={`text-[10px] mt-0.5 tabular-nums ${isActive ? colorClasses.text : 'text-gray-400'}`}>
              Score: {score}
            </p>
          )}
        </div>
        <StatusDot status={status} />
      </div>
    </div>
  )
}

const nodeTypes = { workflow: WorkflowNode }

// ---------------------------------------------------------------------------
// Node config
// ---------------------------------------------------------------------------

const NODE_COLORS: Record<string, ColorClasses> = {
  upload:    { bg: 'bg-green-50',  border: 'border-green-300',  icon: 'text-green-600',  text: 'text-green-800'  },
  jd:        { bg: 'bg-green-50',  border: 'border-green-300',  icon: 'text-green-600',  text: 'text-green-800'  },
  match:     { bg: 'bg-blue-50',   border: 'border-blue-300',   icon: 'text-blue-600',   text: 'text-blue-800'   },
  rewrite:   { bg: 'bg-orange-50', border: 'border-orange-300', icon: 'text-orange-600', text: 'text-orange-800' },
  interview: { bg: 'bg-purple-50', border: 'border-purple-300', icon: 'text-purple-600', text: 'text-purple-800' },
  coach:     { bg: 'bg-teal-50',   border: 'border-teal-300',   icon: 'text-teal-600',   text: 'text-teal-800'   },
}

function getStatus(id: string, currentStep?: string, completedSteps: string[] = []): WorkflowStatus {
  if (completedSteps.includes(id)) return 'completed'
  if (currentStep === id)          return 'running'
  return 'pending'
}

const EDGE_STYLE = { stroke: '#94a3b8', strokeWidth: 1.5 }
const EDGE_MARKER = { type: MarkerType.ArrowClosed, color: '#94a3b8', width: 14, height: 14 } as const

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function WorkflowVisualization({
  currentStep,
  completedSteps = [],
  scores,
  showControls = false,
  interactive = false,
}: WorkflowVisualizationProps) {
  const st = (id: string) => getStatus(id, currentStep, completedSteps)

  const nodes: Node<WorkflowNodeData>[] = [
    {
      id: 'upload', type: 'workflow',
      position: { x: 10, y: 10 },
      data: { label: 'Upload Resume', icon: FileUp,        status: st('upload'), colorClasses: NODE_COLORS.upload },
    },
    {
      id: 'jd', type: 'workflow',
      position: { x: 210, y: 10 },
      data: { label: 'Parse JD',      icon: ClipboardList, status: st('jd'),     colorClasses: NODE_COLORS.jd },
    },
    {
      id: 'match', type: 'workflow',
      position: { x: 110, y: 130 },
      data: { label: 'Match',         icon: BarChart2,     status: st('match'),  colorClasses: NODE_COLORS.match, score: scores?.match },
    },
    {
      id: 'rewrite', type: 'workflow',
      position: { x: 10, y: 260 },
      data: { label: 'Rewrite',       icon: FileEdit,      status: st('rewrite'), colorClasses: NODE_COLORS.rewrite },
    },
    {
      id: 'interview', type: 'workflow',
      position: { x: 210, y: 260 },
      data: { label: 'Interview',     icon: MessageSquare, status: st('interview'), colorClasses: NODE_COLORS.interview },
    },
    {
      id: 'coach', type: 'workflow',
      position: { x: 210, y: 390 },
      data: { label: 'Coach Review',  icon: Trophy,        status: st('coach'),  colorClasses: NODE_COLORS.coach },
    },
  ]

  const edges: Edge[] = [
    {
      id: 'e-upload-match',
      source: 'upload', target: 'match',
      type: 'smoothstep',
      style: EDGE_STYLE, markerEnd: EDGE_MARKER,
    },
    {
      id: 'e-jd-match',
      source: 'jd', target: 'match',
      type: 'smoothstep',
      style: EDGE_STYLE, markerEnd: EDGE_MARKER,
    },
    {
      id: 'e-match-rewrite',
      source: 'match', target: 'rewrite',
      type: 'smoothstep',
      label: 'score < 70',
      labelStyle: { fontSize: 9, fill: '#6b7280', fontWeight: 500 },
      labelBgStyle: { fill: '#f9fafb', fillOpacity: 0.9 },
      labelBgPadding: [3, 5] as [number, number],
      style: EDGE_STYLE, markerEnd: EDGE_MARKER,
    },
    {
      id: 'e-match-interview',
      source: 'match', target: 'interview',
      type: 'smoothstep',
      label: 'score ≥ 70',
      labelStyle: { fontSize: 9, fill: '#6b7280', fontWeight: 500 },
      labelBgStyle: { fill: '#f9fafb', fillOpacity: 0.9 },
      labelBgPadding: [3, 5] as [number, number],
      style: EDGE_STYLE, markerEnd: EDGE_MARKER,
    },
    {
      id: 'e-rewrite-match',
      source: 'rewrite', target: 'match',
      sourceHandle: 'left-out', targetHandle: 'left',
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#f97316', strokeWidth: 1.5, strokeDasharray: '5 5' },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#f97316', width: 14, height: 14 },
    },
    {
      id: 'e-interview-coach',
      source: 'interview', target: 'coach',
      type: 'smoothstep',
      style: EDGE_STYLE, markerEnd: EDGE_MARKER,
    },
  ]

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={interactive}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={interactive}
      zoomOnScroll={interactive}
      zoomOnPinch={interactive}
      preventScrolling={!interactive}
    >
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e5e7eb" />
      {showControls && <Controls showInteractive={false} />}
    </ReactFlow>
  )
}
