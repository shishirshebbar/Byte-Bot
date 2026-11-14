from datetime import datetime
from typing import Literal
from uuid import UUID
from .analysis_schemas import AnalysisStatus
from pydantic import PrivateAttr, model_validator, BaseModel, ConfigDict, Field, field_validator
from .redaction import redact
from .transactions import Transaction

Answer = Literal['yes', 'no', 'unknown']
CaseStatus = Literal['Open', 'Bank Contacted', 'Reported', 'Awaiting Response', 'Resolved', 'Closed']
Channel = Literal['call', 'whatsapp', 'sms', 'paytm_request', 'other']
Pressure = Literal['urgency', 'threat', 'bank_avoidance', 'secrecy']
Destination = Literal['unknown', 'same_sender', 'different_vpa', 'bank_account', 'payment_request', 'not_specified']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Context(StrictModel):
    expected_payment: Answer = 'unknown'
    knows_sender: Answer = 'unknown'
    repayment_requested: Answer = 'unknown'
    contact_channels: list[Channel] | None = Field(default=None, max_length=5)
    requested_destination_type: Destination = 'unknown'
    requested_vpa: str | None = Field(default=None, max_length=256)
    pressure_tactics: list[Pressure] | None = Field(default=None, max_length=4)
    already_sent_money: Answer = 'unknown'

    @field_validator('requested_vpa')
    @classmethod
    def clean_vpa(cls, value):
        if value is None:
            return None
        value = redact(value)
        if len(value) > 256:
            raise ValueError('Value is too long')
        return value or None

    @field_validator('contact_channels', 'pressure_tactics')
    @classmethod
    def unique_choices(cls, value):
        return sorted(set(value)) if value is not None else None


class ContextPatch(Context):
    expected_revision: int = Field(ge=0, strict=True)


class CreateInvestigation(StrictModel):
    transaction_id: UUID


class TextEvidence(StrictModel):
    _request_markers: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode='wrap')
    @classmethod
    def preserve_safe_markers(cls, data, handler):
        from .safety import request_markers
        markers = request_markers(data.get('text', '')) if isinstance(data, dict) and isinstance(data.get('text'), str) else []
        result = handler(data)
        result._request_markers = markers
        return result

    type: Literal['message', 'call_summary']
    text: str = Field(min_length=1, max_length=10000)
    expected_revision: int = Field(ge=0, strict=True)

    @field_validator('text')
    @classmethod
    def clean(cls, value):
        value = redact(value)
        if not value or len(value) > 10000:
            raise ValueError('Provide up to 10000 characters')
        return value


class ConfirmEvidence(StrictModel):
    _request_markers: list[str] = PrivateAttr(default_factory=list)
    _preserve = model_validator(mode='wrap')(TextEvidence.preserve_safe_markers.__func__)

    text: str = Field(min_length=1, max_length=10000)
    confirmed: Literal[True]
    expected_revision: int = Field(ge=0, strict=True)

    _clean = field_validator('text')(TextEvidence.clean.__func__)


class Evidence(BaseModel):
    id: UUID
    type: Literal['message', 'call_summary', 'screenshot', 'voice_note']
    review_state: Literal['needs_review', 'ocr_failed', 'confirmed']
    ocr_text: str | None
    confirmed_text: str | None
    metadata: dict
    notice: Literal['ocr_unavailable', 'unreadable'] | None
    created_at: datetime
    updated_at: datetime


class EscalationReason(BaseModel):
    code: str
    label: str


class Escalation(BaseModel):
    id: UUID
    source: Literal['agent', 'customer']
    priority: Literal['urgent', 'high', 'normal']
    state: Literal['open', 'assigned', 'resolved']
    reasons: list[EscalationReason]
    sla_due_at: datetime
    created_at: datetime
    updated_at: datetime
    assignee: str | None = None


class Investigation(BaseModel):
    id: UUID
    transaction_id: UUID
    input_revision: int
    case_status: CaseStatus
    status_revision: int
    workflow_state: Literal['collecting_context', 'analysis_queued', 'analyzing', 'results_ready', 'analysis_failed']
    created_at: datetime
    updated_at: datetime
    transaction: Transaction
    context: Context
    evidence: list[Evidence]
    analysis: AnalysisStatus | None = None
    escalation: Escalation | None = None


class FollowUpAnswers(StrictModel):
    answers: Context
    expected_revision: int = Field(ge=0, strict=True)


class ConsentRequest(StrictModel):
    decision: Literal['approve', 'decline']
    expected_revision: int = Field(ge=0, strict=True)


class EscalationRequest(StrictModel):
    pass


class SpeakRequest(StrictModel):
    language: Literal['en-IN', 'hi-IN', 'bn-IN', 'ta-IN', 'te-IN', 'kn-IN', 'ml-IN', 'mr-IN', 'gu-IN', 'pa-IN', 'od-IN']


class EvidenceResult(BaseModel):
    evidence: Evidence
    input_revision: int
