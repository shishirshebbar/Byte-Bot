import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, json, request } from './api';

type Scenario = { id: string; title: string; description: string; evidence_text: string | null };
type Catalog = { extraction_mode: 'fixture' | 'gemini'; scenarios: Scenario[] };

export function DemoControls({ ready, onReset }: { ready: boolean; onReset: () => void }) {
  const navigate = useNavigate();
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
    try {
      const loaded = await json<{ transaction_id: string }>('/demo/scenarios/' + selected + '/load', 'POST', { evidence_mode: manual ? 'manual' : 'text' });
      navigate('/transactions/' + loaded.transaction_id);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function reset() {
    if (!window.confirm('Reset demo? This clears this browser session’s cases, evidence, results, reports, and statuses, and restores its eight synthetic transactions. Files you already downloaded remain with you.')) return;
    setBusy('Resetting demo…'); setError(''); setNotice('');
    try {
      await request('/demo/reset', { method: 'POST' });
      onReset(); setNotice('Demo reset. Your eight synthetic transactions are restored.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(''); }
  }
  const scenario = catalog?.scenarios.find(item => item.id === selected);
  return <section className="panel demo-controls" aria-label="Demo scenarios">
    <div className="panel-heading"><h2>Explore a synthetic scenario</h2></div>
    <div className="section-body">
      {!catalog ? <>{!error && <p role="status">Loading scenarios…</p>}{error && <button onClick={() => setAttempt(v => v + 1)}>Retry scenarios</button>}</> : <>
        <p className="field-help">{catalog.extraction_mode === 'fixture' ? 'Synthetic fixture mode: only exact demo evidence uses predefined extraction. Edited evidence uses the limited local fallback.' : 'Gemini mode: evidence uses configured live extraction, with a limited local fallback when unavailable.'} Python rules determine every category.</p>
        <fieldset disabled={!ready || !!busy}>
          <label className="field">Scenario<select aria-label="Scenario" value={selected} onChange={e => setSelected(e.target.value)}>{catalog.scenarios.map(item => <option key={item.id} value={item.id}>{item.id}. {item.title}</option>)}</select></label>
          <p>{scenario?.description}</p>
          {scenario?.evidence_text && <label className="choice"><input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} /> Enter evidence manually (paste or upload a screenshot)</label>}
          <p className="field-help">Loading prepares saved answers and, unless entering manually, synthetic text evidence. Reopening preserves your edits. Choose Ask Byte Bot on the transaction to review and analyze. Reset to replay the original inputs.</p>
          <div className="actions"><button onClick={() => void load()}>Load / reopen scenario</button><button className="secondary" onClick={() => void reset()}>Reset demo</button></div>
        </fieldset>
      </>}
      {error && <p role="alert">{error}</p>}
      <p role="status" aria-live="polite" className="demo-status">{busy || notice}</p>
    </div>
  </section>;
}
