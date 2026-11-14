import { useEffect, useState, type ReactNode } from 'react';
import { Bot, CircleAlert, CircleCheck, CircleX, Frown, Hand, Receipt, Smile, TriangleAlert, Undo2, UserRound } from 'lucide-react';
import { get, json, request } from './api';
import type { AgentAction, Assessment, FollowUp, Investigation } from './investigation-types';
import { money } from './transaction-ui';
import { usePhoneLock } from './presentation-state';
import './teammate.css';
import { ListenGuidance } from './voice-ui';

const OUTCOME_COPY: Record<string, string> = {
  needs_customer_info: 'I need a little more detail before I can act. Please answer below.',
  escalated: 'I have handed this case to a person on the support team, with everything I found.',
  awaiting_consent: 'I can protect your account right away. Approve the steps you want me to take.',
  actions_ready: 'I am carrying out the approved steps.',
  actions_completed: 'Done. Here is what I did on your behalf.',
  resolved: 'No action is needed. I found no strong warning signs in what you shared.',
};
const STATE_LABEL: Record<AgentAction['state'], string> = {
  approved: 'Approved', awaiting_consent: 'Needs your consent', awaiting_human: 'Waiting for a person',
  denied: 'Not allowed by policy', declined: 'You declined', executed: 'Done', failed: 'Failed, a person will follow up',
  compensated: 'Undone', revoked: 'Cancelled after your case changed',
};

function Bubble({ children }: { children: ReactNode }) {
  return <div className="bot-row"><span className="bot-avatar" aria-hidden="true"><Bot size={16} /></span><div className="bot-bubble">{children}</div></div>;
}

function Questions({ questions, busy, onSubmit }: { questions: FollowUp[]; busy: boolean; onSubmit: (answers: Record<string, unknown>) => void }) {
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const complete = questions.every(q => answers[q.field] !== undefined);
  return <div className="follow-ups">
    {questions.map(q => {
      const value = answers[q.field];
      return <fieldset key={q.id} className="chip-question"><legend>{q.prompt}</legend><div className="chips">
        {q.options.map(option => {
          const selected = q.multi ? Array.isArray(value) && value.includes(option.value) : value === option.value;
          return <button type="button" key={option.value} className={`chip ${selected ? 'selected' : ''}`} aria-pressed={selected}
            onClick={() => setAnswers(current => {
              if (!q.multi) return { ...current, [q.field]: option.value };
              const list = Array.isArray(current[q.field]) ? current[q.field] as string[] : [];
              return { ...current, [q.field]: list.includes(option.value) ? list.filter(v => v !== option.value) : [...list, option.value] };
            })}>{option.label}</button>;
        })}
        {q.multi && <button type="button" className={`chip ${Array.isArray(value) && value.length === 0 ? 'selected' : ''}`}
          aria-pressed={Array.isArray(value) && value.length === 0}
          onClick={() => setAnswers(current => ({ ...current, [q.field]: [] }))}>None of these</button>}
      </div></fieldset>;
    })}
    <button disabled={!complete || busy} onClick={() => onSubmit(answers)}>{busy ? 'Sending…' : 'Send answers'}</button>
  </div>;
}

function ActionCard({ action, busy, onConsent, onUndo }: {
  action: AgentAction; busy: boolean; onConsent: (decision: 'approve' | 'decline') => void; onUndo: () => void;
}) {
  const done = action.state === 'executed';
  return <li className={`action-card state-${action.state}`}>
    <div className="action-head">{done ? <Receipt size={16} aria-hidden="true" /> : <Hand size={16} aria-hidden="true" />}<strong>{action.label}</strong></div>
    <p className="action-state">{STATE_LABEL[action.state]} · {action.system_label}</p>
    {done && action.system_reference && <p className="receipt">Reference <code>{action.system_reference}</code>{action.detail && <> · {action.detail}</>}</p>}
    {!done && <p className="action-reason">{action.reason}</p>}
    {action.state === 'awaiting_consent' && <div className="actions">
      <button disabled={busy} aria-label={`Approve: ${action.label}`} onClick={() => onConsent('approve')}>Approve</button>
      <button disabled={busy} className="secondary" aria-label={`Decline: ${action.label}`} onClick={() => onConsent('decline')}>Decline</button>
    </div>}
    {done && action.reversible && <button disabled={busy} className="link-button" aria-label={`Undo: ${action.label}`} onClick={onUndo}><Undo2 size={14} aria-hidden="true" /> Undo</button>}
  </li>;
}

export function AgentPanel({ data, onChange }: { data: Investigation; onChange: (next: Investigation) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<'up' | 'down'>();
  usePhoneLock(busy);
  const agent = data.analysis?.agent;
  if (!agent?.outcome) return null;
  async function send(path: string, body: unknown) {
    setBusy(true); setError('');
    try { onChange(await json<Investigation>(`/investigations/${data.id}${path}`, 'POST', body)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const revision = { expected_revision: data.input_revision };
  const open = agent.follow_ups.filter(q => q.state === 'open');
  const visible = agent.actions.filter(a => a.state !== 'revoked');
  const escalation = data.escalation && data.escalation.state !== 'resolved' ? data.escalation : null;
  return <section className="agent-chat" aria-label="Byte Bot assistant">
    <p className="chat-privacy">This conversation is saved to your private case. Byte Bot acts only on simulated systems in this demo.</p>
    <Bubble><p>{OUTCOME_COPY[agent.outcome]}</p><ListenGuidance caseId={data.id} /></Bubble>
    {open.length > 0 && <Bubble><Questions questions={open} busy={busy}
      onSubmit={answers => void send('/follow-ups', { answers, ...revision })} /></Bubble>}
    {visible.length > 0 && <Bubble><p>{agent.outcome === 'escalated' ? 'Steps waiting for the support team:' : 'Steps on your account:'}</p>
      <ul className="action-cards">{visible.map(action => <ActionCard key={action.id} action={action} busy={busy}
        onConsent={decision => void send(`/actions/${action.id}/consent`, { decision, ...revision })}
        onUndo={() => void send(`/actions/${action.id}/undo`, revision)} />)}</ul></Bubble>}
    {escalation && <div className="escalation-card" role="status"><UserRound size={18} aria-hidden="true" /><div>
      <strong>Handed to a person · {escalation.priority} priority</strong>
      <ul>{escalation.reasons.map(reason => <li key={reason.code}>{reason.label}</li>)}</ul>
      <small>Expected response by {new Date(escalation.sla_due_at).toLocaleTimeString('en-IN', { timeStyle: 'short' })}</small>
    </div></div>}
    {error && <p role="alert" className="error-box">{error}</p>}
    <div className="chat-footer">
      {!escalation && <button className="secondary" disabled={busy} onClick={() => void send('/escalate', {})}><UserRound size={15} aria-hidden="true" /> Talk to a person</button>}
      <div className="helpful" aria-label="Was this helpful?"><span>Was this helpful?</span>
        <button type="button" className={`icon-button ${feedback === 'up' ? 'selected' : ''}`} aria-pressed={feedback === 'up'} aria-label="Helpful" onClick={() => { setFeedback('up'); void request(`/investigations/${data.id}/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ helpful: true }) }).catch(() => undefined); }}><Smile size={20} /></button>
        <button type="button" className={`icon-button ${feedback === 'down' ? 'selected' : ''}`} aria-pressed={feedback === 'down'} aria-label="Not helpful" onClick={() => { setFeedback('down'); void request(`/investigations/${data.id}/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ helpful: false }) }).catch(() => undefined); }}><Frown size={20} /></button>
      </div>
    </div>
  </section>;
}

const LEVEL: Record<Assessment['category'], number> = { 'High concern': 3, 'Needs verification': 2, 'No strong indicators found': 1, 'Unable to assess': 0 };
type Factor = { id: string; label: string; weight: number; status: string; sources: string[]; detail: string };
type Graph = { nodes: { id: string; kind: string; identifier: string; label: string }[]; edges: { source: string; target: string; relation: string }[]; limitations?: string };

function Gauge({ value, tone }: { value: number; tone: string }) {
  const radius = 44, circumference = 2 * Math.PI * radius, dash = (Math.min(value, 100) / 100) * circumference;
  return <svg className={`gauge tone-${tone}`} viewBox="0 0 110 110" role="img" aria-label={`Risk score ${value} out of 100`}>
    <circle cx="55" cy="55" r={radius} className="gauge-track" />
    <circle cx="55" cy="55" r={radius} className="gauge-value" strokeDasharray={`${dash} ${circumference}`} transform="rotate(-90 55 55)" />
    <text x="55" y="56" className="gauge-number">{value}</text><text x="55" y="73" className="gauge-label">Risk score</text>
  </svg>;
}

export function FraudGraph({ caseId }: { caseId: string }) {
  const [graph, setGraph] = useState<Graph>();
  useEffect(() => {
    const controller = new AbortController();
    get<Graph>(`/investigations/${caseId}/intel-graph`, controller.signal).then(setGraph).catch(() => undefined);
    return () => controller.abort();
  }, [caseId]);
  if (!graph || graph.nodes.length === 0) return null;
  const columns: Record<string, number> = { vpa: 0, account: 0, phone: 1, device: 1, incident: 2 };
  const groups: Record<number, typeof graph.nodes> = { 0: [], 1: [], 2: [], 3: [] };
  // Accounts that received repayments after an incident sit to the right of the incidents.
  const recipients = new Set(graph.edges.filter(edge => edge.relation === 'repaid_to').map(edge => edge.target));
  graph.nodes.forEach(node => groups[recipients.has(node.id) ? 3 : columns[node.kind] ?? 1].push(node));
  const width = groups[3].length ? 445 : 330;
  const height = Math.max(...Object.values(groups).map(group => group.length)) * 62 + 20;
  const position: Record<string, { x: number; y: number }> = {};
  Object.entries(groups).forEach(([column, nodes]) => nodes.forEach((node, index) => {
    position[node.id] = { x: 50 + Number(column) * 115, y: (height / (nodes.length + 1)) * (index + 1) };
  }));
  return <section className="fraud-graph" aria-label="Fraud intelligence graph">
    <h3>Simulated fraud graph</h3>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${graph.nodes.length} linked entities in the simulated fraud graph`}>
      {graph.edges.map(edge => <line key={edge.source + edge.target} x1={position[edge.source].x} y1={position[edge.source].y} x2={position[edge.target].x} y2={position[edge.target].y} className="graph-edge" />)}
      {graph.nodes.map(node => <g key={node.id} className={`graph-node node-${node.kind}`} transform={`translate(${position[node.id].x} ${position[node.id].y})`}>
        <circle r="13" /><text y="27">{node.kind === 'incident' ? node.identifier.replace('SYNTHETIC-INCIDENT-', 'Incident ') : node.identifier}</text>
        <text y="38" className="graph-kind">{node.label}</text>
      </g>)}
    </svg>
    <p className="risk-note">{graph.limitations}</p>
  </section>;
}

export function RiskOverview({ data }: { data: Investigation }) {
  const result = data.analysis?.result;
  if (!result) return null;
  const factors: Factor[] = result.risk_factors || [];
  const level = LEVEL[result.category];
  const tone = ['neutral', 'low', 'medium', 'high'][level];
  const linked = (result.graph_links || []).length > 0;
  return <section className={`risk-overview tone-${tone}`} aria-label="Risk factors">
    <div className="risk-top">
      <Gauge value={result.risk_score ?? 0} tone={tone} />
      <div className="risk-side">
        <span className={`risk-badge tone-${tone}`}>{result.category}</span>
        <dl>
          <div><dt>Amount</dt><dd>{money(data.transaction)}</dd></div>
          <div><dt>Sender</dt><dd>{data.transaction.sender_vpa}</dd></div>
          {data.analysis?.duration_seconds != null && <div><dt>Analysis time</dt><dd>{data.analysis.duration_seconds.toFixed(1)}s</dd></div>}
        </dl>
      </div>
    </div>
    <ul className="risk-factors">
      {factors.map(factor => <li key={factor.id} className={`factor-${factor.status}`}>
        {factor.status === 'fail' ? <CircleX size={18} aria-label="Warning sign" /> : <TriangleAlert size={18} aria-label="Needs verification" />}
        <span><strong>{factor.label}<em className="weight">{factor.weight ? `+${factor.weight}` : '±0'}</em></strong><small>{factor.detail}</small><small>{factor.sources.join(' · ')}</small></span>
      </li>)}
      <li className={data.transaction.status === 'successful' ? 'factor-pass' : 'factor-warn'}>
        {data.transaction.status === 'successful' ? <CircleCheck size={18} aria-label="No issue" /> : <TriangleAlert size={18} aria-label="Needs verification" />}
        <span><strong>Transaction status: {data.transaction.status}</strong><small>synthetic transaction record</small></span></li>
      {!result.intelligence_matches.length && !linked && <li className="factor-pass"><CircleCheck size={18} aria-label="No issue" />
        <span><strong>No link in simulated intelligence</strong><small>This is not a safety guarantee.</small></span></li>}
    </ul>
    <p className="risk-note"><CircleAlert size={14} aria-hidden="true" /> The score summarises supported signals ({result.score_version || 'score-1'}). Python rules decide the category; the score never changes it.</p>
    {linked && <FraudGraph caseId={data.id} />}
  </section>;
}
