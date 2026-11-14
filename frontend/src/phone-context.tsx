import { useState } from 'react';
import type { Context } from './investigation-types';

const QUESTIONS = [
  ['expected_payment', 'Were you expecting this payment?'],
  ['knows_sender', 'Do you know the sender?'],
  ['repayment_requested', 'Has anyone asked you to return the money?'],
  ['already_sent_money', 'Have you already sent money in response?'],
] as const;
const CHANNELS = [['call', 'Phone call'], ['whatsapp', 'WhatsApp'], ['sms', 'SMS'], ['paytm_request', 'In-app request'], ['other', 'Other']];
const DESTINATIONS = [['unknown', 'Not sure'], ['same_sender', 'Same sender'], ['different_vpa', 'Different UPI ID'], ['bank_account', 'Bank account'], ['payment_request', 'Payment request'], ['not_specified', 'Not specified']];
const PRESSURE = [['urgency', 'Urgent response'], ['threat', 'Threats'], ['bank_avoidance', 'Avoid the bank'], ['secrecy', 'Keep it secret']];

export function PhoneContext({ value, dirty, disabled, onChange, onSave }: {
  value: Context; dirty: boolean; disabled: boolean; onChange: (next: Context) => void; onSave: () => Promise<boolean>;
}) {
  const [step, setStep] = useState<number | null>(QUESTIONS.every(([field]) => value[field] === 'unknown') ? 0 : null);
  const update = (field: keyof Context, next: Context[keyof Context]) => onChange({ ...value, [field]: next });
  const multi = (field: 'contact_channels' | 'pressure_tactics', options: string[][]) => <div className="reply-chips">
    {options.map(([key, label]) => <button type="button" className="chip" aria-pressed={value[field]?.includes(key) ?? false} key={key} onClick={() => update(field, value[field]?.includes(key) ? value[field]!.filter(v => v !== key) : [...(value[field] ?? []), key])}>{label}</button>)}
    <button type="button" className="chip" aria-pressed={value[field]?.length === 0} onClick={() => update(field, [])}>None</button>
    <button type="button" className="chip" aria-pressed={value[field] === null} onClick={() => update(field, null)}>Not sure</button>
  </div>;
  return <section className="phone-questions" aria-label="Payment context">
    {step === null ? <><div className="home-section-title"><h2>Your answers</h2><button className="link-button" disabled={disabled} onClick={() => setStep(0)}>Review or edit answers</button></div>
      <p>{value.expected_payment === 'no' ? 'Unexpected payment' : value.expected_payment === 'yes' ? 'Expected payment' : 'Payment expectation unknown'} · {value.repayment_requested === 'yes' ? 'Return requested' : value.repayment_requested === 'no' ? 'No return requested' : 'Return request unknown'}</p>
      <small>You can leave anything you don't know as “Not sure”.</small></> : <fieldset disabled={disabled}>
      <small>Question {step + 1} of 7</small>
      <h2>{step < 4 ? QUESTIONS[step][1] : step === 4 ? 'How did they contact you?' : step === 5 ? 'Where did they ask you to send money?' : 'Did they pressure you?'}</h2>
      {step < 4 ? <div className="reply-chips">{[['yes', 'Yes'], ['no', 'No'], ['unknown', 'Not sure']].map(([key, label]) => <button className="chip" type="button" key={key} aria-pressed={value[QUESTIONS[step][0]] === key} onClick={() => update(QUESTIONS[step][0], key)}>{label}</button>)}</div>
        : step === 4 ? multi('contact_channels', CHANNELS) : step === 5 ? <><div className="reply-chips">{DESTINATIONS.map(([key, label]) => <button type="button" className="chip" key={key} aria-pressed={value.requested_destination_type === key} onClick={() => update('requested_destination_type', key)}>{label}</button>)}</div><label className="field">Requested UPI ID<input maxLength={256} value={value.requested_vpa ?? ''} onChange={e => update('requested_vpa', e.target.value || null)} /></label><small>A matching UPI ID does not make a repayment safe.</small></> : multi('pressure_tactics', PRESSURE)}
      <div className="question-navigation"><button className="secondary" type="button" onClick={() => setStep(step === 0 ? null : step - 1)}>{step === 0 ? 'Close' : 'Back'}</button>
        {step < 6 ? <button type="button" onClick={() => setStep(step + 1)}>Next</button> : <button type="button" onClick={async () => { if (await onSave()) setStep(null); }}>Save answers</button>}</div>
    </fieldset>}
    {dirty && <p role="status">Unsaved answers · save before checking this payment.</p>}
    {step === null && dirty && <button disabled={disabled} onClick={() => void onSave()}>Save answers</button>}
  </section>;
}
