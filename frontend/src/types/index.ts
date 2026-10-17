export interface DashboardMetrics {
  observations: number;
  handles: number;
  indicators: number;
  candidate_clues: number;
  reviewed_clues: number;
  incidents: number;
}

export interface GraphNode {
  data: {
    id: string;
    label: string;
    full_label: string;
    type: string;
    properties: Record<string, any>;
  };
}

export interface GraphEdge {
  data: {
    id: string;
    source: string;
    target: string;
    label: string;
    properties: Record<string, any>;
  };
}

export interface GraphElements {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SignalDetail {
  name: string;
  weight: number;
  value: number | null;
  status: 'available' | 'missing';
  contribution: number;
  reliability: 'normal' | 'low';
  method: string;
  details: string;
  evidence_ids: string[];
}

export interface Clue {
  clue_id: string;
  handle_a: string;
  handle_b: string;
  score: number;
  score_type: string;
  status: 'candidate' | 'under_review' | 'supported' | 'rejected';
  priority: 'high' | 'normal';
  coverage: number;
  signals: Record<string, SignalDetail>;
  evidence_ids: string[];
  explanation: string[];
  contradictions: string[];
  limitations: string[];
  scoring_method_version: string;
  reviewer?: string;
  review_notes?: string;
  reviewed_at?: string;
}

export interface GraphRAGResponse {
  question: string;
  answer: string;
  evidence_references: any[];
  limitations: string[];
  llm_available: boolean;
  model: string;
}

export interface TorStatus {
  configured: boolean;
  enabled: boolean;
  proxy: string;
  reachable: boolean;
  message: string;
}

export interface IngestReport {
  batch_id: string;
  filename: string;
  format: string;
  total_records: number;
  accepted: number;
  duplicates_in_batch: number;
  duplicates_existing: number;
  rejected: Array<{ index: number; reason: string }>;
  extractions: Record<string, number>;
  synthetic?: boolean;
}

