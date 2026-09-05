export type Status = "confirmed" | "assumed" | "unknown" | "rejected";
export type ContextItem = {
  id: string;
  category: string;
  title: string;
  content: string;
  status: Status;
  source: string;
  confidence: number;
};
export type Organization = {
  id: string;
  name: string;
  description: string;
  mode: string;
  blueprint_validated: boolean;
  maturity?: { overall: number; categories: Record<string, string> };
};
export type Rule = { id: string; kind: "must" | "must_not"; content: string };
export type Product = {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  users: string;
  primary_goal: string;
  current_user_journey: string;
  major_features: string;
  business_metrics: string;
  constraints: string;
  technical_context: string;
};
export type Question = {
  id: string;
  question: string;
  reason: string;
  category: string;
  required: boolean;
  answer: string;
  status: string;
};
export type Assumption = {
  id: string;
  title: string;
  content: string;
  status: Status;
  promoted_context_id: string | null;
};
export type Requirement = {
  id: string;
  requirement_code: string;
  title: string;
  description: string;
  type: string;
  priority: string;
  acceptance_criteria: string[];
  dependencies: string[];
  edge_cases: string[];
};
export type Issue = {
  id: string;
  severity: string;
  category: string;
  title: string;
  description: string;
  affected_section: string;
  current_text: string;
  suggested_change: string;
  status: string;
};
export type Brief = {
  problem_statement: string;
  target_users: string;
  current_user_journey: string;
  proposed_solution: string;
  value_proposition: string;
  goals: string[];
  non_goals: string[];
  assumptions: { title: string; content: string; status: string }[];
  open_questions: string[];
  constraints: string[];
  dependencies: string[];
  success_metrics: string[];
};
export type PRD = {
  id: string;
  product_id: string;
  title: string;
  idea: string;
  status: string;
  ai_relevant: boolean;
  created_at: string;
  updated_at: string;
  sections: Record<string, unknown>;
  document_sections: Record<string, unknown>;
  context_snapshot: Record<string, unknown>;
  questions: Question[];
  brief: { content: Brief; approved: boolean } | null;
  requirements: Requirement[];
  assumptions: Assumption[];
  review_issues: Issue[];
  quality: {
    overall: number;
    breakdown: Record<string, number>;
    issues: number;
  };
};
export const categories = [
  "overview",
  "industry",
  "customers",
  "business_model",
  "products",
  "metrics",
  "technology",
  "compliance",
  "principles",
  "terminology",
  "rules",
  "open_questions",
];
export const label = (s: string) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
