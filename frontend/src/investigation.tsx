import { VoiceNote } from './voice-ui';
import { PhoneContext } from './phone-context';
import { useContext, useEffect, useRef, useState } from 'react';
import { Link, useBlocker, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ApiError, get, json, request } from './api';
import { date, money, Status, statusExplanation } from './transaction-ui';
import { StatusControl } from './incidents';
import { PresentationState, useCaseSnapshot, usePhoneLock } from './presentation-state';
import { useScreenPath } from './screen-path';

import type { Answer, Context, Evidence, Investigation, Analysis } from './investigation-types';
type EvidenceResult = { evidence: Evidence; input_revision: number };
const textOf = (item: Evidence) => item.confirmed_text ?? item.ocr_text ?? '';
const titles = { message: 'Pasted message', call_summary: 'Typed call summary', screenshot: 'Screenshot', voice_note: 'Voice note (Sarvam AI)' };

export function AskByteBot({ transactionId }: { transactionId: string }) {
  const navigate = useNavigate();
  const screen = useScreenPath();
  const presentation = useContext(PresentationState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  usePhoneLock(busy);
  async function open() {
    setBusy(true); setError('');
    try {
      const data = await json<Investigation>('/investigations', 'POST', { transaction_id: transactionId });
      presentation?.showCase(data);
      navigate(screen(`/investigations/${data.id}`));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="ask"><button disabled={busy} onClick={open}>{busy ? 'Opening investigation…' : 'Ask Byte Bot'}</button>{error && <p role="alert">{error}</p>}</div>;
}

function useUnsaved(dirty: boolean) {
  const blocker = useBlocker(dirty);
  useEffect(() => {
    if (blocker.state === 'blocked') {
      if (window.confirm('Leave with unsaved changes?')) blocker.proceed();
      else blocker.reset();
    }
  }, [blocker]);
  useEffect(() => {
    function unload(event: BeforeUnloadEvent) { if (dirty) { event.preventDefault(); event.returnValue = ''; } }
    window.addEventListener('beforeunload', unload);
    return () => window.removeEventListener('beforeunload', unload);
  }, [dirty]);
}

function Choices({ title, value, options, onChange }: { title: string; value: string[] | null; options: [string, string][]; onChange: (next: string[] | null) => void }) {
  return <fieldset><legend>{title}</legend><label className="choice"><input type="checkbox" checked={value === null} onChange={() => onChange(value === null ? [] : null)} /> Not sure / unanswered</label>
    <label className="choice"><input type="checkbox" checked={value !== null && value.length === 0} onChange={() => onChange([])} /> None</label>
    {options.map(([key, label]) => <label className="choice" key={key}><input type="checkbox" checked={value?.includes(key) ?? false} onChange={e => onChange(e.target.checked ? [...(value ?? []), key].sort() : value!.filter(v => v !== key))} /> {label}</label>)}
  </fieldset>;
}

export function InvestigationPage() {
  const { id } = useParams();
  const screen = useScreenPath();
  const showCase = useContext(PresentationState)?.showCase;
  const [data, setData] = useState<Investigation>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setData(undefined); setError('');
    get<Investigation>(`/investigations/${id}`, abort.signal).then(value => { if (!abort.signal.aborted) setData(value); }).catch(e => {
      if (!abort.signal.aborted) { setError(e.message); showCase?.(undefined); }
    });
    return () => abort.abort();
  }, [id, attempt, showCase]);
  if (!data || data.id !== id) return <><h1>Byte Bot investigation</h1>{error ? <div role="alert" className="notice"><h2>Investigation unavailable</h2><p>{error}</p><button onClick={() => setAttempt(v => v + 1)}>Try again</button><p><Link to={screen('/')}>All transactions</Link></p></div> : <p role="status">Loading saved investigation…</p>}</>;
  return <Workspace key={`${data.id}:${attempt}`} initial={data} reload={() => { setData(undefined); setAttempt(v => v + 1); }} />;
}

function Workspace({ initial, reload }: { initial: Investigation; reload: () => void }) {
  const navigate = useNavigate();
  const screen = useScreenPath();
  const presentation = useContext(PresentationState);
  const { hash } = useLocation();
  const [data, setData] = useState(initial);
  const [context, setContext] = useState(initial.context);
  const [attachmentsOpen, setAttachmentsOpen] = useState(false);
  const [attachment, setAttachment] = useState('message');
  const [kind, setKind] = useState<'message' | 'call_summary'>('message');
  const [text, setText] = useState('');
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ url: string; id?: string }>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [failure, setFailure] = useState('');
  const [conflict, setConflict] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const contextDirty = JSON.stringify(context) !== JSON.stringify(data.context);
  const dirty = contextDirty || !!text || !!file || data.evidence.some(e => drafts[e.id] !== undefined && drafts[e.id] !== textOf(e));
  useUnsaved(dirty);
  usePhoneLock(dirty || busy);
  useCaseSnapshot(data);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview?.url]);
  useEffect(() => {
    if (!hash.startsWith('#evidence-')) return;
    const evidence = document.getElementById(hash.slice(1));
    evidence?.focus({ preventScroll: true });
    evidence?.scrollIntoView({ block: 'start' });
  }, [hash, data.id]);
  function update<K extends keyof Context>(key: K, value: Context[K]) { setContext(v => ({ ...v, [key]: value })); }
  async function perform(action: () => Promise<void>, notice: string) {
    setBusy(true); setFailure(''); setMessage('');
    try { await action(); setMessage(notice); return true; }
    catch (e) {
      setFailure((e as Error).message);
      if (e instanceof ApiError && e.status === 409) { setConflict(true); presentation?.showCase(undefined); }
      return false;
    }
    finally { setBusy(false); }
  }
  function apply(result: EvidenceResult) {
    setData(v => ({ ...v, input_revision: result.input_revision,
      analysis: result.input_revision === v.input_revision ? v.analysis : null,
      evidence: v.evidence.some(e => e.id === result.evidence.id) ? v.evidence.map(e => e.id === result.evidence.id ? result.evidence : e) : [...v.evidence, result.evidence],
    }));
    setDrafts(v => { const next = { ...v }; delete next[result.evidence.id]; return next; });
  }
  function chooseFile(next: File | null) {
    setFile(null); setPreview(undefined); setFailure('');
    if (!next) return;
    if (!['image/png', 'image/jpeg'].includes(next.type) || next.size > 5 * 1024 * 1024) { setFailure('Choose a PNG or JPEG up to 5 MiB.'); if (fileInput.current) fileInput.current.value = ''; return; }
    setFile(next); setPreview({ url: URL.createObjectURL(next) });
  }
  const base = `/investigations/${data.id}`;
  const t = data.transaction;
  const awaitingReview = data.evidence.some(e => e.review_state !== 'confirmed');
  const run = data.analysis;
  const viewingRun = run && run.state !== 'failed' && (!presentation || run.prepare_report || run.report_id);
  const resultsPath = screen(`/investigations/${data.id}/results`);
  const needsApproval = !!presentation && !viewingRun && !run?.prepare_report;
  const analyze = <button disabled={busy || conflict || dirty || awaitingReview} onClick={() => void perform(async () => {
    if (!viewingRun) {
      const analysis = await json<Analysis>(`${base}/analyze`, 'POST', {
        expected_revision: data.input_revision, ...(presentation ? { prepare_report: true } : {}),
      });
      presentation?.showCase({ ...data, analysis });
    }
    navigate(resultsPath);
  }, 'Analysis requested.')}>{viewingRun ? run.state === 'complete' ? 'View current result' : 'View analysis progress' :
    presentation ? run?.state === 'complete' ? 'Prepare private report' : run?.prepare_report ? 'Retry analysis' : 'Analyze & prepare report' :
    'Analyze saved information'}</button>;
  const statusControl = <StatusControl id={data.id} value={data} onChange={next => setData(v => ({ ...v, case_status: next.case_status, status_revision: next.status_revision }))} />;
  return <><Link className="back" to={screen(`/transactions/${t.id}`)}>← Transaction details</Link><div className="eyebrow">BYTE BOT</div><h1>{presentation ? "Check this payment" : "Let’s understand what happened"}</h1><p className="intro">{presentation ? "Tell Byte Bot what happened. You choose what to share." : "Save your answers and voluntarily share the evidence you want to review."}</p>
    {!presentation && statusControl}
    {presentation && <section className="panel quick-review" aria-label="Case review">
      <div className="section-body">
        <h2>Review before analysis</h2>
        <p>{data.context.expected_payment === 'no' ? 'Unexpected credit' : 'Payment context saved'} · {data.evidence.filter(e => e.review_state === 'confirmed').length} confirmed evidence</p>

        <a href="#phone-case-inputs" onClick={event => {
          event.preventDefault();
          const inputs = document.getElementById('phone-case-inputs');
          inputs?.focus({ preventScroll: true });
          inputs?.scrollIntoView({ block: 'start' });
        }}>Review answers and evidence</a>
        {dirty && <p>Save edits before analyzing.</p>}
        {awaitingReview && <p>Confirm or remove each screenshot before analyzing.</p>}
        {needsApproval && <p className="field-help">Byte Bot uses your saved answers and confirmed evidence to prepare a private report in this case. You choose whether to download or share it.</p>}
        {analyze}
      </div>
    </section>}
    <section className="panel attached" aria-label="Attached transaction"><div className="panel-heading"><h2>{money(t)} · {t.sender_name}</h2><Status value={t.status} /></div><div className="section-body"><p>{statusExplanation(t)}</p><p>{t.sender_vpa} · {date(t.occurred_at)} IST</p>{!presentation && <p>Reference: {t.reference} · Source: synthetic demo transaction</p>}</div></section>
    <aside className="guidance">{presentation ? "Never share your UPI PIN or OTP. Verify unexpected repayment requests using your bank's official contact details. This demo cannot move money." : "Never share your UPI PIN, OTP, password, or CVV. Do not make a separate repayment because of pressure. Verify the original credit with your bank using its official contact details. This demo cannot move money."}</aside>
    <div role="status" aria-live="polite" className="save-status">{busy ? 'Saving or reading screenshot…' : message || (presentation ? "Your case is saved" : `Saved case · revision ${data.input_revision}`)}</div>
    {failure && <div role="alert" className="error-box"><p>{failure}</p>{conflict && <button onClick={() => { if (!dirty || window.confirm('Reload and discard unsaved changes?')) reload(); }}>Reload saved case</button>}</div>}
    <div id={presentation ? 'phone-case-inputs' : undefined} tabIndex={presentation ? -1 : undefined}>
    {presentation ? <PhoneContext value={context} dirty={contextDirty} disabled={busy || conflict} onChange={setContext}
      onSave={() => perform(async () => { const next = await json<Investigation>(`${base}/context`, 'PATCH', { ...context, expected_revision: data.input_revision }); setData(next); setContext(next.context); }, 'Answers saved.')} /> : (
    <form className="panel intake" onSubmit={e => { e.preventDefault(); void perform(async () => { const next = await json<Investigation>(`${base}/context`, 'PATCH', { ...context, expected_revision: data.input_revision }); setData(next); setContext(next.context); }, 'Answers saved.'); }}>
      <div className="panel-heading"><h2>1. Tell us the context</h2><span>User-provided answers</span></div><fieldset disabled={busy || conflict} className="form-body">
      {([['expected_payment', 'Were you expecting this payment?'], ['knows_sender', 'Do you know the sender?'], ['repayment_requested', 'Has anyone asked you to return the money?'], ['already_sent_money', 'Have you already sent money in response?']] as [keyof Pick<Context, 'expected_payment' | 'knows_sender' | 'repayment_requested' | 'already_sent_money'>, string][]).map(([key, label]) => <label className="field" key={key}>{label}<select aria-label={label} value={context[key]} onChange={e => update(key, e.target.value as Answer)}><option value="unknown">Not sure / unanswered</option><option value="yes">Yes</option><option value="no">No</option></select></label>)}
      <Choices title="How did they contact you?" value={context.contact_channels} options={[[ 'call', 'Phone call'], ['whatsapp', 'WhatsApp'], ['sms', 'SMS'], ['paytm_request', 'Paytm / in-app request'], ['other', 'Other']]} onChange={v => update('contact_channels', v)} />
      <label className="field">Where did they ask you to send money?<select aria-label="Where did they ask you to send money?" value={context.requested_destination_type} onChange={e => update('requested_destination_type', e.target.value)}>{[['unknown', 'Not sure / unanswered'], ['same_sender', 'Same sender'], ['different_vpa', 'Different UPI ID'], ['bank_account', 'Bank account'], ['payment_request', 'Payment request'], ['not_specified', 'Not specified']].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label className="field">Requested UPI ID<input maxLength={256} value={context.requested_vpa ?? ''} onChange={e => update('requested_vpa', e.target.value || null)} /></label>
      <p className="field-help">A matching UPI ID does not establish that a repayment request is safe.</p>
      <Choices title="Did they use pressure or isolation tactics?" value={context.pressure_tactics} options={[[ 'urgency', 'Urgent response'], ['threat', 'Threats'], ['bank_avoidance', 'Do not contact your bank'], ['secrecy', 'Keep it secret']]} onChange={v => update('pressure_tactics', v)} />
      <button type="submit" disabled={!contextDirty}>Save answers</button>{contextDirty && <span className="field-help"> Unsaved answers</span>}
      </fieldset></form>)}

    <section className="panel evidence-section"><div className="panel-heading"><h2>{presentation ? 'Share a message or attachment' : '2. Add evidence'}</h2>{presentation && <button className="link-button" aria-expanded={attachmentsOpen} onClick={() => setAttachmentsOpen(v => !v)}>{attachmentsOpen ? 'Close' : 'Add evidence'}</button>}</div><div className="section-body" hidden={!!presentation && !attachmentsOpen}>
      {presentation && <div className="attachment-menu" role="group" aria-label="Attachment type">{[['message', 'Message'], ['call_summary', 'Call summary'], ['screenshot', 'Screenshot'], ['voice_note', 'Voice note']].map(([key, label]) => <button type="button" className="chip" key={key} aria-pressed={attachment === key} onClick={() => { setAttachment(key); if (key === 'message' || key === 'call_summary') setKind(key); }}>{label}</button>)}</div>}<p className="field-help">Only submit text or images you choose to share. Calls are described by you; no calls or messages are accessed automatically. Credential-labelled passages may be removed; review the saved text. Redacted text stays in this demo until you remove it. Images are processed transiently and are never saved on the server.</p>
      <form hidden={!!presentation && !["message", "call_summary"].includes(attachment)} onSubmit={e => { e.preventDefault(); void perform(async () => { apply(await json<EvidenceResult>(`${base}/evidence`, 'POST', { type: kind, text, expected_revision: data.input_revision })); setText(''); }, 'Evidence saved with credential values redacted.'); }}><fieldset disabled={busy || conflict}>
      <label className="field" hidden={!!presentation}>Evidence type<select aria-label="Evidence type" value={kind} onChange={e => setKind(e.target.value as typeof kind)}><option value="message">Pasted message</option><option value="call_summary">Typed call summary</option></select></label>
      <label className="field">{kind === 'message' ? 'Message text' : 'What did the caller say?'}<textarea aria-label={kind === 'message' ? 'Message text' : 'What did the caller say?'} required maxLength={10000} rows={4} value={text} onChange={e => setText(e.target.value)} /></label><button disabled={!text.trim()}>Save text evidence</button></fieldset></form>
      <div className="upload" hidden={!!presentation && attachment !== "screenshot"}><label className="field">Screenshot (PNG or JPEG, up to 5 MiB and 16 megapixels)<input ref={fileInput} disabled={busy || conflict} type="file" accept="image/png,image/jpeg" onChange={e => chooseFile(e.target.files?.[0] ?? null)} /></label>
      {preview && <div className="preview"><img src={preview.url} alt="Browser-local screenshot preview" /><button type="button" className="secondary" onClick={() => { setFile(null); setPreview(undefined); if (fileInput.current) fileInput.current.value = ''; }}>Close preview</button></div>}
      <button disabled={!file || busy || conflict} onClick={() => void perform(async () => { const form = new FormData(); form.append('file', file!); form.append('expected_revision', String(data.input_revision)); const result = await request<EvidenceResult>(`${base}/evidence`, { method: 'POST', body: form }); apply(result); setFile(null); setPreview(p => p && { ...p, id: result.evidence.id }); if (fileInput.current) fileInput.current.value = ''; }, 'Screenshot processed. Review and confirm its text.')}>Upload and read screenshot</button>
      <p className="field-help">To replace a screenshot, upload a new one and remove the previous item.</p></div>
      <div className="upload" hidden={!!presentation && attachment !== "voice_note"}><VoiceNote base={base} revision={data.input_revision} disabled={busy || conflict} onDone={result => { apply(result); setMessage('Voice note transcribed. Review and confirm its text.'); }} /></div>
    </div></section>
    <section className="panel evidence-section" aria-label="Saved evidence"><div className="panel-heading"><h2>{presentation ? "Shared evidence" : "3. Review saved evidence"}</h2><span>{data.evidence.length} / 20 items</span></div><div className="section-body">
      {data.evidence.length === 0 && <p>No evidence added. Your saved answers remain available.</p>}
      {data.evidence.map(item => <article className="evidence-item" id={`evidence-${item.id}`} tabIndex={-1} key={item.id}><h3>{titles[item.type]}</h3><p className="field-help">Source: {item.type === 'screenshot' ? 'local OCR, reviewed by you when confirmed' : item.type === 'voice_note' ? 'Sarvam speech-to-text and translation, reviewed by you when confirmed' : 'user statement'} · {item.review_state === 'confirmed' ? 'Confirmed' : 'Awaiting your review'}</p>
        {item.notice && <p role="status" className="guidance">{item.notice === 'unreadable' ? 'No readable text was found.' : 'OCR is unavailable.'} Type or paste the message below, then confirm it. Your investigation is saved.</p>}
        {item.review_state !== 'confirmed' && <p className="field-help">This screenshot is excluded from future analysis until you confirm its text.</p>}
        {presentation && item.review_state === 'confirmed' && <blockquote className="evidence-preview">{textOf(item)}</blockquote>}
        <details className="evidence-editor" open={!presentation || item.review_state !== 'confirmed' || hash === `#evidence-${item.id}` ? true : undefined}>
          <summary hidden={!presentation}>{item.review_state === 'confirmed' ? 'Edit or remove evidence' : 'Review and confirm text'}</summary>
        <label className="field">{item.type === 'screenshot' ? 'Review screenshot text' : 'Review evidence text'}<textarea aria-label={item.type === 'screenshot' ? 'Review screenshot text' : 'Review evidence text'} maxLength={10000} rows={4} value={drafts[item.id] ?? textOf(item)} disabled={busy || conflict} onChange={e => setDrafts(v => ({ ...v, [item.id]: e.target.value }))} /></label>
        <div className="actions"><button disabled={busy || conflict || !(drafts[item.id] ?? textOf(item)).trim()} onClick={() => void perform(async () => { apply(await json<EvidenceResult>(`${base}/evidence/${item.id}`, 'PATCH', { text: drafts[item.id] ?? textOf(item), confirmed: true, expected_revision: data.input_revision })); }, 'Reviewed text confirmed and saved.')}>{item.review_state === 'confirmed' ? 'Save corrected text' : 'Confirm reviewed text'}</button>
        <button className="secondary" disabled={busy || conflict} onClick={() => void perform(async () => { await request<void>(`${base}/evidence/${item.id}?expected_revision=${data.input_revision}`, { method: 'DELETE' }); setData(v => ({ ...v, input_revision: v.input_revision + 1, analysis: null, evidence: v.evidence.filter(e => e.id !== item.id) })); setDrafts(v => { const next = { ...v }; delete next[item.id]; return next; }); if (preview?.id === item.id) setPreview(undefined); }, 'Evidence removed from this case.')}>Remove evidence</button></div></details></article>)}
    </div></section>
    {!presentation && <section className="panel"><div className="panel-heading"><h2>4. Analyze saved information</h2></div><div className="section-body">
      <p>Analysis uses saved answers and confirmed evidence. It does not verify the identity of the sender.</p>
      {dirty && <p role="status">Save or discard your unsaved edits before analyzing.</p>}
      {awaitingReview && <p role="status">Confirm or remove every screenshot before analyzing.</p>}
      {analyze}
    </div></section>}
    </div>
    </>;
}
