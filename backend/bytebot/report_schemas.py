from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .analysis_schemas import Assessment, Category, Kind
from .transactions import Transaction
from .investigation_schemas import Context, CaseStatus


class StatusPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: CaseStatus
    expected_status_revision: int = Field(ge=0, strict=True)


class Incident(BaseModel):
    id: UUID
    transaction: Transaction
    created_at: datetime
    case_status: CaseStatus
    status_revision: int
    category: Category | None


class IncidentList(BaseModel):
    incidents: list[Incident]


class ReportEvidence(BaseModel):
    id: UUID
    type: Literal['message', 'call_summary', 'screenshot']
    source: str
    text: str


class ReportSignal(BaseModel):
    evidence_id: UUID
    kind: Kind
    quote: str
    value: str | None = None


class ReportSnapshot(BaseModel):
    schema_version: Literal[1] = 1
    id: UUID
    investigation_id: UUID
    input_revision: int
    run_id: UUID
    generated_at: datetime
    status_at_generation: CaseStatus
    transaction: Transaction
    transaction_explanation: str
    user_statements: Context
    evidence: list[ReportEvidence]
    extracted_signals: list[ReportSignal]
    assessment: Assessment
    unknowns: list[str]
    notices: list[str]
