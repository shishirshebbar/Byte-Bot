import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, json, request } from './api';
import { useScreenPath } from './screen-path';
import type { Investigation } from './investigation-types';

type Scenario = { id: string; title: string; description: string; evidence_text: string | null };
type Catalog = { extraction_mode: 'fixture' | 'gemini'; scenarios: Scenario[] };

export function DemoControls({ ready, onReset, onLoad, onBusy, sessionRetry }: {
  ready: boolean;
  onReset: () => void;
  onLoad?: (data: Investigation) => void;
  onBusy?: (value: boolean) => void;
  sessionRetry?: () => void;
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
    get<Catalog>('/demo/scenarios', controller.signal).then(value => { if (!controller.signal.aborted) setCatalog(value); }).catch(e => {
      if (!controller.signal.aborted) setError(e.message);
    });
    return () => controller.abort();
  }, [attempt]);
  async function load() {
    setBusy('Loading scenario…'); setError(''); setNotice('');
    onBusy?.(true);
    try {
      const loaded = await json<{ transaction_id: string; investigation: Investigation }>('/demo/scenarios/' + selected + '/load', 'POST', { evidence_mode: manual ? 'manual' : 'text' });
      onLoad?.(loaded.investigation);
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
  const scenario = catalog?.scenarios.find(item => item.id === selected);
  const modeText = catalog?.extraction_mode === 'fixture'
    ? 'Synthetic fixture mode: only exact demo evidence uses predefined extraction. Edited evidence uses the limited local fallback.'
    : 'Gemini mode: evidence uses configured live extraction, with a limited local fallback when unavailable.';
  const loadHelp = 'Loading prepares saved answers and, unless entering manually, synthetic text evidence. Reopening preserves your edits. Choose Ask Byte Bot on the transaction to review and analyze. Reset to replay the original inputs.';
  return <section className="panel demo-controls" aria-label="Demo scenarios">
    <div className="panel-heading"><h2>{onLoad ? 'Presenter controls' : 'Explore a synthetic scenario'}</h2></div>
    <div className="section-body">
      {!catalog ? <>{!error && <p role="status">Loading scenarios…</p>}{error && <button onClick={() => setAttempt(v => v + 1)}>Retry scenarios</button>}</> : <>
        {!onLoad && <p className="field-help">{modeText} Python rules determine every category.</p>}
        <fieldset disabled={!ready || !!busy}>
          <label className="field">Scenario<select aria-label="Scenario" value={selected} onChange={e => setSelected(e.target.value)}>{catalog.scenarios.map(item => <option key={item.id} value={item.id}>{item.id}. {item.title}</option>)}</select></label>
          <p>{scenario?.description}</p>
          {scenario?.evidence_text && <label className="choice"><input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} /> Enter evidence manually (paste or upload a screenshot)</label>}
          {!onLoad && <p className="field-help">{loadHelp}</p>}
          <div className="actions"><button onClick={() => void load()}>Load / reopen scenario</button><button className="secondary" onClick={() => void reset()}>Reset demo</button></div>
        </fieldset>
        {onLoad && <details className="fixture-details"><summary>{catalog.extraction_mode === 'fixture' ? 'Synthetic fixture mode' : 'Gemini extraction mode'}</summary>
          <p className="field-help">{modeText} Python rules determine every category.</p>
          <p className="field-help">{loadHelp}</p>
        </details>}
      </>}
      {sessionRetry && <p role="alert">Could not initialize the demo session. <button className="secondary" onClick={sessionRetry}>Retry session</button></p>}
      {error && <p role="alert">{error}</p>}
      <p role="status" aria-live="polite" className="demo-status">{busy || notice}</p>
    </div>
  </section>;
}
