import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import { get, json, request } from './api';
import { useScreenPath } from './screen-path';
import type { Investigation } from './investigation-types';

type Scenario = { id: string; title: string; description: string; evidence_text: string | null };
type Catalog = { extraction_mode: 'fixture' | 'gemini' | 'sarvam'; scenarios: Scenario[] };

const WORLDS = [
  { label: '1. No credit arrived', short: 'No credit arrived', hint: 'Fake payment claim', key: null },
  { label: '2. Real credit, suspicious request', short: 'Real credit, suspicious request', hint: 'Caution', key: 'M' },
  { label: '3. Real credit, QR "refund"', short: 'Real credit, QR "refund"', hint: 'Money would go out', key: 'N' },
  { label: '4. Same UPI ID, suspicious network', short: 'Same UPI ID, suspicious network', hint: 'Fraud graph', key: 'O' },
] as const;

export function DemoControls({ ready, onReset, onLoad, onBusy, sessionRetry, onMode, onActive }: {
  ready: boolean;
  onReset: () => void;
  onLoad?: (data: Investigation) => void;
  onBusy?: (value: boolean) => void;
  sessionRetry?: () => void;
  onMode?: (mode: string) => void;
  onActive?: (label: string | undefined) => void;
}) {
  const navigate = useNavigate();
  const screen = useScreenPath();
  const [catalog, setCatalog] = useState<Catalog>();
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState('B');
  const [manual, setManual] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    get<Catalog>('/demo/scenarios', controller.signal).then(value => {
      if (controller.signal.aborted) return;
      setCatalog(value);
      onMode?.(value.extraction_mode);
    }).catch(e => {
      if (!controller.signal.aborted) setError(e.message);
    });
    return () => controller.abort();
  }, [attempt]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(''), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  async function load(key = selected, label?: string) {
    setBusy('Loading scenario…'); setError(''); setNotice('');
    onBusy?.(true);
    try {
      const loaded = await json<{ transaction_id: string; investigation: Investigation }>('/demo/scenarios/' + key + '/load', 'POST', { evidence_mode: manual && key === selected ? 'manual' : 'text' });
      onLoad?.(loaded.investigation);
      onActive?.(label ?? `Scenario ${key}`);
      navigate(screen('/transactions/' + loaded.transaction_id));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); onBusy?.(false); }
  }
  async function reset() {
    if (!window.confirm('Reset demo? This clears this browser session’s cases, evidence, results, reports, and statuses, and restores its eight synthetic transactions. Files you already downloaded remain with you.')) return;
    setBusy('Resetting demo…'); setError(''); setNotice('');
    onBusy?.(true);
    try {
      await request('/demo/reset', { method: 'POST' });
      onReset(); setNotice('Demo reset. Your eight synthetic transactions are restored.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); onBusy?.(false); }
  }
  function world(index: number) {
    const item = WORLDS[index];
    const label = `World ${index + 1} · ${item.short}`;
    if (!item.key) { onActive?.(label); navigate('/check-payment?preset=rahul'); return; }
    void load(item.key, label);
  }
  const scenario = catalog?.scenarios.find(item => item.id === selected);
  const modeText = catalog?.extraction_mode === 'fixture'
    ? 'Synthetic fixture mode: only exact demo evidence uses predefined extraction. Edited evidence uses the limited local fallback.'
    : `${catalog?.extraction_mode === 'sarvam' ? 'Sarvam' : 'Gemini'} mode: evidence uses configured live extraction, with a limited local fallback when unavailable.`;
  const loadHelp = 'Loading prepares saved answers and, unless entering manually, synthetic text evidence. Reopening preserves your edits. Choose Ask Byte Bot on the transaction to review and analyze. Reset to replay the original inputs.';
  const feedback = <>
    {sessionRetry && <p role="alert">Could not initialize the demo session. <button className="secondary" onClick={sessionRetry}>Retry session</button></p>}
    {error && <p role="alert">{error}</p>}
    <p role="status" aria-live="polite" className="demo-status">{busy || notice}</p>
  </>;

  if (onLoad) {
    return <section className="demo-controls dock" aria-label="Demo scenarios">
      <h2 className="sr-only">Presenter controls</h2>
      {!catalog ? <div className="dock-loading">{!error && <p role="status">Loading scenarios…</p>}{error && <button onClick={() => setAttempt(v => v + 1)}>Retry scenarios</button>}</div> : <>
        {catalog.scenarios.some(item => item.id === 'N') && <fieldset className="three-worlds" disabled={!ready || !!busy}>
          <legend>Three worlds <span>Rahul says he sent ₹5,000 by mistake</span></legend>
          <div className="world-buttons">
            {WORLDS.map((item, index) => <button key={item.label} type="button" className="world" aria-label={item.label}
              data-shortcut={String(index + 1)} onClick={() => world(index)} title={`${item.hint} (key ${index + 1})`}>
              <kbd aria-hidden="true">{index + 1}</kbd><span aria-hidden="true"><b>{item.short}</b><small>{item.hint}</small></span>
            </button>)}
          </div>
        </fieldset>}
        <fieldset className="dock-row" disabled={!ready || !!busy}>
          <label className="field dock-scenario" title={scenario?.description}>Scenario<select aria-label="Scenario" value={selected} onChange={e => setSelected(e.target.value)}>{catalog.scenarios.map(item => <option key={item.id} value={item.id}>{item.id}. {item.title}</option>)}</select></label>
          <button type="button" className="dock-load" onClick={() => void load()}>Load / reopen scenario</button>
          {scenario?.evidence_text && <label className="choice"><input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} /> Enter evidence manually (paste or upload a screenshot)</label>}
          <button type="button" className="secondary dock-reset" data-shortcut="r" title={`${loadHelp} (key R)`} onClick={() => void reset()}><RotateCcw size={14} aria-hidden="true" />Reset demo</button>
          <span className="dock-keys" aria-hidden="true" title={`${modeText} Keys: 1-4 worlds, Space replay, R reset, F full screen.`}><kbd>1–4</kbd><kbd>Space</kbd><kbd>R</kbd><kbd>F</kbd></span>
        </fieldset>
      </>}
      {feedback}
    </section>;
  }

  return <section className="panel demo-controls" aria-label="Demo scenarios">
    <div className="panel-heading"><h2>Explore a synthetic scenario</h2></div>
    <div className="section-body">
      {!catalog ? <>{!error && <p role="status">Loading scenarios…</p>}{error && <button onClick={() => setAttempt(v => v + 1)}>Retry scenarios</button>}</> : <>
        <p className="field-help">{modeText} Python rules determine every category.</p>
        <fieldset disabled={!ready || !!busy}>
          <label className="field">Scenario<select aria-label="Scenario" value={selected} onChange={e => setSelected(e.target.value)}>{catalog.scenarios.map(item => <option key={item.id} value={item.id}>{item.id}. {item.title}</option>)}</select></label>
          <p>{scenario?.description}</p>
          {scenario?.evidence_text && <label className="choice"><input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} /> Enter evidence manually (paste or upload a screenshot)</label>}
          <p className="field-help">{loadHelp}</p>
          <div className="actions"><button onClick={() => void load()}>Load / reopen scenario</button><button className="secondary" onClick={() => void reset()}>Reset demo</button></div>
        </fieldset>
      </>}
      {feedback}
    </div>
  </section>;
}
