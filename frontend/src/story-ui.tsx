import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, CircleCheck, CircleX, Info, ShieldAlert, ShieldCheck, TriangleAlert } from 'lucide-react';
import { json } from './api';
import type { Headline, StoryStep } from './investigation-types';
import { usePhoneLock } from './presentation-state';
import './teammate.css';

const TONE_ICON = { danger: ShieldAlert, caution: TriangleAlert, safe: ShieldCheck, info: Info } as const;

export function VerdictBanner({ headline }: { headline?: Headline | null }) {
  if (!headline) return null;
  const Icon = TONE_ICON[headline.tone] ?? Info;
  return <section className={`verdict verdict-${headline.tone}`} aria-label={`Verdict: ${headline.label}`}>
    <span className="verdict-icon"><Icon size={22} aria-hidden="true" /></span>
    <div><span className="verdict-label">{headline.label}</span><strong>{headline.title}</strong><p>{headline.message}</p></div>
  </section>;
}

export function StoryChain({ steps }: { steps?: StoryStep[] }) {
  if (!steps?.length) return null;
  return <section className="story-chain" aria-label="How Byte Bot checked the story">
    <h3>How Byte Bot checked the story</h3>
    <ol>{steps.map(step => {
      const Icon = step.status === 'pass' ? CircleCheck : step.status === 'fail' ? CircleX : TriangleAlert;
      const label = step.status === 'pass' ? 'OK' : step.status === 'fail' ? 'Warning' : 'Check';
      return <li key={step.id} className={`story-${step.status}`}>
        <Icon size={18} aria-label={label} /><span><strong>{step.question}</strong><small>{step.answer}</small></span>
      </li>;
    })}</ol>
  </section>;
}

type ClaimResult = {
  status: 'not_found' | 'not_completed' | 'verified' | 'ambiguous' | 'need_amount';
  claimed_amount_paise: number | null;
  matches: { transaction_id: string; amount_paise: number; sender_name: string; sender_vpa: string; status: string; occurred_at: string }[];
  headline: Headline; story: StoryStep[];
};
const PRESETS: Record<string, { text: string; sender: string }> = {
  rahul: { text: 'Hi, I sent you ₹5,000 by mistake. Please return it immediately.', sender: 'Rahul' },
};
const rupees = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(paise / 100);

export function ClaimCheckPage() {
  const [params] = useSearchParams();
  const preset = PRESETS[params.get('preset') || ''];
  const [text, setText] = useState(preset?.text ?? '');
  const [sender, setSender] = useState(preset?.sender ?? '');
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ClaimResult>();
  usePhoneLock(busy);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const rupeesValue = Number(amount.replace(/[,₹\s]/g, ''));
      setResult(await json<ClaimResult>('/claim-check', 'POST', {
        text: text.trim() || null, sender: sender.trim() || null,
        amount_paise: amount.trim() && rupeesValue > 0 ? Math.round(rupeesValue * 100) : null,
      }));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="claim-check">
    <Link className="back" to="/"><ArrowLeft size={18} aria-hidden="true" /> All transactions</Link>
    <h1>Did the money really arrive?</h1>
    <p className="claim-intro">Someone says they paid you and wants it back? Byte Bot checks your Paytm history first. Nothing you type here is saved.</p>
    <form onSubmit={e => void submit(e)}>
      <label className="field">What did they say?<textarea aria-label="What did they say?" rows={3} maxLength={2000} value={text} onChange={e => setText(e.target.value)} placeholder="Hi, I sent you ₹5,000 by mistake…" /></label>
      <div className="claim-row">
        <label className="field">Who says they sent it?<input aria-label="Who says they sent it?" value={sender} maxLength={80} onChange={e => setSender(e.target.value)} placeholder="Name or UPI ID" /></label>
        <label className="field">Amount (optional)<input aria-label="Claimed amount" inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} placeholder="5000" /></label>
      </div>
      <button disabled={busy || (!text.trim() && !amount.trim())}>{busy ? 'Checking…' : 'Check my payments'}</button>
    </form>
    {error && <p role="alert" className="error-box">{error}</p>}
    {result && <div className="claim-result" role="status">
      <VerdictBanner headline={result.headline} />
      {result.matches.length > 0 && <ul className="claim-matches">{result.matches.map(match => <li key={match.transaction_id}>
        <span><strong>{rupees(match.amount_paise)} from {match.sender_name}</strong><small>{match.sender_vpa} · {match.status}</small></span>
        <Link className="button-link" to={`/transactions/${match.transaction_id}`}>Check this payment</Link>
      </li>)}</ul>}
      <StoryChain steps={result.story} />
    </div>}
  </div>;
}
