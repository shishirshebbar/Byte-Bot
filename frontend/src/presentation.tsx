import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, ArrowDownLeft, BatteryFull, Bot, ScanLine, Check, ChevronDown, CircleHelp, FileText,
  Fingerprint, ListChecks, MessageSquareText, ShieldCheck, Signal, Wallet, Wifi,
} from 'lucide-react';
import { DemoControls } from './demo';
import type { Finding, Investigation } from './investigation-types';
import { PresentationState } from './presentation-state';
import { highlightedFindings } from './findings';
import { money } from './transaction-ui';
import './presentation.css';

const stages = [
  { id: 'transaction_context', title: 'Transaction Context', icon: Wallet, detail: 'Loads the original payment and checks its recorded status and sender details.' },
  { id: 'message_analysis', title: 'Message Analysis', icon: MessageSquareText, detail: 'Extracts supported claims from confirmed evidence, with a source for each claim.' },
  { id: 'risk_investigation', title: 'Risk Investigation', icon: Fingerprint, detail: 'Compares repayment destinations, checks simulated intelligence, and applies Python risk rules.' },
  { id: 'incident_resolution', title: 'Incident Resolution', icon: FileText, detail: 'Prepares safe next steps and an approved private report. The customer chooses whether to download it and records their own follow-up.' },
];

const views = ['Workflow', 'Findings', 'Outcome'] as const;
type View = typeof views[number];

function Workflow({ data }: { data?: Investigation }) {
  const run = data?.analysis;
  const current = stages.findIndex(stage => stage.id === run?.stage);
  const summary = {
    queued: 'Analysis queued',
    running: 'Analysis in progress',
    complete: 'Analysis complete',
    failed: 'Analysis failed',
  };
  return <>
    <p className="workflow-summary" role="status"><Activity size={15} aria-hidden="true" />
      {run ? summary[run.state] : data ? 'Case ready for review' : 'Waiting for a case'}
    </p>
    <ol className="workflow-steps">
      {stages.map(({ id, title, icon: Icon, detail }, index) => {
        const active = current === index && run?.state === 'running';
        const complete = run?.state === 'complete' || index < current;
        const state = complete ? 'Complete' : active ? 'In progress' : current === index && run?.state === 'failed' ? 'Failed' : 'Waiting';
        return <li key={id}><details aria-current={active ? 'step' : undefined}>
          <summary><span className="step-icon"><Icon size={18} aria-hidden="true" /></span><span>{title}</span>
            <span className={`step-state ${complete ? 'done' : ''}`}>{complete && <Check size={12} aria-hidden="true" />}{state}</span>
            <ChevronDown className="step-chevron" size={15} aria-hidden="true" />
          </summary>
          <p>{detail}</p>
        </details></li>;
      })}
    </ol>
    {run?.agent && run.agent.trace.length > 0 && <div className="agent-trace">
      <h3>Supervisor decisions</h3>
      <ol>{run.agent.trace.map(step => <li key={step.seq} className={`trace-${step.node}`}>
        <span className="trace-node">{NODE_LABELS[step.node] || step.node}</span><span>{step.reason}</span>
      </li>)}</ol>
      {run.agent.outcome && <p className="trace-outcome">Outcome: {OUTCOMES[run.agent.outcome]}{data?.escalation && data.escalation.state !== 'resolved' ? ` · ${data.escalation.priority} priority handoff` : ''}</p>}
    </div>}
  </>;
}

const NODE_LABELS: Record<string, string> = {
  transaction_context: 'Transaction Context agent', message_analysis: 'Message Analysis agent',
  risk_investigation: 'Risk Investigation agent', gather_context: 'Ask for missing details',
  plan_actions: 'Plan protective steps', policy_gate: 'Policy check', escalate: 'Hand off to a person',
  incident_resolution: 'Incident Resolution agent',
};
const OUTCOMES: Record<string, string> = {
  needs_customer_info: 'waiting for customer answers', escalated: 'escalated to a person',
  awaiting_consent: 'waiting for customer consent', actions_ready: 'approved steps running',
  actions_completed: 'steps carried out', resolved: 'resolved without action',
};

function FindingList({ findings, data }: { findings: Finding[]; data: Investigation }) {
  return <ul className="presenter-finding-list">
    {findings.map((finding, index) => <li key={index}>
      <strong>{finding.text}</strong><p>Source: {finding.source} · {finding.rule_id}</p>
      {finding.quote && <blockquote>{finding.quote}</blockquote>}
      {data.evidence.some(item => item.id === finding.reference && item.review_state === 'confirmed') &&
        <Link to={`/investigations/${data.id}#evidence-${finding.reference}`}>Review source evidence</Link>}
    </li>)}
  </ul>;
}

function Findings({ data }: { data?: Investigation }) {
  const result = data?.analysis?.result;
  if (!result) return <p className="explainer-empty">Findings appear after Byte Bot analyzes the saved case.</p>;
  const keyFindings = highlightedFindings(result.findings);
  const otherFindings = result.findings.filter(finding => !keyFindings.includes(finding));
  return <div className="presenter-findings">
    <h3>{result.category}</h3><p>{result.summary}</p>
    <FindingList findings={keyFindings.length ? keyFindings : otherFindings} data={data} />
    {keyFindings.length > 0 && otherFindings.length > 0 && <details>
      <summary>All other findings</summary><FindingList findings={otherFindings} data={data} />
    </details>}
    <details><summary>Limitations and unknowns</summary><ul>
      {result.limitations.map((line, index) => <li key={index}>{line}</li>)}
    </ul></details>
  </div>;
}

function Outcome({ data }: { data?: Investigation }) {
  if (!data) return <p className="explainer-empty">Open a case to see its saved outcomes.</p>;
  const evidence = data.evidence.filter(item => item.review_state === 'confirmed').length;
  const run = data.analysis;
  const reportStatus = run?.report_id ? 'Ready to download' : run?.prepare_report && run.state === 'complete'
    ? 'Report needs retry' : run?.prepare_report && (run.state === 'queued' || run.state === 'running')
      ? 'Approved · awaiting assessment' : 'Awaiting generation';
  return <div className="presenter-outcome">
    <p>{money(data.transaction)} incoming payment</p>
    <dl>
      <div><dt>Confirmed evidence</dt><dd>{evidence} {evidence === 1 ? 'item' : 'items'}</dd></div>
      <div><dt>Incident report</dt><dd>{reportStatus}</dd></div>
      <div><dt>Saved case status</dt><dd>{data.case_status}</dd></div>
    </dl>
    <p>The customer downloads the report and records follow-up in the phone.</p>
  </div>;
}

export function Presentation({ children, ready, onReset, sessionRetry }: {
  children: ReactNode; ready: boolean; onReset: () => void; sessionRetry?: () => void;
}) {
  const { pathname, hash } = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<Investigation>();
  const [locks, setLocks] = useState<string[]>([]);
  const [presenterBusy, setPresenterBusy] = useState(false);
  const [view, setView] = useState<View>('Workflow');
  const phone = useRef<HTMLElement>(null);
  const previousPath = useRef(pathname);
  const actions = useMemo(() => ({
    showCase: setData,
    showStatus: (id: string, status: Pick<Investigation, 'case_status' | 'status_revision'>) =>
      setData(current => current?.id === id ? { ...current, case_status: status.case_status, status_revision: status.status_revision } : current),
    lock: (id: string, locked: boolean) => setLocks(current => locked ? [...current, id] : current.filter(value => value !== id)),
  }), []);
  const target = pathname.split('/');
  const active = pathname === '/incidents' || (target[1] === 'investigations' && target[2] === data?.id) ||
    (target[1] === 'transactions' && target[2] === data?.transaction_id) ? data : undefined;
  const blocked = locks.length > 0;

  useLayoutEffect(() => {
    if (previousPath.current === pathname) return;
    previousPath.current = pathname;
    if (hash.startsWith('#evidence-')) return;
    const scroller = phone.current;
    scroller?.scrollTo({ top: 0 });
    scroller?.focus({ preventScroll: true });
    if (scroller && window.matchMedia('(max-width: 1023px)').matches) scroller.scrollIntoView({ block: 'start' });
  }, [pathname, hash]);

  const load = useCallback((next: Investigation) => {
    setData(next);
    setView('Workflow');
  }, []);
  function reset() {
    setData(undefined);
    setView('Workflow');
    onReset();
    navigate('/', { replace: true });
  }

  return <div className="presentation">
    <div className="stage-header">
      <Link className="stage-brand" to="/"><span><ShieldCheck size={22} aria-hidden="true" /></span>Byte Bot</Link>
      <a className="jump-controls" href="#presenter-controls">Presenter controls</a>
      <span className="prototype-label">Paytm hackathon prototype <span aria-hidden="true">·</span> Synthetic data</span>
    </div>
    <div className="stage-grid">
      <section className="phone-frame" aria-label="Interactive Paytm prototype">
        <div className="phone-screen" inert={presenterBusy}>
          <div className="phone-status" aria-hidden="true"><span>9:41</span><i /><span><Signal size={14} /><Wifi size={14} /><BatteryFull size={19} /></span></div>
          <div className="phone-brand"><Link to="/" aria-label="Paytm prototype home"><b>pay<span>tm</span></b><small>UPI</small></Link><NavLink to="/incidents"><ListChecks size={16} aria-hidden="true" />My Incidents</NavLink></div>
          <main className="phone-content" ref={phone} tabIndex={-1} aria-label="Phone screen">
            <PresentationState.Provider value={actions}>{children}</PresentationState.Provider>
          </main>
          <nav className="phone-nav" aria-label="Phone navigation">
            <NavLink to="/" end><Wallet size={18} aria-hidden="true" />Transactions</NavLink>
            <span className="nav-static" aria-hidden="true"><ScanLine size={18} />Scan</span>
            <NavLink to="/incidents" aria-label="Byte Bot cases"><Bot size={18} aria-hidden="true" />Byte Bot</NavLink>
            <a href="#presenter-controls"><CircleHelp size={18} aria-hidden="true" />Demo controls</a>
          </nav>
          <div className="phone-home" aria-hidden="true" />
        </div>
      </section>
      <aside className="explanation" aria-label="Live investigation explanation">
        <div className="explanation-intro">
          <div className="live-label"><span /> LIVE CASE WORKFLOW</div>
          <h2>When a payment<br className="wide-break" /> feels <em>wrong.</em></h2>
          <p>Follow Byte Bot from transaction review to an evidence-backed assessment, a downloadable report, and customer follow-up.</p>
        </div>
        <div className="explainer-tabs" role="tablist" aria-label="Explanation views">
          {views.map((item, index) => <button key={item} type="button" role="tab" id={`explain-tab-${item}`}
            aria-selected={item === view} tabIndex={item === view ? 0 : -1} aria-controls={`explain-${item}`}
            onClick={() => setView(item)} onKeyDown={event => {
              const destination = { ArrowRight: (index + 1) % views.length, ArrowLeft: (index + views.length - 1) % views.length, Home: 0, End: views.length - 1 }[event.key];
              if (destination === undefined) return;
              event.preventDefault();
              const next = views[destination];
              setView(next);
              document.getElementById(`explain-tab-${next}`)?.focus();
            }}>{item}</button>)}
        </div>
        {views.map(item => <section key={item} id={`explain-${item}`} role="tabpanel" aria-labelledby={`explain-tab-${item}`} hidden={item !== view} tabIndex={0}>
          {item === 'Workflow' && <Workflow data={active} />}
          {item === 'Findings' && <Findings data={active} />}
          {item === 'Outcome' && <Outcome data={active} />}
        </section>)}
        <div id="presenter-controls" tabIndex={-1}>
          <DemoControls ready={ready && !blocked} onLoad={load} onReset={reset} onBusy={setPresenterBusy} sessionRetry={sessionRetry} />
          {blocked && <p className="presenter-lock">Finish the current phone action or save your edits to use the presenter controls.</p>}
        </div>
      </aside>
    </div>
    <div className="stage-footer"><ArrowDownLeft size={14} aria-hidden="true" /> Seeded UPI transactions and simulated intelligence <a href="/metrics" target="_blank" rel="noopener">Outcome metrics</a> <a href="/console" target="_blank" rel="noopener">Open human console</a> <Link to="/workspace">Open standard workspace</Link></div>
  </div>;
}
