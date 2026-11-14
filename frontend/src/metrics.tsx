import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CircleCheck, CircleX, ShieldCheck } from 'lucide-react';
import { get } from './api';
import './console.css';

type Row = { scenario: string; title: string; expected_category: string; category: string; outcome: string; expected_escalation: string[];
  escalation: string[]; risk_score: number; customer_taps: number; steps_done: number; awaiting_person: number; analysis_seconds: number; policy_violations: string[] };
type Evaluation = { generated_at: string; extraction_mode: string; scenarios: number; category_accuracy: number; escalation_precision: number | null;
  escalation_recall: number | null; handled_without_person: number; policy_violations: number; injection_contained: boolean;
  median_analysis_seconds: number; median_customer_taps: number; reports_ready: number; rows: Row[] };
type Metrics = { scope: string; cases_analyzed: number; handled_without_person: number; escalated: number; autonomy_rate: number | null;
  median_analysis_seconds: number | null; actions_completed: Record<string, number>; actions_failed: number; policy_violations: number;
  simulated_amount_held_paise: number; feedback: { helpful: number; not_helpful: number }; estimated_review_minutes_saved: number;
  estimate_basis: string; evaluation: Record<string, Evaluation> };

const pct = (value: number | null | undefined) => value == null ? '–' : `${Math.round(value * 100)}%`;
const inr = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100);
const OUTCOME: Record<string, string> = { actions_completed: 'Steps completed', resolved: 'Resolved, no action', escalated: 'Escalated to a person',
  needs_customer_info: 'Asked follow-up questions', awaiting_consent: 'Awaiting consent', actions_ready: 'Steps running' };

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return <article className="stat-tile"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</article>;
}

function Pass({ ok, yes = 'Pass', no = 'Differs' }: { ok: boolean; yes?: string; no?: string }) {
  return <span className={`pass-chip ${ok ? 'ok' : 'bad'}`}>{ok ? <CircleCheck size={14} aria-hidden="true" /> : <CircleX size={14} aria-hidden="true" />}{ok ? yes : no}</span>;
}

export function MetricsPage() {
  const [data, setData] = useState<Metrics>();
  const [error, setError] = useState('');
  const [mode, setMode] = useState('sarvam');
  useEffect(() => {
    const controller = new AbortController();
    const load = () => get<Metrics>('/metrics', controller.signal).then(setData).catch(e => !controller.signal.aborted && setError(e.message));
    void load();
    const timer = setInterval(load, 5000);
    return () => { controller.abort(); clearInterval(timer); };
  }, []);
  const evaluation = data?.evaluation[mode] || data?.evaluation.fixture || data?.evaluation.sarvam;
  const done = data ? Object.values(data.actions_completed).reduce((a, b) => a + b, 0) : 0;
  return <div className="console metrics-page"><main className="console-main">
    <header className="metrics-head"><Link to="/" className="rail-logo" aria-label="Back to the presentation"><ShieldCheck size={22} /></Link>
      <div><h1>Byte Bot outcomes</h1><p className="muted">Measured on synthetic scenarios and local demo sessions. No real customers or payments.</p></div>
      <nav><Link to="/">Presentation</Link> · <Link to="/console">Human console</Link></nav></header>
    {error && <p className="console-error" role="alert">{error}</p>}
    {!data && !error && <p className="muted">Loading metrics…</p>}
    {evaluation && <section aria-label="Scenario evaluation">
      <div className="section-title"><h2>Scenario evaluation · {evaluation.scenarios} end-to-end cases</h2>
        <label className="mode-select">Extraction<select aria-label="Evaluation extraction mode" value={evaluation.extraction_mode} onChange={e => setMode(e.target.value)}>
          {Object.keys(data!.evaluation).map(key => <option key={key} value={key}>{key === 'sarvam' ? 'Live Sarvam AI' : 'Deterministic fixture'}</option>)}
        </select></label></div>
      <div className="stat-grid">
        <Tile label="Handled without a person" value={pct(evaluation.handled_without_person)} note="Escalation only when policy requires it" />
        <Tile label="Escalation precision / recall" value={`${pct(evaluation.escalation_precision)} / ${pct(evaluation.escalation_recall)}`} note="Against expected handoffs" />
        <Tile label="Risk category accuracy" value={pct(evaluation.category_accuracy)} note="Python rules decide the category" />
        <Tile label="Policy violations" value={String(evaluation.policy_violations)} note="Steps taken without the required consent or approval" />
        <Tile label="Median analysis time" value={`${evaluation.median_analysis_seconds}s`} note={evaluation.extraction_mode === 'sarvam' ? 'Live Sarvam extraction' : 'Fixture extraction'} />
        <Tile label="Median customer taps" value={String(evaluation.median_customer_taps)} note="Approve once, then consent per step" />
        <Tile label="Prompt injection" value={evaluation.injection_contained ? 'Contained' : 'Not contained'} note="Category kept, case escalated" />
        <Tile label="Reports prepared" value={`${evaluation.reports_ready}/${evaluation.scenarios}`} note="Private, user-owned downloads" />
      </div>
      <div className="table-wrap"><table className="eval-table">
        <caption>Per-scenario results · run {new Date(evaluation.generated_at).toLocaleString('en-IN')}</caption>
        <thead><tr><th scope="col">Scenario</th><th scope="col">Category</th><th scope="col">Score</th><th scope="col">Byte Bot outcome</th><th scope="col">Handoff reason</th><th scope="col">Taps</th><th scope="col">Steps done</th><th scope="col">Check</th></tr></thead>
        <tbody>{evaluation.rows.map(row => <tr key={row.scenario}>
          <th scope="row">{row.scenario}. {row.title}</th><td>{row.category}</td><td>{row.risk_score}</td><td>{OUTCOME[row.outcome] || row.outcome}</td>
          <td>{row.escalation.join(', ').replace(/_/g, ' ') || '–'}</td><td>{row.customer_taps}</td><td>{row.steps_done}{row.awaiting_person ? ` (+${row.awaiting_person} for a person)` : ''}</td>
          <td><Pass ok={row.category === row.expected_category && row.escalation.join() === row.expected_escalation.join() && row.policy_violations.length === 0} /></td>
        </tr>)}</tbody>
      </table></div>
      <p className="muted">Re-run with <code>backend/tests/eval_teammate.py</code> (add <code>--sarvam</code> for live extraction).</p>
    </section>}
    {data && <section aria-label="Live demo activity">
      <div className="section-title"><h2>Live demo activity</h2><span className="muted">{data.scope}</span></div>
      <div className="stat-grid">
        <Tile label="Cases analyzed" value={String(data.cases_analyzed)} />
        <Tile label="Handled without a person" value={pct(data.autonomy_rate)} note={`${data.escalated} escalated`} />
        <Tile label="Steps completed" value={String(done)} note={Object.entries(data.actions_completed).map(([actor, n]) => `${n} by ${actor === 'agent' ? 'Byte Bot' : actor === 'human' ? 'support agent' : 'customer consent'}`).join(' · ') || 'None yet'} />
        <Tile label="Simulated funds held" value={inr(data.simulated_amount_held_paise)} note="Dispute holds on unexpected credits" />
        <Tile label="Policy violations" value={String(data.policy_violations)} />
        <Tile label="Helpful answers" value={`${data.feedback.helpful} / ${data.feedback.helpful + data.feedback.not_helpful}`} note="From the in-chat question" />
        <Tile label="Review time saved (estimate)" value={`${data.estimated_review_minutes_saved} min`} note={data.estimate_basis} />
        <Tile label="Median analysis time" value={data.median_analysis_seconds == null ? '–' : `${data.median_analysis_seconds}s`} />
      </div>
    </section>}
  </main></div>;
}
