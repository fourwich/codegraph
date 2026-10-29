export interface CodeNodeInfo {
  uid: string;
  kind: string;
  name: string;
  file_path: string;
  line_start: number;
  line_end: number;
  language: string;
  commit_sha?: string;
}

export interface DecisionCard {
  uid: string;
  content: string;
  reason: string;
  alternatives: string[];
  status: string;
  source: string;
  source_ref: string;
  timestamp: string;
  author: string;
  file_path: string;
  line: number | null;
  constraints: string[];
  confidence: number;
  category?: string;
  tier?: string;
}

export interface WhyResult {
  file: string;
  line: number;
  node: CodeNodeInfo | null;
  decisions: DecisionCard[];
  binding?: string;
  /** Decisions that govern the whole file, when nothing is bound to the line. */
  related?: DecisionCard[];
}

export interface IndexResult {
  root: string;
  commits: number;
  nodes: number;
  edges: number;
  decisions: number;
}
