import { useContext, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, get } from './api';
import type { Transaction } from './api';
import type { Assessment, CaseStatus, Context, Investigation } from './investigation-types';
import { date, money, Status } from './transaction-ui';
import { PresentationState } from './presentation-state';
import { useScreenPath } from './screen-path';

type Report = {
  id: string; investigation_id: string; input_revision: number; run_id: string; generated_at: string;
  status_at_generation: CaseStatus; transaction: Transaction; transaction_explanation: string;
  user_statements: Context; evidence: { id: string; type: string; source: string; text: string }[];
  extracted_signals: { evidence_id: string; kind: string; quote: string; value: string | null }[];
  assessment: Assessment; unknowns: string[]; notices: string[];
};

export async function downloadReport(caseId: string, reportId: string) {
  const response = await fetch(`/api/v1/investigations/${caseId}/report?format=txt`, { credentials: 'same-origin' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.message || 'The report is unavailable. Reload the saved case.');
  }
  const filename = `bytebot-report-${reportId}.txt`;
  if (response.headers.get('content-disposition') !== `attachment; filename="${filename}"`) {
    throw new ApiError(409, 'The saved report changed. Review it before downloading.');
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const labels: Record<keyof Context, string> = {
  expected_payment: 'Expected payment', knows_sender: 'Knows sender', repayment_requested: 'Repayment requested',
  contact_channels: 'Contact channels', requested_destination_type: 'Requested destination type', requested_vpa: 'Requested UPI ID',
  pressure_tactics: 'Reported pressure', already_sent_money: 'Already sent money',
};
function answer(value: string | string[] | null) { return value === null || value === 'unknown' ? 'Not supplied or unknown' : Array.isArray(value) ? value.join(', ') || 'None reported' : value; }

export function ReportPage() {
  const { id } = useParams();
  const screen = useScreenPath();
  const { showCase } = useContext(PresentationState) ?? {};
  const [snapshot, setData] = useState<Report>();
  const data = snapshot?.investigation_id === id ? snapshot : undefined;
  const [error, setError] = useState<ApiError>();
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  useEffect(() => {
    const abort = new AbortController(); setData(undefined); setError(undefined); setDownloadError('');
    async function load() {
      try {
        const next = await get<Report>(`/investigations/${id}/report`, abort.signal);
        if (abort.signal.aborted) return;
        setData(next);
      } catch (e) {
        if (abort.signal.aborted) return;
        setError(e as ApiError);
      }
      if (!showCase || abort.signal.aborted) return;
      try {
        const saved = await get<Investigation>(`/investigations/${id}`, abort.signal);
        if (!abort.signal.aborted) showCase(saved);
      } catch {
        if (!abort.signal.aborted) showCase(undefined);
      }
    }
    void load();
    return () => abort.abort();
  }, [id, attempt, showCase]);
  useEffect(() => {
    const refresh = () => { setData(undefined); setAttempt(v => v + 1); };
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [id]);
  async function download() {
    if (!data) return;
    setBusy(true); setDownloadError('');
    try {
      await downloadReport(data.investigation_id, data.id);
    } catch (e) {
      if (e instanceof ApiError && [404, 409].includes(e.status)) {
        setData(undefined); setAttempt(v => v + 1);
      }
      setDownloadError((e as Error).message);
    }
    finally { setBusy(false); }
  }
  const a = data?.assessment;
  return <><Link className="back" to={screen(`/investigations/${id}/results`)}>← Investigation results</Link><div className="eyebrow">BYTE BOT · USER-OWNED DOWNLOAD</div><h1>Incident report</h1>
    {error && <div className="error-box" role="alert"><h2>{error.status === 409 ? 'Analysis needed' : 'Report unavailable'}</h2><p>{error.message}</p><p>Generate a report from a completed current result.</p><button onClick={() => setAttempt(v => v + 1)}>Reload report</button><p><Link to={screen(`/investigations/${id}`)}>Review saved context and evidence</Link></p></div>}
    {!data && !error && <p role="status">Loading saved report…</p>}
    {data && a && <>
      <section className="panel"><div className="section-body"><p><strong>{a.category}</strong> · {data.transaction.status} payment</p><p className="primary-guidance">{a.recommendations[0]}</p><p><strong>Report ID:</strong> {data.id}</p><p>Case ID: {data.investigation_id} · Input revision: {data.input_revision}</p><p>Analysis run: {data.run_id}</p><p>Generated {date(data.generated_at)} IST</p><p>Status at generation: {data.status_at_generation}</p>
        <button disabled={busy} onClick={() => void download()}>{busy ? 'Preparing download…' : 'Download text report'}</button><p className="field-help">This report is saved for you. Byte Bot has not submitted it to anyone.</p>{downloadError && <p role="alert">{downloadError}</p>}
      </div></section>
      <section className="panel"><div className="panel-heading"><h2>Transaction facts</h2><Status value={data.transaction.status} /></div><div className="section-body"><h3>{money(data.transaction)}</h3><p>{data.transaction_explanation}</p><dl>{Object.entries(data.transaction).filter(([key]) => key !== 'amount_paise' && key !== 'status').map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl></div></section>
      <section className="panel"><div className="panel-heading"><h2>User statements</h2></div><div className="section-body"><p>Reported by you; not independently verified.</p><dl>{Object.entries(data.user_statements).map(([key, value]) => <div key={key}><dt>{labels[key as keyof Context]}</dt><dd>{answer(value)}</dd></div>)}</dl></div></section>
      <section className="panel"><div className="panel-heading"><h2>Confirmed redacted evidence</h2></div><div className="section-body">{data.evidence.length === 0 && <p>No evidence submitted.</p>}{data.evidence.map(e => <article className="finding" key={e.id}><h3>{e.type} · {e.source}</h3><p className="finding-reference">Evidence {e.id}</p><blockquote>{e.text}</blockquote></article>)}</div></section>
      <section className="panel"><div className="panel-heading"><h2>Validated extracted signals</h2></div><div className="section-body">{data.extracted_signals.length === 0 && <p>No validated extracted signals available.</p>}{data.extracted_signals.map((s, i) => <article className="finding" key={i}><h3>{s.kind}</h3><p>Value: {s.value ?? 'Not supplied'}</p><blockquote>{s.quote}</blockquote><p className="finding-reference">Source evidence: {s.evidence_id}</p></article>)}</div></section>
      <section className={`panel result-summary ${a.category === 'High concern' ? 'concern' : ''}`}><div className="section-body"><div className="eyebrow">{a.provider_mode === 'fixture' ? 'SYNTHETIC EXTRACTION FIXTURE' : 'RULE-BASED ASSESSMENT'}</div><h2>{a.category}</h2><p>{a.summary}</p><p className="primary-guidance">{a.recommendations[0]}</p><p>Assessment generated {date(a.generated_at)} IST · {a.rule_version}</p><p>Triggered rules: {a.triggered_rules.join(', ')}</p><p>Extraction: {a.extraction_status} · Provider mode: {a.provider_mode}</p></div></section>
      {a.findings.some(f => ['credential_request', 'collect_approval', 'remote_access', 'screen_sharing'].includes(f.kind)) && <aside className="guidance safety-warning" role="alert"><h2>Safety warning</h2><p>Never disclose credentials, enable remote access, or approve an unexpected collect request. This warning also applies when the payment is pending or failed.</p></aside>}
      <section className="panel"><div className="panel-heading"><h2>Findings and provenance</h2></div><div className="section-body">{a.findings.map((f, i) => <article className="finding" key={i}><h3>{f.text}</h3><p>Source: {f.source}</p>{f.quote && <blockquote>{f.quote}</blockquote>}<p className="finding-reference">Reference: {f.reference} · Rule: {f.rule_id}</p></article>)}</div></section>
      <section className="panel"><div className="panel-heading"><h2>Simulated intelligence matches</h2></div><div className="section-body">{a.intelligence_matches.length === 0 && <p>No match found in the available demo data. This does not imply trust.</p>}{a.intelligence_matches.map((m, i) => <article key={i}><h3>{m.identifier}</h3><p>{m.source_label} · {m.match_type} · {m.reported_at}</p><p>{m.incident_reference}: {m.limitations}</p></article>)}</div></section>
      <section className="panel"><div className="panel-heading"><h2>Unknowns and limitations</h2></div><div className="section-body"><ul>{[...data.unknowns, ...a.limitations, ...data.notices].map((text, i) => <li key={i}>{text}</li>)}</ul></div></section>
      <section className="panel"><div className="panel-heading"><h2>Recommended next steps</h2></div><div className="section-body"><ol>{a.recommendations.map(text => <li key={text}>{text}</li>)}</ol></div></section>
    </>}
    <p className="footnote">Byte Bot cannot confirm fraud, move money, contact your bank, or submit this report. Recovery cannot be promised. Changed case inputs invalidate the server copy; previously downloaded files remain with you.</p>
  </>;
}
