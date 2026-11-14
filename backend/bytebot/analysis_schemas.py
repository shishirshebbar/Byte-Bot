"""Validated analysis interfaces. Model output never assigns a category."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

RULE_VERSION = 'foundation-rules-2'
SCORE_VERSION = 'score-1'
Kind = Literal['repayment', 'amount', 'vpa', 'phone', 'urgency', 'threat',
               'bank_avoidance', 'secrecy', 'credential_request', 'collect_approval',
               'remote_access', 'screen_sharing']
Category = Literal['High concern', 'Needs verification', 'No strong indicators found', 'Unable to assess']
Stage = Literal['queued', 'transaction_context', 'message_analysis', 'risk_investigation', 'incident_resolution', 'complete']


class Claim(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_ref: str = Field(max_length=16)
    kind: Kind
    quote: str = Field(min_length=1, max_length=1000)
    value: str | None = Field(default=None, max_length=256)


class Extraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claims: list[Claim] = Field(default_factory=list, max_length=200)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0, strict=True)


class AnalyzeRequest(RevisionRequest):
    prepare_report: bool = Field(default=False, strict=True)


class Finding(BaseModel):
    kind: str
    text: str
    source: str
    reference: str
    quote: str | None = None
    rule_id: str


class Assessment(BaseModel):
    category: Category
    rule_version: str
    triggered_rules: list[str]
    findings: list[Finding]
    limitations: list[str]
    recommendations: list[str]
    summary: str
    generated_at: datetime
    intelligence_matches: list[dict]
    extraction_status: str
    provider_mode: str
    risk_score: int = 0
    score_version: str | None = None
    risk_factors: list[dict] = Field(default_factory=list)
    graph_links: list[dict] = Field(default_factory=list)


class TraceStep(BaseModel):
    seq: int
    node: str
    reason: str
    created_at: datetime


class Option(BaseModel):
    value: str
    label: str


class FollowUp(BaseModel):
    id: UUID
    field: str
    prompt: str
    multi: bool
    options: list[Option]
    blocking: bool
    state: Literal['open', 'answered', 'revoked']


class AgentAction(BaseModel):
    id: UUID
    action_type: str
    label: str
    system: str
    reversible: bool
    verdict: Literal['auto', 'needs_customer_consent', 'needs_human_approval', 'deny']
    state: Literal['approved', 'awaiting_consent', 'awaiting_human', 'denied', 'declined', 'executed', 'failed', 'compensated', 'revoked']
    actor: Literal['agent', 'customer', 'human']
    reason: str
    system_reference: str | None = None
    system_label: str
    detail: str | None = None


Outcome = Literal['needs_customer_info', 'escalated', 'awaiting_consent', 'actions_ready', 'actions_completed', 'resolved']


class AgentState(BaseModel):
    policy_version: str
    outcome: Outcome | None
    trace: list[TraceStep]
    follow_ups: list[FollowUp]
    actions: list[AgentAction]


class AnalysisStatus(BaseModel):
    run_id: UUID
    input_revision: int
    state: Literal['queued', 'running', 'complete', 'failed']
    stage: Stage
    error_code: str | None = None
    notices: list[str] = Field(default_factory=list)
    result: Assessment | None = None
    prepare_report: bool
    report_id: UUID | None = None
    agent: AgentState | None = None
    duration_seconds: float | None = None
