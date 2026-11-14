import type { Transaction } from './api';
export type Answer = 'yes' | 'no' | 'unknown';
export type CaseStatus = 'Open' | 'Bank Contacted' | 'Reported' | 'Awaiting Response' | 'Resolved' | 'Closed';
export type Context = {
  expected_payment: Answer; knows_sender: Answer; repayment_requested: Answer; already_sent_money: Answer;
  contact_channels: string[] | null; pressure_tactics: string[] | null;
  requested_destination_type: string; requested_vpa: string | null;
};
export type Evidence = { id: string; type: 'message' | 'call_summary' | 'screenshot' | 'voice_note'; review_state: 'confirmed' | 'needs_review' | 'ocr_failed'; ocr_text: string | null; confirmed_text: string | null; notice: string | null };
export type Finding = { kind: string; text: string; source: string; reference: string; quote: string | null; rule_id: string };
export type Assessment = {
  category: 'High concern' | 'Needs verification' | 'No strong indicators found' | 'Unable to assess';
  summary: string; findings: Finding[]; limitations: string[]; recommendations: string[];
  rule_version: string; triggered_rules: string[]; generated_at: string; provider_mode: string; extraction_status: string;
  risk_score?: number; score_version?: string | null; risk_factors?: { id: string; label: string; weight: number; status: string; sources: string[]; detail: string }[];
  graph_links?: { identifier: string; incidents: string[]; min_hops: number; via: string[] }[];
  intelligence_matches: { identifier: string; source_label: string; reported_at: string; match_type: string; limitations: string; incident_reference: string }[];
};
export type TraceStep = { seq: number; node: string; reason: string; created_at: string };
export type FollowUp = { id: string; field: keyof Context; prompt: string; multi: boolean; options: { value: string; label: string }[]; blocking: boolean; state: 'open' | 'answered' | 'revoked' };
export type AgentAction = { id: string; action_type: string; label: string; system: string; reversible: boolean; verdict: 'auto' | 'needs_customer_consent' | 'needs_human_approval' | 'deny'; state: 'approved' | 'awaiting_consent' | 'awaiting_human' | 'denied' | 'declined' | 'executed' | 'failed' | 'compensated' | 'revoked'; actor: 'agent' | 'customer' | 'human'; reason: string; system_reference: string | null; system_label: string; detail: string | null };
export type AgentState = { policy_version: string; outcome: 'needs_customer_info' | 'escalated' | 'awaiting_consent' | 'actions_ready' | 'actions_completed' | 'resolved' | null; trace: TraceStep[]; follow_ups: FollowUp[]; actions: AgentAction[] };
export type Escalation = { id: string; source: 'agent' | 'customer'; priority: 'urgent' | 'high' | 'normal'; state: 'open' | 'assigned' | 'resolved'; reasons: { code: string; label: string }[]; sla_due_at: string; created_at: string; updated_at: string };
export type Analysis = { run_id: string; input_revision: number; state: 'queued' | 'running' | 'complete' | 'failed'; stage: string; error_code: string | null; notices: string[]; result: Assessment | null; prepare_report: boolean; report_id: string | null; agent?: AgentState | null; duration_seconds?: number | null };
export type Investigation = { id: string; transaction_id: string; transaction: Transaction; input_revision: number; case_status: CaseStatus; status_revision: number; context: Context; evidence: Evidence[]; analysis: Analysis | null; escalation?: Escalation | null };
