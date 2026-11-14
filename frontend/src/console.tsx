import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Bell, Bot, Check, CircleUserRound, LayoutGrid, Link2, ListTodo, Plug, ShieldCheck, Undo2, X } from 'lucide-react';
import { json, request } from './api';
import type { AgentState, Assessment } from './investigation-types';
import { VerdictBanner } from './story-ui';
import './console.css';

const TOAST: [RegExp, string][] = [
  [/decision":"approve/, 'Approved. Byte Bot is carrying out the step on the simulated system.'],
  [/decision":"reject/, 'Rejected. The customer will not see this step run.'],
  [/^\/resolve/, 'Case resolved and recorded in the audit chain.'],
  [/^\/assign/, 'Assigned to you.'], [/^\/notes/, 'Note saved (credentials redacted).'], [/\/undo$/, 'Step undone on the simulated system.'],
];

function AuditChain({ ledger }: { ledger: { verified: boolean; entries: number; head: string | null } }) {
  const blocks = Math.min(ledger.entries, 9);
  return <div className={`audit-chain ${ledger.verified ? 'is-ok' : 'is-broken'}`} title="Every console and agent action is hash-chained per case">
    <span className="chain-label"><Link2 size={14} aria-hidden="true" />Audit chain</span>
    <ol aria-hidden="true">{Array.from({ length: blocks }, (_, i) => <li key={i} style={{ ['--i' as string]: i }} />)}{ledger.entries > blocks && <li className="more">+{ledger.entries - blocks}</li>}</ol>
    <span className="chain-meta">{ledger.entries} linked entries{ledger.head ? ` · head ${ledger.head.slice(0, 10)}…` : ''}</span>
  </div>;
}

type Reason = { code: string; label: string };
type Escalation = { id: string; investigation_id: string; priority: 'urgent' | 'high' | 'normal'; state: 'open' | 'assigned' | 'resolved';
  assignee: string | null; reasons: Reason[]; sla_due_at: string; created_at: string; resolved_at: string | null; source: string };
type QueueItem = Escalation & { amount_paise: number; sender_vpa: string; transaction_status: string; category: string | null; risk_score: number | null; awaiting_human: number };
type Detail = {
  escalation: Escalation; case: { id: string; input_revision: number; case_status: string };
  transaction: { amount_paise: number; sender_name: string; sender_vpa: string; customer_vpa: string; status: string; reference: string; occurred_at: string };
  context: Record<string, unknown>; evidence: { id: string; type: string; text: string }[];
  analysis: { result: Assessment | null; agent: AgentState | null } | null;
  notes: { id: string; text: string; created_at: string; author: string | null }[];
  activity: { action: string; actor: string; created_at: string; metadata: Record<string, string> }[];
  ledger: { verified: boolean; entries: number; legacy_entries: number; head: string | null };
};
type Notice = { action: string; actor: string; created_at: string; escalation_id: string; priority: string; metadata: Record<string, string> };
type Integration = { key: string; name: string; type: string; status: string; detail: string };

const inr = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100);
const ago = (value: string) => {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  return minutes < 1 ? 'just now' : minutes < 60 ? `${minutes}m ago` : `${Math.round(minutes / 60)}h ago`;
};
const due = (value: string) => {
  const minutes = Math.round((new Date(value).getTime() - Date.now()) / 60000);
  return minutes >= 0 ? `SLA ${minutes}m left` : `SLA overdue ${-minutes}m`;
};
const ACTIVITY: Record<string, string> = {
  escalation_opened: 'Case escalated', action_executed: 'Step carried out', action_failed: 'Step failed',
  action_declined: 'Step declined', action_compensated: 'Step undone', escalation_assigned: 'Case assigned',
  escalation_resolved: 'Case resolved', note_added: 'Note added', analysis_completed: 'Assessment published',
  report_generated: 'Report prepared', follow_ups_answered: 'Customer answered questions', context_updated: 'Customer answers saved',
  evidence_submitted: 'Evidence submitted', investigation_created: 'Case opened',
};
const ACTOR: Record<string, string> = { human: 'Support agent', agent: 'Byte Bot', user: 'Customer', system: 'System' };

function insights(detail: Detail) {
  const kinds = new Set(detail.analysis?.result?.findings.map(f => f.kind) || []);
  const has = (...names: string[]) => names.some(name => kinds.has(name));
  return [
    ['Threat detected', has('threat')], ['Bank avoidance', has('bank_avoidance')],
    ['Credential or remote-access request', has('credential_request', 'remote_access', 'screen_sharing', 'collect_approval')],
    ['Different repayment destination', has('destination_mismatch', 'reported_destination_mismatch')],
    ['Simulated intelligence match', has('intel_match')], ['Money already sent', detail.context.already_sent_money === 'yes'],
  ] as [string, boolean][];
}

function CaseView({ id, onChanged }: { id: string; onChanged: () => void }) {
  const [detail, setDetail] = useState<Detail>();
  const [tab, setTab] = useState<'Activity' | 'Notes' | 'Evidence'>('Activity');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3500); return () => clearTimeout(timer); }, [toast]);
  const load = useCallback(() => request<Detail>(`/console/cases/${id}`).then(setDetail).catch(e => setError(e.message)), [id]);
  useEffect(() => { setDetail(undefined); void load(); const timer = setInterval(() => void load(), 4000); return () => clearInterval(timer); }, [load]);
  async function act(path: string, body: unknown = {}) {
    setBusy(true); setError('');
    try {
      setDetail(await json<Detail>(`/console/cases/${id}${path}`, 'POST', body)); onChanged();
      const key = path + ' ' + JSON.stringify(body);
      setToast(TOAST.find(([pattern]) => pattern.test(key) || pattern.test(path))?.[1] ?? 'Saved.');
    }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  if (!detail) return <div className="console-empty">{error || 'Loading case…'}</div>;
  const { escalation: e, transaction: t } = detail;
  const agent = detail.analysis?.agent;
  const result = detail.analysis?.result;
  const pending = agent?.actions.filter(a => a.state === 'awaiting_human') || [];
  const others = agent?.actions.filter(a => a.state !== 'awaiting_human' && a.state !== 'revoked') || [];
  return <div className="case-view">
    <header className="case-header">
      <h1>{inr(t.amount_paise)} repayment request <small>Case {detail.case.id.slice(0, 8)}</small></h1>
      <div className="case-chips">
        <span className={`chip-pill sev-${e.priority}`}>{e.priority} priority</span>
        {result && <span className="chip-pill">{result.category}</span>}
        {result?.risk_score != null && <span className="chip-pill">Risk score {result.risk_score}/100</span>}
        <span className="chip-pill">{e.state === 'resolved' ? 'Resolved' : due(e.sla_due_at)}</span>
        <span className={`chip-pill ${detail.ledger.verified ? 'ledger-ok' : 'sev-urgent'}`} title={`${detail.ledger.entries} hash-chained entries${detail.ledger.head ? ` · head ${detail.ledger.head.slice(0, 12)}…` : ''}`}>
          {detail.ledger.verified ? <><ShieldCheck size={13} aria-hidden="true" /> Ledger verified</> : 'Ledger check failed'}</span>
      </div>
      <div className="case-meta">
        <span><b>Requester</b> {t.sender_vpa}</span><span aria-hidden="true">→</span><span><b>Customer</b> {t.customer_vpa}</span>
        <span><b>Payment</b> {t.status} · {t.reference}</span>
      </div>
    </header>
    {result?.headline && <VerdictBanner headline={result.headline} />}
    <AuditChain ledger={detail.ledger} />
    {error && <p className="console-error" role="alert">{error}</p>}
    {toast && <p className="console-toast" role="status">{toast}</p>}
    <div className="case-grid">
      <section className="console-card" aria-label="Case management">
        <h2>Case management</h2>
        <div className="mgmt-row"><span>Actions</span><div className="mgmt-actions">
          {e.state !== 'resolved' && !e.assignee && <button disabled={busy} onClick={() => void act('/assign')}>Assign to me</button>}
          {e.state !== 'resolved' && <button disabled={busy} className="resolve" onClick={() => void act('/resolve', note.trim() ? { note } : {})}><Check size={15} aria-hidden="true" /> Resolve</button>}
        </div></div>
        <div className="mgmt-row"><span>Status</span><b className={`state-${e.state}`}>{e.state === 'open' ? 'Open' : e.state === 'assigned' ? 'In progress' : 'Resolved'}</b></div>
        <div className="mgmt-row"><span>Analyst</span><b><CircleUserRound size={16} aria-hidden="true" /> {e.assignee || 'Unassigned'}</b></div>
        <h3>Why Byte Bot escalated</h3>
        <ul className="reason-list">{e.reasons.map(r => <li key={r.code}>{r.label}</li>)}</ul>
        <h3>Insights</h3>
        <ul className="insight-list">{insights(detail).map(([label, yes]) => <li key={label}><span>{label}</span><b className={yes ? 'yes' : 'no'}>{yes ? 'Yes' : 'No'}</b></li>)}</ul>
      </section>
      <section className="console-card" aria-label="Steps for approval">
        <h2>Steps for approval</h2>
        {pending.length === 0 && <p className="muted">Nothing is waiting for you.</p>}
        <ul className="approval-list">{pending.map(a => <li key={a.id}>
          <strong>{a.label}</strong><small>{a.system_label}</small><p>{a.reason}</p>
          <div className="mgmt-actions">
            <button disabled={busy} aria-label={`Approve ${a.label}`} onClick={() => void act(`/actions/${a.id}`, { decision: 'approve' })}><Check size={14} aria-hidden="true" /> Approve</button>
            <button disabled={busy} className="ghost" aria-label={`Reject ${a.label}`} onClick={() => void act(`/actions/${a.id}`, { decision: 'reject' })}><X size={14} aria-hidden="true" /> Reject</button>
          </div>
        </li>)}</ul>
        {others.length > 0 && <><h3>Other steps</h3><ul className="step-list">{others.map(a => <li key={a.id}>
          <span className={`dot st-${a.state}`} /><span>{a.label}<small>{a.state.replace('_', ' ')} · by {ACTOR[a.actor === 'customer' ? 'user' : a.actor] || a.actor}{a.system_reference ? ` · ${a.system_reference}` : ''}</small></span>
          {a.state === 'executed' && a.reversible && <button disabled={busy} className="ghost small" aria-label={`Undo ${a.label}`} onClick={() => void act(`/actions/${a.id}/undo`)}><Undo2 size={13} aria-hidden="true" /></button>}
        </li>)}</ul></>}
        {result && <><h3>Assessment</h3><p className="muted">{result.summary}</p></>}
      </section>
    </div>
    <section className="console-card" aria-label="Case timeline">
      <div className="console-tabs" role="tablist">{(['Activity', 'Notes', 'Evidence'] as const).map(name =>
        <button key={name} role="tab" aria-selected={tab === name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>)}</div>
      {tab === 'Activity' && <ol className="timeline">
        {agent?.trace.map(step => <li key={`t${step.seq}`} className="tl-agent"><Bot size={14} aria-hidden="true" /><div><b>{step.node.replace(/_/g, ' ')}</b><p>{step.reason}</p></div></li>)}
        {detail.activity.map((item, index) => <li key={index} className={`tl-${item.actor}`}><span className="tl-dot" /><div>
          <b>{ACTIVITY[item.action] || item.action}</b><p>{ACTOR[item.actor]}{item.metadata.action_type ? ` · ${item.metadata.action_type.replace(/_/g, ' ')}` : ''} · {ago(item.created_at)}</p></div></li>)}
      </ol>}
      {tab === 'Notes' && <div className="notes">
        {detail.notes.map(n => <article key={n.id}><b>{n.author || 'Agent'}</b> <small>{ago(n.created_at)}</small><p>{n.text}</p></article>)}
        <label className="note-field">Add a note<textarea value={note} maxLength={2000} onChange={event => setNote(event.target.value)} placeholder="Credentials are redacted automatically." /></label>
        <button disabled={busy || !note.trim()} onClick={() => void act('/notes', { text: note }).then(() => setNote(''))}>Save note</button>
      </div>}
      {tab === 'Evidence' && <div className="notes">{detail.evidence.length ? detail.evidence.map(item => <article key={item.id}><b>{item.type.replace('_', ' ')}</b><blockquote>{item.text}</blockquote></article>) : <p className="muted">No evidence was shared.</p>}</div>}
    </section>
  </div>;
}

function Integrations() {
  const [items, setItems] = useState<Integration[]>();
  useEffect(() => { void request<{ integrations: Integration[] }>('/console/integrations').then(v => setItems(v.integrations)); }, []);
  return <div className="integrations"><h1>Integrations <small>{items?.length ?? ''}</small></h1>
    <div className="integration-grid">{items?.map(item => <article key={item.key} className="console-card">
      <div className="int-head"><Plug size={16} aria-hidden="true" /><strong>{item.name}</strong><span className={`health h-${item.status}`} title={item.status} /></div>
      <p className="int-type">{item.type}</p><p className="muted">{item.detail}</p><span className="int-status">{item.status}</span>
    </article>)}</div></div>;
}

export function ConsolePage({ view = 'queue' }: { view?: 'queue' | 'integrations' }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<{ name: string }>();
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [feed, setFeed] = useState<Notice[]>([]);
  const [showFeed, setShowFeed] = useState(false);
  const [error, setError] = useState('');
  const refresh = useCallback(() => {
    void request<{ cases: QueueItem[] }>('/console/queue').then(v => setQueue(v.cases)).catch(e => setError(e.message));
    void request<{ notifications: Notice[] }>('/console/notifications').then(v => setFeed(v.notifications)).catch(() => undefined);
  }, []);
  useEffect(() => {
    json<{ agent: { name: string } }>('/console/session', 'POST', {}).then(v => { setAgent(v.agent); refresh(); }).catch(e => setError(e.message));
  }, [refresh]);
  useEffect(() => { if (!agent) return; const timer = setInterval(refresh, 4000); return () => clearInterval(timer); }, [agent, refresh]);
  const active = queue.filter(item => item.state !== 'resolved');
  return <div className="console">
    <nav className="console-rail" aria-label="Console navigation">
      <Link to="/console" className="rail-logo" aria-label="Byte Bot console"><ShieldCheck size={22} /></Link>
      <Link to="/console" aria-label="Escalation queue" className={view === 'queue' ? 'active' : ''}><ListTodo size={20} /></Link>
      <Link to="/console/integrations" aria-label="Integrations" className={view === 'integrations' ? 'active' : ''}><LayoutGrid size={20} /></Link>
      <span className="rail-spacer" />
      <button aria-label="Notifications" aria-expanded={showFeed} className={`rail-bell ${showFeed ? 'active' : ''}`} onClick={() => setShowFeed(v => !v)}><Bell size={20} />{feed.length > 0 && <i>{Math.min(feed.length, 9)}</i>}</button>
      <span className="rail-avatar" title={agent?.name}>{agent?.name.slice(0, 1) || '?'}</span>
    </nav>
    {showFeed && <aside className="console-feed" aria-label="Notifications"><h2>Notifications</h2>
      <ul>{feed.map((n, index) => <li key={index}><button onClick={() => { setShowFeed(false); navigate(`/console/cases/${n.escalation_id}`); }}>
        <b>{ACTIVITY[n.action] || n.action}</b><span>{ACTOR[n.actor]}{n.metadata.action_type ? ` · ${n.metadata.action_type.replace(/_/g, ' ')}` : ''} · {n.priority} priority</span><small>{ago(n.created_at)}</small>
      </button></li>)}</ul></aside>}
    {view === 'integrations' ? <main className="console-main"><Integrations /></main> : <main className="console-main console-split">
      <section className="queue" aria-label="Escalation queue">
        <h1>Escalations <small>{active.length} open</small></h1>
        <p className="muted">Byte Bot hands over only the cases it should not finish alone. Demo console, synthetic data.</p>
        {error && <p className="console-error" role="alert">{error}</p>}
        {queue.length === 0 && <p className="muted">No escalated cases yet. Load Scenario F, H or K in the presentation and analyze it.</p>}
        <ul>{queue.map(item => <li key={item.id}><Link to={`/console/cases/${item.id}`} className={`queue-item ${item.id === id ? 'selected' : ''} ${item.state === 'resolved' ? 'resolved' : ''}`}>
          <span className={`sev-bar sev-${item.priority}`} />
          <span className="q-main"><strong>{inr(item.amount_paise)} · {item.category || 'Not assessed'}{item.risk_score != null ? ` · ${item.risk_score}/100` : ''}</strong>
            <small>{item.reasons.map(r => r.label).join(' ')}</small>
            <span className="q-meta">{item.state === 'resolved' ? 'Resolved' : due(item.sla_due_at)} · {item.assignee || 'Unassigned'}{item.awaiting_human ? ` · ${item.awaiting_human} to approve` : ''}</span></span>
        </Link></li>)}</ul>
      </section>
      <section className="case-pane">{id ? <CaseView id={id} onChanged={refresh} /> : <div className="console-empty">Select an escalation to see Byte Bot’s handoff brief.</div>}</section>
    </main>}
  </div>;
}
