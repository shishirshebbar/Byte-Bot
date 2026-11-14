import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { ArrowRight, CircleCheck, CircleX, QrCode, Search, ShieldAlert, UserRound, Wallet } from 'lucide-react';
import { get, type Transaction } from '../api';
import { FraudGraph } from '../agent-ui';
import type { ClaimResult, Finding, Investigation } from '../investigation-types';
import { money } from '../transaction-ui';

/* Presentation-only proof visuals. Each one re-displays data the API already returned; none of them decides anything. */

const breakable = (value: string) => value.split(/(?<=[.@])/).flatMap((part, i) => i ? [<wbr key={i} />, part] : [part]);
const rupees = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100);
const delay = (i: number): CSSProperties => ({ ['--i' as string]: i });
const OUTGOING = ['qr_payment', 'pin_to_receive', 'collect_approval'];
const PRESSURE: Record<string, string> = {
  urgency: 'Urgency', threat: 'Threat', bank_avoidance: 'Avoid the bank', secrecy: 'Secrecy',
  repayment: 'Repayment ask', vpa: 'UPI ID', amount: 'Amount', credential_request: 'PIN / OTP ask',
  same_destination: 'Same UPI ID', destination_mismatch: 'Different UPI ID',
};

export function ProofPanel({ data, claim }: { data?: Investigation; claim?: ClaimResult }) {
  if (claim) return <LedgerScan claim={claim} />;
  const result = data?.analysis?.result;
  if (!data || !result) return null;
  const outgoing = result.findings.find(f => f.kind === 'qr_payment' && QR_TEXT.test(f.text))
    ?? result.findings.find(f => OUTGOING.includes(f.kind));
  if (outgoing) return <MoneyDirection finding={outgoing} data={data} />;
  if ((result.graph_links || []).length > 0) {
    return <div className="proof proof-graph"><FraudGraph caseId={data.id} variant="stage" senderVpa={data.transaction.sender_vpa} /></div>;
  }
  const quoted = result.findings.filter(f => f.quote && PRESSURE[f.kind]);
  if (quoted.length > 0 && data.evidence.some(e => e.review_state === 'confirmed')) return <MessageXray data={data} findings={quoted} />;
  return <FactorBars data={data} />;
}

/* Case 1: did the claimed credit ever arrive? Scans the owner's own synthetic history. */
function LedgerScan({ claim }: { claim: ClaimResult }) {
  const [rows, setRows] = useState<Transaction[]>();
  useEffect(() => {
    const controller = new AbortController();
    get<{ transactions: Transaction[] }>('/transactions', controller.signal)
      .then(value => setRows(value.transactions)).catch(() => setRows([]));
    return () => controller.abort();
  }, [claim]);
  const matched = new Set(claim.matches.map(m => m.transaction_id));
  const list = useMemo(() => {
    const all = [...(rows || [])].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
    const shown = all.slice(0, 6);
    all.filter(t => matched.has(t.id) && !shown.includes(t)).forEach(t => shown.splice(shown.length - 1, 1, t));
    return shown;
  }, [rows, claim]); // eslint-disable-line react-hooks/exhaustive-deps
  const claimed = claim.claimed_amount_paise ? rupees(claim.claimed_amount_paise) : 'the claimed amount';
  const who = claim.sender ? ` from ${claim.sender}` : '';
  const verdict = {
    not_found: `No credit of ${claimed}${who} in ${rows?.length ?? 'your'} payments`,
    verified: `Found it: ${claimed}${who} really arrived`,
    not_completed: `Found${who}, but the payment never completed`,
    ambiguous: `${claim.matches.length} possible matches: check each one`,
    need_amount: 'Add the amount so Byte Bot can search',
  }[claim.status];
  const good = claim.status === 'verified';
  return <div className={`proof proof-ledger ${good ? 'is-found' : 'is-missing'}`}>
    <h3><Search size={16} aria-hidden="true" /> Searching your Paytm history</h3>
    <div className="ledger-claim"><span>They say</span><b>{claimed}{who}</b></div>
    <ul className="ledger-rows">
      {list.map((t, i) => <li key={t.id} style={delay(i)} className={matched.has(t.id) ? 'is-match' : ''}>
        <span>{t.sender_name}</span><span className="ledger-status">{t.status}</span><b>{money(t)}</b>
      </li>)}
      {!rows && <li className="ledger-loading">Loading history…</li>}
      <i className="ledger-beam" aria-hidden="true" />
    </ul>
    <p className="ledger-verdict">{good ? <CircleCheck size={18} aria-hidden="true" /> : <CircleX size={18} aria-hidden="true" />}{verdict}</p>
    <small className="proof-note">Checked against your own history only. Nothing you typed was saved.</small>
  </div>;
}

/* Case 3: show which way the money would move. */
const QR_TEXT = /payment of (.+?) from your account to (\S+@[\w.-]*\w)( \(the original sender\))?\./;
function MoneyDirection({ finding, data }: { finding: Finding; data: Investigation }) {
  const parsed = finding.kind === 'qr_payment' ? QR_TEXT.exec(finding.text) : null;
  const amount = parsed?.[1] ?? null;
  const payee = parsed?.[2] ?? data.context.requested_vpa ?? (finding.kind === 'collect_approval' ? 'the requester' : 'the person asking');
  const sender = !!parsed?.[3] || payee === data.transaction.sender_vpa;
  const how = { qr_payment: 'Scanning this QR code', pin_to_receive: 'Entering your UPI PIN', collect_approval: 'Approving this collect request' }[finding.kind] ?? 'This step';
  return <div className="proof proof-money">
    <h3><ShieldAlert size={16} aria-hidden="true" /> {how} sends money out</h3>
    <div className="money-flow">
      <div className="mf-node mf-you"><span><Wallet size={22} aria-hidden="true" /></span><b>You</b><small>{data.transaction.receiver_vpa}</small></div>
      <div className="mf-arrow" aria-hidden="true">
        <span className="mf-amount">{amount ?? 'Money'}</span>
        <span className="mf-track"><i /><ArrowRight size={22} /></span>
        <span className="mf-out">leaves your account</span>
      </div>
      <div className="mf-node mf-them"><span><UserRound size={22} aria-hidden="true" /></span><b>{breakable(payee)}</b><small>{sender ? 'the original sender' : 'the person asking'}</small></div>
    </div>
    {finding.kind === 'qr_payment' && <p className="mf-source"><span className="mf-qr"><QrCode size={30} aria-hidden="true" /><i /></span>
      {parsed ? 'Decoded on the server, in memory: the QR is a UPI payment request, not a refund.' : 'The message asks you to scan a QR code to "return" the money.'}</p>}
    <p className="mf-stamp">Receiving money never needs a QR scan, a collect approval, or your PIN.</p>
  </div>;
}

/* Case 2: highlight the pressure inside the message the customer confirmed. */
function MessageXray({ data, findings }: { data: Investigation; findings: Finding[] }) {
  const text = data.evidence.filter(e => e.review_state === 'confirmed').map(e => e.confirmed_text || '').join('\n\n').slice(0, 600);
  const marks: { start: number; end: number; kind: string }[] = [];
  const lower = text.toLowerCase();
  findings.forEach(f => {
    const quote = (f.quote || '').trim();
    const start = quote ? lower.indexOf(quote.toLowerCase()) : -1;
    if (start < 0 || marks.some(m => start < m.end && start + quote.length > m.start)) return;
    marks.push({ start, end: start + quote.length, kind: f.kind });
  });
  marks.sort((a, b) => a.start - b.start);
  const parts: (string | { text: string; kind: string; i: number })[] = [];
  let cursor = 0;
  marks.forEach((m, i) => { parts.push(text.slice(cursor, m.start), { text: text.slice(m.start, m.end), kind: m.kind, i }); cursor = m.end; });
  parts.push(text.slice(cursor));
  const tags = [...new Set(findings.map(f => PRESSURE[f.kind]))];
  const genuine = data.transaction.status === 'successful';
  return <div className="proof proof-xray">
    <h3>Message X-ray</h3>
    <blockquote>{parts.map((part, index) => typeof part === 'string' ? part
      : <mark key={index} className={`mx mx-${part.kind}`} style={delay(part.i)}>{part.text}<small>{PRESSURE[part.kind]}</small></mark>)}</blockquote>
    <ul className="xray-tags">{tags.map((tag, i) => <li key={tag} style={delay(i)}>{tag}</li>)}</ul>
    <div className="xray-checks">
      <span className={genuine ? 'ok' : 'bad'}>{genuine ? <CircleCheck size={16} aria-hidden="true" /> : <CircleX size={16} aria-hidden="true" />}{genuine ? 'The credit is genuine' : `The credit is ${data.transaction.status}`}</span>
      <span className="bad"><CircleX size={16} aria-hidden="true" />The request can't be verified</span>
    </div>
  </div>;
}

/* Fallback: the display-only factors behind the risk score. */
function FactorBars({ data }: { data: Investigation }) {
  const factors = data.analysis?.result?.risk_factors || [];
  if (!factors.length) return <div className="proof proof-clear">
    <CircleCheck size={34} aria-hidden="true" /><h3>No warning signs in what you shared</h3>
    <p>This is not a safety guarantee. Check again if anyone asks for the money back.</p>
  </div>;
  return <div className="proof proof-factors">
    <h3>What moved the risk score</h3>
    <ul>{factors.slice(0, 6).map((f, i) => <li key={f.id} style={delay(i)}>
      <span>{f.label}</span><b>{f.weight ? `+${f.weight}` : '±0'}</b>
      <i style={{ ['--w' as string]: `${Math.min(100, f.weight * 2.5)}%` }} />
    </li>)}</ul>
    <small className="proof-note">Python rules decide the category; the score never changes it.</small>
  </div>;
}
