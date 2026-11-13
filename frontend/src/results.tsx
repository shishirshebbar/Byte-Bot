import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { get, json } from './api';
import type { Investigation, Analysis } from './investigation-types';
import { date, money, Status, statusExplanation } from './transaction-ui';

const stages = [
  ['transaction_context', 'Checking transaction context'],
  ['message_analysis', 'Reviewing confirmed evidence'],
  ['risk_investigation', 'Checking simulated intelligence and risk rules'],
  ['incident_resolution', 'Preparing explanations and guidance'],
];
const dangerous = new Set(['credential_request', 'collect_approval', 'remote_access', 'screen_sharing']);

export function ResultsPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [data, setData] = useState<Investigation>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setData(undefined); setError('');
    async function load() {
      try {
        const next = await get<Investigation>(`/investigations/${id}`, abort.signal);
        if (abort.signal.aborted) return;
        setData(next);
        if (next.analysis && ['queued', 'running'].includes(next.analysis.state)) timer = setTimeout(() => void load(), 1000);
      } catch (e) { if (!abort.signal.aborted) setError((e as Error).message); }
    }
    void load();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [id, attempt]);
  async function retry() {
    if (!data) return;
    setBusy(true); setError('');
    try {
      await json<Analysis>(`/investigations/${id}/analyze`, 'POST', { expected_revision: data.input_revision });
      setAttempt(v => v + 1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const run = data?.analysis;
  const result = run?.result;
  return <><Link className="back" to={`/investigations/${id}`}>← Edit saved context and evidence</Link>
    <div className="eyebrow">BYTE BOT · ANALYSIS</div><h1>Investigation results</h1>
    {error && <div role="alert" className="error-box"><p>{error}</p><button onClick={() => setAttempt(v => v + 1)}>Reload saved case</button></div>}
    {!data && !error && <p role="status">Loading saved analysis…</p>}
    {data && <>
      <section className="panel attached" aria-label="Attached transaction"><div className="panel-heading"><h2>{money(data.transaction)} · {data.transaction.sender_name}</h2><Status value={data.transaction.status} /></div><div className="section-body"><p>{statusExplanation(data.transaction)}</p><p>Source: synthetic transaction record · {date(data.transaction.occurred_at)} IST</p></div></section>
      {!run && <div role="status" className="notice"><h2>Analysis needed</h2><p>No current result exists. Saved input may have changed. Review your evidence and analyze the current revision.</p></div>}
      {run && ['queued', 'running'].includes(run.state) && <section className="panel analysis-progress" aria-label="Analysis progress"><div className="panel-heading"><h2>Investigation in progress</h2></div><div className="section-body"><p role="status" aria-live="polite">{run.state === 'queued' ? 'Queued for analysis…' : stages.find(([key]) => key === run.stage)?.[1] || 'Preparing analysis…'}</p><ol>{stages.map(([key, label], index) => <li key={key} aria-current={run.stage === key ? 'step' : undefined}>{index < stages.findIndex(([name]) => name === run.stage) ? '✓ ' : ''}{label}</li>)}</ol><p>Your case is saved. You can return later.</p></div></section>}
      {run?.state === 'failed' && <div className="error-box" role="alert"><h2>Analysis could not finish</h2><p>Your saved context and evidence remain available. You can retry.</p><button disabled={busy} onClick={() => void retry()}>{busy ? 'Queuing…' : 'Retry analysis'}</button></div>}
      {result && <>
        <div className="actions report-actions"><button disabled={busy} onClick={async () => {
          setBusy(true); setError('');
          try { await json(`/investigations/${id}/report`, 'POST', { expected_revision: data.input_revision }); navigate(`/investigations/${id}/report`); }
          catch (e) { setError((e as Error).message); setData(undefined); setAttempt(v => v + 1); }
          finally { setBusy(false); }
        }}>{busy ? 'Preparing report…' : 'Generate / view report'}</button><Link to="/incidents">Track case in My Incidents</Link></div>
        <section className={`panel result-summary ${result.category === 'High concern' ? 'concern' : ''}`} aria-label="Assessment"><div className="section-body"><div className="eyebrow">{result.provider_mode === 'fixture' ? 'SYNTHETIC EXTRACTION FIXTURE' : 'RULE-BASED ASSESSMENT'}</div><h2>{result.category}</h2><p>{result.summary}</p><p className="primary-guidance">{result.recommendations[0]}</p><p className="field-help">Generated {date(result.generated_at)} IST · {result.rule_version} · Evidence extraction: {result.extraction_status}</p></div></section>
        {result.findings.some(f => dangerous.has(f.kind)) && <aside className="guidance safety-warning" role="alert"><h2>Safety warning</h2><p>Never disclose credentials, enable remote access, or approve an unexpected collect request.</p><p>These warnings remain relevant even when the payment is pending or failed.</p></aside>}
        <section className="panel"><div className="panel-heading"><h2>Recommended next steps</h2></div><div className="section-body"><ol>{result.recommendations.map(text => <li key={text}>{text}</li>)}</ol></div></section>
        <section className="panel" aria-label="Findings and sources"><div className="panel-heading"><h2>Findings and sources</h2></div><div className="section-body">{result.findings.map((f, i) => <article className="finding" key={i}><h3>{f.text}</h3><p className="field-help">Source: {f.source}</p>{f.quote && <blockquote>{f.quote}</blockquote>}<p className="finding-reference">Reference: {data.evidence.some(e => e.id === f.reference) ? <Link to={`/investigations/${id}#evidence-${f.reference}`}>Review source evidence</Link> : f.reference} · Rule: {f.rule_id}</p></article>)}</div></section>
        {result.intelligence_matches.length > 0 && <section className="panel"><div className="panel-heading"><h2>Simulated intelligence matches</h2></div><div className="section-body">{result.intelligence_matches.map((m, i) => <article key={i}><h3>{m.identifier}</h3><p>{m.source_label} · {m.match_type} · {date(m.reported_at)} IST</p><p>{m.incident_reference}: {m.limitations}</p></article>)}</div></section>}
        <section className="panel"><div className="panel-heading"><h2>Unknowns and limitations</h2></div><div className="section-body"><ul>{result.limitations.map(text => <li key={text}>{text}</li>)}</ul></div></section>
      </>}
    </>}
    <p className="footnote">This demo provides guidance only. It cannot send money, contact your bank, or submit a report.</p>
  </>;
}
