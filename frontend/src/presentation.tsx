import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { BatteryFull, Bot, Home, ShieldCheck, Signal, Wallet, Wifi, UserRound } from 'lucide-react';
import { DemoControls } from './demo';
import type { ClaimResult, Investigation } from './investigation-types';
import { JudgeView } from './judge-view';
import { PresentationState } from './presentation-state';
import './presentation.css';
import './simple-presentation.css';

export function Presentation({ children, ready, refreshTransactions, sessionRetry }: {
  children: ReactNode; ready: boolean; refreshTransactions: () => void; sessionRetry?: () => void;
}) {
  const { pathname, hash } = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<Investigation>();
  const [claim, setClaim] = useState<ClaimResult>();
  const [locks, setLocks] = useState<string[]>([]);
  const [presenterBusy, setPresenterBusy] = useState(false);
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
  const current = (target[1] === 'investigations' && target[2] === data?.id) ||
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

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      const element = event.target as HTMLElement | null;
      if (element?.closest('input, textarea, select, button, a, summary, [contenteditable="true"]')) return;
      if (event.key.toLowerCase() !== 'f') return;
      event.preventDefault();
      if (document.fullscreenElement) void document.exitFullscreen();
      else void document.documentElement.requestFullscreen?.().catch(() => undefined);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function load(next: Investigation) {
    setData(next);
    setClaim(undefined);
    refreshTransactions();
  }
  function reset() {
    setData(undefined); setClaim(undefined); setActive(undefined);
    refreshTransactions();
    navigate('/', { replace: true });
  }

  return <div className="presentation simple-presentation">
    <header className="stage-header">
      <Link className="stage-brand" to="/"><span><ShieldCheck size={20} aria-hidden="true" /></span>Byte Bot</Link>
      <a className="jump-controls" href="#judge-panel">Judge view ↓</a>
      <div className="stage-chips"><details className="stage-more"><summary>More</summary><nav aria-label="Other screens"><a href="/metrics" target="_blank" rel="noopener">Evaluation metrics ↗</a><a href="/console" target="_blank" rel="noopener">Human console ↗</a><Link to="/workspace">Full workspace</Link></nav></details></div>
    </header>
    <div className="stage-grid">
      <section className="phone-frame" aria-label="Interactive Paytm prototype">
        <div className="phone-screen" inert={presenterBusy}>
          <div className="phone-status" aria-hidden="true"><span>9:41</span><i /><span><Signal size={14} /><Wifi size={14} /><BatteryFull size={19} /></span></div>
          <div className="phone-brand"><Link to="/" aria-label="Paytm prototype home"><b>pay<span>tm</span></b><small>UPI</small></Link><Link className="phone-profile" to="/incidents" aria-label="Your Byte Bot cases"><UserRound size={20} aria-hidden="true" /></Link></div>
          <main className="phone-content" ref={phone} tabIndex={-1} aria-label="Phone screen"><PresentationState.Provider value={actions}>{children}</PresentationState.Provider></main>
          <nav className="phone-nav" aria-label="Phone navigation">
            <NavLink to="/" end><Home size={20} aria-hidden="true" />Home</NavLink>
            <NavLink to="/history"><Wallet size={20} aria-hidden="true" />History</NavLink>
            <NavLink to="/incidents" aria-label="Byte Bot cases"><Bot size={20} aria-hidden="true" />Byte Bot</NavLink>
          </nav><div className="phone-home" aria-hidden="true" />
        </div>
      </section>
      <aside id="judge-panel" className="explanation" aria-label="Judge backend view">
        <div className="judge-panel-heading"><h1>Backend activity</h1></div>
        <div className="judge-scroll" tabIndex={0} aria-label="Backend activity details"><JudgeView data={current} claim={shownClaim} mode={mode} /></div>
        <details id="presenter-controls" className="judge-setup"><summary>Demo setup <span>{active ?? 'Scenario B selected by default'}</span></summary><DemoControls ready={ready && !blocked} onLoad={load} onReset={reset} onBusy={setPresenterBusy} sessionRetry={sessionRetry} onMode={setMode} onActive={setActive} />{blocked && <p className="presenter-lock">Finish the current phone action or save your edits to change the scenario.</p>}</details>
      </aside>
    </div>
  </div>;
}
