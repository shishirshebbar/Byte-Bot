import { useContext, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, get, json } from './api';
import { date, money, Status } from './transaction-ui';
import type { Assessment, CaseStatus, Investigation } from './investigation-types';
import type { Transaction } from './api';
import { PresentationState, usePhoneLock } from './presentation-state';
import { useScreenPath } from './screen-path';

export const caseStatuses: CaseStatus[] = ['Open', 'Bank Contacted', 'Reported', 'Awaiting Response', 'Resolved', 'Closed'];
type SavedStatus = { case_status: CaseStatus; status_revision: number };
export type Incident = SavedStatus & { id: string; transaction: Transaction; created_at: string; category: Assessment['category'] | null };

export function StatusControl({ id, value, onChange }: { id: string; value: SavedStatus; onChange: (next: SavedStatus) => void }) {
  const [draft, setDraft] = useState(value.case_status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState('');
  const presentation = useContext(PresentationState);
  usePhoneLock(busy || draft !== value.case_status);
  useEffect(() => { setDraft(value.case_status); }, [value.case_status, value.status_revision]);
  async function save() {
    setBusy(true); setError(''); setNotice('');
    try {
      const next = await json<Incident>(`/incidents/${id}/status`, 'PATCH', { status: draft, expected_status_revision: value.status_revision });
      onChange(next); presentation?.showStatus(id, next); setNotice('Case status saved.');
    } catch (e) { setError((e as Error).message); setConflict(e instanceof ApiError && e.status === 409); }
    finally { setBusy(false); }
  }
  async function reload() {
    setBusy(true); setError('');
    try { const next = await get<Investigation>(`/investigations/${id}`, new AbortController().signal); onChange(next); presentation?.showStatus(id, next); setDraft(next.case_status); setConflict(false); setNotice('Saved case status reloaded.'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="case-status" aria-label="Case follow-up status">
    <p><strong>Saved case status: {value.case_status}</strong></p>
    <p className="field-help">Record actions you took outside Byte Bot. Changing status does not contact a bank or submit a report.</p>
    <div className="actions"><label className="field">Case status<select aria-label="Case status" value={draft} disabled={busy || conflict} onChange={e => setDraft(e.target.value as CaseStatus)}>{caseStatuses.map(s => <option key={s}>{s}</option>)}</select></label>
      <button disabled={busy || conflict || draft === value.case_status} onClick={() => void save()}>{busy ? 'Saving…' : 'Save case status'}</button></div>
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert"><p>{error}</p>{conflict && <button disabled={busy} onClick={() => void reload()}>Reload saved status</button>}</div>}
  </section>;
}

export function IncidentsPage() {
  const screen = useScreenPath();
  const [data, setData] = useState<Incident[]>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setData(undefined); setError('');
    get<{ incidents: Incident[] }>('/incidents', abort.signal).then(next => { if (!abort.signal.aborted) setData(next.incidents); }).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [attempt]);
  return <><div className="eyebrow">BYTE BOT · FOLLOW-UP</div><h1>My Incidents</h1><p className="intro">Your saved investigations and the actions you report taking.</p>
    <Link to={screen('/')}>View transactions</Link>
    {error && <div role="alert" className="error-box"><p>{error}</p><button onClick={() => setAttempt(v => v + 1)}>Reload incidents</button></div>}
    {!data && !error && <p role="status">Loading incidents…</p>}
    {data?.length === 0 && <p className="notice">No investigations yet. Open a transaction and choose Ask Byte Bot.</p>}
    {data?.map(item => <article key={item.id} className="panel incident-card" aria-label={`Incident from ${item.transaction.sender_name}`}>
      <div className="panel-heading"><h2>{money(item.transaction)} · {item.transaction.sender_name}</h2><Status value={item.transaction.status} /></div>
      <div className="section-body"><p>Created {date(item.created_at)} IST</p><p>Current assessment: <strong>{item.category || 'Analysis needed'}</strong></p>
        <StatusControl id={item.id} value={item} onChange={next => setData(items => items?.map(i => i.id === item.id ? { ...i, case_status: next.case_status, status_revision: next.status_revision } : i))} />
        <div className="actions"><Link to={screen(`/investigations/${item.id}`)}>Reopen case</Link><Link to={screen(`/investigations/${item.id}/results`)}>View results</Link>{item.category && <Link to={screen(`/investigations/${item.id}/report`)}>View saved report</Link>}</div>
      </div></article>)}
  </>;
}
