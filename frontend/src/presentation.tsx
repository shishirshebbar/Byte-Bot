import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3, BatteryFull, Bot, CircleHelp, Headset, LayoutList, ListChecks, ScanLine, ShieldCheck, Signal, Wallet, Wifi,
} from 'lucide-react';
import { DemoControls } from './demo';
import type { ClaimResult, Finding, Investigation } from './investigation-types';
import { STATE_LABEL } from './agent-ui';
import { StoryBoard } from './stage/storyboard';
import './stage/stage.css';
import { PresentationState } from './presentation-state';
import { highlightedFindings } from './findings';
import { money } from './transaction-ui';
import './presentation.css';

const views = ['Workflow', 'Findings', 'Outcome'] as const;
type View = typeof views[number];

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
  const actions = (run?.agent?.actions || []).filter(action => action.state !== 'revoked');
  const escalation = data.escalation && data.escalation.state !== 'resolved' ? data.escalation : null;
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
    {actions.length > 0 && <ul className="outcome-actions">{actions.map(action => <li key={action.id} className={`state-${action.state}`}>
      <strong>{action.label}</strong><span>{STATE_LABEL[action.state]}{action.system_reference ? ` · ${action.system_reference}` : ''}</span>
    </li>)}</ul>}
    {escalation && <p className="outcome-escalation">Escalated to a person · {escalation.priority} priority. <a href="/console" target="_blank" rel="noopener">Open the human console ↗</a></p>}
    <p>The customer downloads the report and records follow-up in the phone.</p>
  </div>;
}

const MODE_LABEL: Record<string, string> = { fixture: 'Fixture mode', sarvam: 'Live Sarvam', gemini: 'Live Gemini' };

export function Presentation({ children, ready, onReset, sessionRetry }: {
  children: ReactNode; ready: boolean; onReset: () => void; sessionRetry?: () => void;
}) {
  const { pathname, hash } = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<Investigation>();
  const [claim, setClaim] = useState<ClaimResult>();
  const [locks, setLocks] = useState<string[]>([]);
  const [presenterBusy, setPresenterBusy] = useState(false);
  const [view, setView] = useState<View>('Workflow');
  const [replay, setReplay] = useState(0);
  const [mode, setMode] = useState<string>();
  const [active, setActive] = useState<string>();
  const phone = useRef<HTMLElement>(null);
  const previousPath = useRef(pathname);
  const actions = useMemo(() => ({
    showCase: setData,
    showStatus: (id: string, status: Pick<Investigation, 'case_status' | 'status_revision'>) =>
      setData(current => current?.id === id ? { ...current, case_status: status.case_status, status_revision: status.status_revision } : current),
    showClaim: setClaim,
    lock: (id: string, locked: boolean) => setLocks(current => locked ? [...current, id] : current.filter(value => value !== id)),
  }), []);
  const target = pathname.split('/');
  const current = pathname === '/incidents' || (target[1] === 'investigations' && target[2] === data?.id) ||
    (target[1] === 'transactions' && target[2] === data?.transaction_id) ? data : undefined;
  const shownClaim = pathname === '/check-payment' ? claim : undefined;
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

  // Presenter shortcuts: 1-4 worlds, R reset, Space replay, F fullscreen. Ignored while typing.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      const element = event.target as HTMLElement | null;
      if (element?.closest('input, textarea, select, [contenteditable="true"]')) return;
      const key = event.key.toLowerCase();
      if (key === ' ') {
        if (element?.closest('button, a, summary, [role="tab"]')) return;
        event.preventDefault();
        setReplay(value => value + 1);
        return;
      }
      if (key === 'f') {
        event.preventDefault();
        if (document.fullscreenElement) void document.exitFullscreen();
        else void document.documentElement.requestFullscreen?.().catch(() => undefined);
        return;
      }
      const button = document.querySelector<HTMLButtonElement>(`[data-shortcut="${key}"]`);
      if (!button) return;
      event.preventDefault();
      if (!button.disabled && !button.closest('fieldset:disabled')) button.click();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const load = useCallback((next: Investigation) => {
    setData(next);
    setView('Workflow');
  }, []);
  function reset() {
    setData(undefined);
    setClaim(undefined);
    setActive(undefined);
    setView('Workflow');
    onReset();
    navigate('/', { replace: true });
  }

  return <div className="presentation">
    <header className="stage-header">
      <Link className="stage-brand" to="/"><span><ShieldCheck size={20} aria-hidden="true" /></span>Byte Bot</Link>
      <a className="jump-controls" href="#presenter-controls">Presenter controls</a>
      <p className="stage-tagline">Verifies the story behind a suspicious payment</p>
      <div className="stage-chips">
        {active && <span className="chip-world">{active}</span>}
        {mode && <span className={`chip-mode mode-${mode}`}><i aria-hidden="true" />{MODE_LABEL[mode] ?? mode}</span>}
        <span className="prototype-label">Paytm hackathon prototype <span aria-hidden="true">·</span> Synthetic data</span>
        <nav className="stage-links" aria-label="Other screens">
          <a href="/metrics" target="_blank" rel="noopener"><BarChart3 size={15} aria-hidden="true" />Metrics</a>
          <a href="/console" target="_blank" rel="noopener"><Headset size={15} aria-hidden="true" />Console</a>
          <Link to="/workspace"><LayoutList size={15} aria-hidden="true" />Workspace</Link>
        </nav>
      </div>
    </header>
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
        <div className="explainer-bar">
          <div className="live-label"><span /> BYTE BOT · LIVE</div>
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
        </div>
        {views.map(item => <section key={item} id={`explain-${item}`} role="tabpanel" aria-labelledby={`explain-tab-${item}`} hidden={item !== view} tabIndex={0} className={`explain-panel explain-${item.toLowerCase()}`}>
          {item === 'Workflow' && <StoryBoard data={current} claim={shownClaim} replay={replay} onReplay={() => setReplay(value => value + 1)} />}
          {item === 'Findings' && <Findings data={current} />}
          {item === 'Outcome' && <Outcome data={current} />}
        </section>)}
        <div id="presenter-controls" tabIndex={-1}>
          <DemoControls ready={ready && !blocked} onLoad={load} onReset={reset} onBusy={setPresenterBusy} sessionRetry={sessionRetry}
            onMode={setMode} onActive={setActive} />
          {blocked && <p className="presenter-lock">Finish the current phone action or save your edits to use the presenter controls.</p>}
        </div>
      </aside>
    </div>
  </div>;
}
