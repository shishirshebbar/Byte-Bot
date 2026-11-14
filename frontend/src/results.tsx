import { useContext, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError, get, json } from './api';
import type { Investigation, Analysis } from './investigation-types';
import { date, money, Status, statusExplanation } from './transaction-ui';
import { PresentationState, useCaseSnapshot, usePhoneLock } from './presentation-state';
import { useScreenPath } from './screen-path';
import { StatusControl } from './incidents';
import { downloadReport } from './report';
import { highlightedFindings } from './findings';
import { AgentPanel, RiskOverview } from './agent-ui';
import { StoryChain, VerdictBanner } from './story-ui';

const stages = [
  ['transaction_context', 'Checking transaction context'],
  ['message_analysis', 'Reviewing confirmed evidence'],
  ['risk_investigation', 'Checking simulated intelligence and risk rules'],
  ['incident_resolution', 'Preparing explanations and guidance'],
];
const dangerous = new Set(['credential_request', 'collect_approval', 'remote_access', 'screen_sharing', 'qr_payment', 'pin_to_receive']);

export function ResultsPage() {
  const navigate = useNavigate();
  const screen = useScreenPath();
  const { id } = useParams();
  const [snapshot, setData] = useState<Investigation>();
  const data = snapshot?.id === id ? snapshot : undefined;
  const [error, setError] = useState('');
  const [reportError, setReportError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const presentation = useContext(PresentationState);
  const showCase = presentation?.showCase;
  useCaseSnapshot(data);
  usePhoneLock(busy);
  useEffect(() => setReportError(''), [id]);
  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setError('');
    async function load() {
      try {
        const next = await get<Investigation>(`/investigations/${id}`, abort.signal);
        if (abort.signal.aborted) return;
        setData(current => current?.id === next.id && current.status_revision > next.status_revision
          ? { ...next, case_status: current.case_status, status_revision: current.status_revision }
          : next);
        if (next.analysis && ['queued', 'running'].includes(next.analysis.state)) timer = setTimeout(() => void load(), 1000);
      } catch (e) {
        if (!abort.signal.aborted) {
          setError((e as Error).message); setData(undefined); showCase?.(undefined);
        }
      }
    }
    void load();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [id, attempt, showCase]);
  useEffect(() => {
    if (!presentation || busy) return;
    const refresh = () => setAttempt(value => value + 1);
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [presentation, busy]);
  async function retry() {
    if (!data) return;
    setBusy(true); setError('');
    try {
      const analysis = await json<Analysis>(`/investigations/${id}/analyze`, 'POST', {
        expected_revision: data.input_revision,
        ...(data.analysis?.prepare_report ? { prepare_report: true } : {}),
      });
      presentation?.showCase({ ...data, analysis });
      setAttempt(v => v + 1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const run = data?.analysis;
  const result = run?.result;
  const findings = result ? highlightedFindings(result.findings) : [];
  const reportPath = screen(`/investigations/${id}/report`);
  async function reportAction(action: 'download' | 'prepare') {
    if (!data || !run || busy) return;
    setReportError('');
    setBusy(true);
    try {
      if (action === 'download' && run.report_id) {
        await downloadReport(data.id, run.report_id);
      } else if (action === 'prepare') {
        const report = await json<{ id: string }>(`/investigations/${data.id}/report`, 'POST', { expected_revision: data.input_revision });
        if (presentation) {
          setData(current => current?.analysis?.run_id === run.run_id
            ? { ...current, analysis: { ...current.analysis, report_id: report.id } }
            : current);
        } else {
          navigate(reportPath);
        }
      }
    } catch (e) {
      setReportError((e as Error).message);
      if (e instanceof ApiError && [404, 409].includes(e.status)) {
        setData(undefined);
        showCase?.(undefined);
        setAttempt(value => value + 1);
      }
    } finally {
      setBusy(false);
    }
  }
  const summary = result && <section className={`panel result-summary ${result.category === 'High concern' ? 'concern' : ''}`} aria-label="Assessment">
    <div className="section-body"><div className="eyebrow">{result.provider_mode === 'fixture' ? 'SYNTHETIC EXTRACTION FIXTURE' : 'RULE-BASED ASSESSMENT'}</div>
      <h2>{result.category}</h2><p>{result.summary}</p><p className="primary-guidance">{result.recommendations[0]}</p>
      {presentation && data?.context.already_sent_money !== 'yes' &&
        result.recommendations.slice(1, -1).map(text => <p key={text}>{text}</p>)}
      <p className="field-help">Generated {date(result.generated_at)} IST · {result.rule_version} · Evidence extraction: {result.extraction_status}</p>
    </div>
  </section>;
  const warning = result?.findings.some(f => dangerous.has(f.kind)) && <aside className="guidance safety-warning" role="alert"><h2>Safety warning</h2><p>Never disclose credentials, enable remote access, or approve an unexpected collect request.</p><p>These warnings remain relevant even when the payment is pending or failed.</p></aside>;
  const agentViews = data && <>
    <AgentPanel data={data} onChange={next => { setData(next); presentation?.showCase(next); setAttempt(value => value + 1); }} />
    <RiskOverview data={data} />
  </>;
  const evidenceLink = (reference: string) => screen(`/investigations/${id}#evidence-${reference}`);
  return <><Link className="back" to={screen(`/investigations/${id}`)}>← Edit saved context and evidence</Link>
    <div className="eyebrow">BYTE BOT · ANALYSIS</div><h1>Investigation results</h1>
    {error && <div role="alert" className="error-box"><p>{error}</p><button onClick={() => setAttempt(v => v + 1)}>Reload saved case</button></div>}
    {reportError && <div role="alert" className="error-box">{reportError}</div>}
    {!data && !error && <p role="status">Loading saved analysis…</p>}
    {data && <>
      {(!presentation || !result) && <section className="panel attached" aria-label="Attached transaction"><div className="panel-heading"><h2>{money(data.transaction)} · {data.transaction.sender_name}</h2><Status value={data.transaction.status} /></div><div className="section-body"><p>{statusExplanation(data.transaction)}</p><p>Source: synthetic transaction record · {date(data.transaction.occurred_at)} IST</p></div></section>}
      {!run && <div role="status" className="notice"><h2>Analysis needed</h2><p>No current result exists. Saved input may have changed. Review your evidence and analyze the current revision.</p></div>}
      {run && ['queued', 'running'].includes(run.state) && <section className="panel analysis-progress" aria-label="Analysis progress"><div className="panel-heading"><h2>Investigation in progress</h2></div><div className="section-body"><p role="status" aria-live="polite">{run.state === 'queued' ? 'Queued for analysis…' : stages.find(([key]) => key === run.stage)?.[1] || 'Preparing analysis…'}</p><ol>{stages.map(([key, label], index) => <li key={key} aria-current={run.stage === key ? 'step' : undefined}>{index < stages.findIndex(([name]) => name === run.stage) ? '✓ ' : ''}{label}</li>)}</ol><p>Your case is saved. You can return later.</p></div></section>}
      {run?.state === 'failed' && <div className="error-box" role="alert"><h2>Analysis could not finish</h2><p>Your saved context and evidence remain available. You can retry.</p><button disabled={busy} onClick={() => void retry()}>{busy ? 'Queuing…' : 'Retry analysis'}</button></div>}
      {result && run && <>
        {presentation ? <>
          <p className="results-payment">{money(data.transaction)} · {data.transaction.sender_name} <Status value={data.transaction.status} /></p>
          <VerdictBanner headline={result?.headline} />
          {summary}
          {warning}
          <StoryChain steps={result?.story} />
          {agentViews}
          <section className="panel resolution-actions" aria-label="Private incident report"><div className="section-body">
            <h2>Incident report</h2>
            {run.report_id ? <>
              <p role="status">Private report ready</p>
              <div className="actions">
                <button disabled={busy} onClick={() => void reportAction('download')}>{busy ? 'Downloading…' : 'Download report'}</button>
                <Link to={reportPath}>View report</Link>
              </div>
            </> : <>
              <p>{run.prepare_report ? 'Your assessment is saved. The report could not be prepared.' : 'Prepare a private copy of this assessment and its evidence.'}</p>
              <button disabled={busy} onClick={() => void reportAction('prepare')}>{busy ? 'Preparing report…' : run.prepare_report ? 'Retry report' : 'Prepare private report'}</button>
            </>}
          </div></section>
          {findings.length > 0 && <section className="panel resolution-findings" aria-label="What shaped the assessment">
            <div className="panel-heading"><h2>What shaped the assessment</h2></div>
            <ul>
              {findings.map(finding => <li key={finding.rule_id}>
                <strong>{finding.kind === 'same_destination' ? 'Matching UPI ID' : finding.kind === 'threat' ? 'Threat' : 'Asked to avoid the bank'}</strong>
                {finding.quote && <blockquote>{finding.quote}</blockquote>}
                <p>{finding.kind === 'same_destination' ? 'The requested ID matches the original sender and leaves the risk unchanged.' : finding.text}</p>
                {data.evidence.some(e => e.id === finding.reference && e.review_state === 'confirmed')
                  ? <Link to={evidenceLink(finding.reference)}>Review source evidence</Link> : <small>Source: {finding.source}</small>}
              </li>)}
            </ul>
          </section>}
          <StatusControl id={data.id} value={data} onChange={next => setData(current => current?.id === data.id ? { ...current, case_status: next.case_status, status_revision: next.status_revision } : current)} />
          <p><Link to={screen('/incidents')}>Track case in My Incidents</Link></p>
        </> : <>
          <div className="actions report-actions"><button disabled={busy} onClick={() => void reportAction('prepare')}>{busy ? 'Preparing report…' : 'Generate / view report'}</button><Link to={screen('/incidents')}>Track case in My Incidents</Link></div>
          <VerdictBanner headline={result?.headline} />
          {summary}
          {warning}
          <StoryChain steps={result?.story} />
          {agentViews}
        </>}
        <section className="panel"><div className="panel-heading"><h2>Recommended next steps</h2></div><div className="section-body"><ol>{result.recommendations.map(text => <li key={text}>{text}</li>)}</ol></div></section>
        <section className="panel" aria-label="Findings and sources"><div className="panel-heading"><h2>Findings and sources</h2></div><div className="section-body">{result.findings.map((f, i) => <article className="finding" key={i}><h3>{f.text}</h3><p className="field-help">Source: {f.source}</p>{f.quote && <blockquote>{f.quote}</blockquote>}<p className="finding-reference">Reference: {data.evidence.some(e => e.id === f.reference) ? <Link to={screen(`/investigations/${id}#evidence-${f.reference}`)}>Review source evidence</Link> : f.reference} · Rule: {f.rule_id}</p></article>)}</div></section>
        {result.intelligence_matches.length > 0 && <section className="panel"><div className="panel-heading"><h2>Simulated intelligence matches</h2></div><div className="section-body">{result.intelligence_matches.map((m, i) => <article key={i}><h3>{m.identifier}</h3><p>{m.source_label} · {m.match_type} · {date(m.reported_at)} IST</p><p>{m.incident_reference}: {m.limitations}</p></article>)}</div></section>}
        <section className="panel"><div className="panel-heading"><h2>Unknowns and limitations</h2></div><div className="section-body"><ul>{result.limitations.map(text => <li key={text}>{text}</li>)}</ul></div></section>
      </>}
    </>}
    <p className="footnote">Reports stay in your demo case until you choose to download them. You decide whether to contact your bank or share the report.</p>
  </>;
}
