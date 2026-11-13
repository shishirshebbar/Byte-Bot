import type { Transaction } from './api';
export type Answer = 'yes' | 'no' | 'unknown';
export type CaseStatus = 'Open' | 'Bank Contacted' | 'Reported' | 'Awaiting Response' | 'Resolved' | 'Closed';
export type Context = {
  expected_payment: Answer; knows_sender: Answer; repayment_requested: Answer; already_sent_money: Answer;
  contact_channels: string[] | null; pressure_tactics: string[] | null;
  requested_destination_type: string; requested_vpa: string | null;
};
export type Evidence = { id: string; type: 'message' | 'call_summary' | 'screenshot'; review_state: 'confirmed' | 'needs_review' | 'ocr_failed'; ocr_text: string | null; confirmed_text: string | null; notice: string | null };
export type Finding = { kind: string; text: string; source: string; reference: string; quote: string | null; rule_id: string };
export type Assessment = {
  category: 'High concern' | 'Needs verification' | 'No strong indicators found' | 'Unable to assess';
  summary: string; findings: Finding[]; limitations: string[]; recommendations: string[];
  rule_version: string; triggered_rules: string[]; generated_at: string; provider_mode: string; extraction_status: string;
  intelligence_matches: { identifier: string; source_label: string; reported_at: string; match_type: string; limitations: string; incident_reference: string }[];
};
export type Analysis = { run_id: string; input_revision: number; state: 'queued' | 'running' | 'complete' | 'failed'; stage: string; error_code: string | null; notices: string[]; result: Assessment | null };
export type Investigation = { id: string; transaction_id: string; transaction: Transaction; input_revision: number; case_status: CaseStatus; status_revision: number; context: Context; evidence: Evidence[]; analysis: Analysis | null };
