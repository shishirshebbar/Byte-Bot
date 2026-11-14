import type { CSSProperties, ReactNode } from 'react';
import {
  Check, CircleCheck, CircleX, FileText, Fingerprint, Loader, MessageSquareText, RotateCcw, ShieldCheck, TriangleAlert, UserRound, Wallet,
} from 'lucide-react';
import { Gauge, STATE_LABEL } from '../agent-ui';
import type { ClaimResult, Headline, Investigation, StoryStep } from '../investigation-types';
import { TONE_ICON } from '../story-ui';
import { money } from '../transaction-ui';
import { ProofPanel } from './proof';

/*
 * The presenter's Story Board. It replays what Byte Bot already decided: agents, then the six questions,
 * then the verdict, the proof, and the actions. Remounting on a new run (or Replay) restarts the CSS choreography;
 * with reduced motion everything appears at once. Nothing here changes a category or a decision.
 */

export const STAGES = [
  { id: 'transaction_context', title: 'Transaction Context', icon: Wallet },
  { id: 'message_analysis', title: 'Message Analysis', icon: MessageSquareText },
  { id: 'risk_investigation', title: 'Risk Investigation', icon: Fingerprint },
  { id: 'incident_resolution', title: 'Incident Resolution', icon: FileText },
];
const QUESTIONS = [
  'Did the money actually arrive?', 'What exactly are you being asked to do?', 'Would that send money from your account?',
  'Is there evidence of social engineering?', 'Is there relevant fraud intelligence?', "What's the safest next action?",
];
export const NODE_LABELS: Record<string, string> = {
  transaction_context: 'Transaction Context agent', message_analysis: 'Message Analysis agent',
  risk_investigation: 'Risk Investigation agent', gather_context: 'Ask for missing details',
  plan_actions: 'Plan protective steps', policy_gate: 'Policy check', escalate: 'Hand off to a person',
  incident_resolution: 'Incident Resolution agent',
};
export const OUTCOMES: Record<string, string> = {
  needs_customer_info: 'waiting for customer answers', escalated: 'escalated to a person',
  awaiting_consent: 'waiting for customer consent', actions_ready: 'approved steps running',
  actions_completed: 'steps carried out', resolved: 'resolved without action',
};
const SUMMARY = { queued: 'Analysis queued', running: 'Analysis in progress', complete: 'Analysis complete', failed: 'Analysis failed' };
const LEVEL: Record<string, string> = { 'High concern': 'high', 'Needs verification': 'medium', 'No strong indicators found': 'low', 'Unable to assess': 'neutral' };
const at = (i: number, d = 0): CSSProperties => ({ ['--i' as string]: i, ['--d' as string]: `${d}ms` });

export function StoryBoard({ data, claim, replay, onReplay }: {
  data?: Investigation; claim?: ClaimResult; replay: number; onReplay: () => void;
}) {
  const run = data?.analysis;
  const result = run?.state === 'complete' ? run.result : null;
  const status = claim ? 'Payment claim checked' : run ? SUMMARY[run.state] : data ? 'Case ready for review' : 'Waiting for a case';
  const revealed = !!claim || !!result;
  const key = claim ? `claim-${claim.status}-${claim.matches.length}-${replay}` : result ? `${run!.run_id}-${replay}` : `idle-${run?.state ?? (data ? 'ready' : 'none')}`;
  return <div className="storyboard">
    <div className="sb-head">
      <p className="workflow-summary" role="status">
        <span className={`sb-live ${run && ['queued', 'running'].includes(run.state) ? 'is-busy' : ''}`} aria-hidden="true" />{status}
      </p>
      {revealed && <button type="button" className="sb-replay" onClick={onReplay}><RotateCcw size={14} aria-hidden="true" /> Replay <kbd aria-hidden="true">Space</kbd></button>}
    </div>
    <div className="sb-body" key={key}>
      {claim ? <Revealed story={claim.story} headline={claim.headline} proof={<ProofPanel claim={claim} />}
        meta={<><div><dt>Check</dt><dd>Your own history</dd></div><div><dt>Stored</dt><dd>Nothing</dd></div><div><dt>AI calls</dt><dd>None</dd></div></>}
        footer={<p className="sb-claim-note"><ShieldCheck size={15} aria-hidden="true" /> A stateless check: Byte Bot searched this customer's synthetic history for the claimed credit. No case was opened.</p>} />
        : result && data ? <Revealed story={result.story || []} headline={result.headline} score={result.risk_score ?? null} tone={LEVEL[result.category]}
          meta={<>
            <div><dt>Payment</dt><dd>{money(data.transaction)}</dd></div>
            <div><dt>Python rules</dt><dd>{result.category}</dd></div>
            {run?.duration_seconds != null && <div><dt>Analysed in</dt><dd>{run.duration_seconds.toFixed(1)} s</dd></div>}
          </>}
          proof={<ProofPanel data={data} />}
          below={<Agents data={data} />}
          footer={<Pipeline data={data} />} />
          : <Hook data={data} />}
    </div>
  </div>;
}

function Revealed({ story, headline, score, tone, meta, proof, footer, below }: {
  story: StoryStep[]; headline?: Headline | null; score?: number | null; tone?: string;
  meta: ReactNode; proof: ReactNode; footer: ReactNode; below?: ReactNode;
}) {
  const Icon = headline ? TONE_ICON[headline.tone] : ShieldCheck;
  return <>
    <div className="sb-grid">
      <div className="sb-left">
      <ol className="sb-story" aria-label="Story check">
        {story.map((step, i) => {
          const StepIcon = step.status === 'pass' ? CircleCheck : step.status === 'fail' ? CircleX : TriangleAlert;
          return <li key={step.id} className={`sb-step story-${step.status}`} style={at(i, 250)}>
            <span className="sb-num" aria-hidden="true">{i + 1}</span>
            <div><strong>{step.question}</strong><p title={step.answer}>{step.answer}</p></div>
            <StepIcon className="sb-step-icon" size={20} aria-label={step.status === 'pass' ? 'OK' : step.status === 'fail' ? 'Warning' : 'Check'} />
          </li>;
        })}
      </ol>
      {below}
      </div>
      <div className="sb-right">
        {headline && <section className={`sb-verdict tone-${headline.tone}`} aria-label="Stage verdict" style={at(0, 1900)}>
          <span className="sb-verdict-icon"><Icon size={26} aria-hidden="true" /></span>
          <div className="sb-verdict-text">
            <span className="sb-verdict-label">{headline.label}</span>
            <h3>{headline.title}</h3>
            <p>{headline.message}</p>
          </div>
          {score != null && <div className="sb-gauge"><Gauge value={score} tone={tone || 'neutral'} /></div>}
          <dl className="sb-meta">{meta}</dl>
        </section>}
        <div className="sb-proof" style={at(0, 2300)}>{proof}</div>
      </div>
    </div>
    {footer}
  </>;
}

function Pipeline({ data }: { data: Investigation }) {
  const agent = data.analysis?.agent;
  const actions = (agent?.actions || []).filter(a => a.state !== 'revoked');
  const escalation = data.escalation && data.escalation.state !== 'resolved' ? data.escalation : null;
  return <div className="sb-pipeline">
    {agent && agent.trace.length > 0 && <div className="sb-trace">
      <h3>Supervisor decisions</h3>
      <ol>{agent.trace.map((step, i) => <li key={step.seq} className={`trace-${step.node}`} style={at(i, 150)} title={step.reason}>
        <b>{NODE_LABELS[step.node] || step.node}</b><span>{step.reason}</span>
      </li>)}</ol>
    </div>}
    <div className="sb-actions">
      <h3>Actions on simulated systems{agent?.outcome && <span className="trace-outcome"> · Outcome: {OUTCOMES[agent.outcome]}</span>}</h3>
      <ul>
        {actions.map((action, i) => <li key={action.id} className={`sb-action state-${action.state}`} style={at(i, 2700)}>
          {action.state === 'executed' ? <CircleCheck size={15} aria-hidden="true" /> : action.state === 'awaiting_consent' || action.state === 'awaiting_human' ? <Loader size={15} aria-hidden="true" /> : <TriangleAlert size={15} aria-hidden="true" />}
          <span>{action.label}</span><small>{STATE_LABEL[action.state]}{action.system_reference ? ` · ${action.system_reference}` : ''}</small>
        </li>)}
        {escalation && <li className="sb-action sb-escalation" style={at(actions.length, 2700)}><UserRound size={15} aria-hidden="true" />
          <span>Human support team</span><small>{escalation.priority} priority · reply by {new Date(escalation.sla_due_at).toLocaleTimeString('en-IN', { timeStyle: 'short' })}</small></li>}
        {!actions.length && !escalation && <li className="sb-action sb-none">No action needed on the customer's account.</li>}
      </ul>
    </div>
  </div>;
}

function Agents({ data }: { data?: Investigation }) {
  const run = data?.analysis;
  const current = STAGES.findIndex(stage => stage.id === run?.stage);
  return <ol className="sb-agents" aria-label="Specialist agents">
    {STAGES.map(({ id, title, icon: Icon }, index) => {
      const active = current === index && run?.state === 'running';
      const complete = run?.state === 'complete' || index < current;
      const failed = current === index && run?.state === 'failed';
      const state = complete ? 'Complete' : active ? 'In progress' : failed ? 'Failed' : 'Waiting';
      return <li key={id} className={`sb-agent ${complete ? 'is-done' : active ? 'is-active' : failed ? 'is-failed' : ''}`} style={at(index)} aria-current={active ? 'step' : undefined}>
        <span className="sb-agent-icon"><Icon size={16} aria-hidden="true" /></span>
        <span className="sb-agent-title">{title}</span>
        <span className="sb-agent-state">{complete && <Check size={12} aria-hidden="true" />}{state}</span>
      </li>;
    })}
  </ol>;
}

function Hook({ data }: { data?: Investigation }) {
  const run = data?.analysis;
  const busy = !!run && ['queued', 'running'].includes(run.state);
  return <div className={`sb-hook ${busy ? 'is-busy' : ''}`}>
    <span className="sb-kicker">{data ? `${money(data.transaction)} from ${data.transaction.sender_name} · ${data.transaction.status}` : 'Byte Bot verifies the story behind a suspicious payment'}</span>
    <h2>{busy ? <>Checking the story<span className="sb-dots" aria-hidden="true">…</span></>
      : run?.state === 'failed' ? 'The analysis could not finish. Retry on the phone.'
        : data ? <>The money arrived. <em>Is the story behind it true?</em></>
          : <>You've received ₹5,000. Rahul says it was a mistake. <em>What would you do?</em></>}</h2>
    <ol className="sb-ghost">{QUESTIONS.map((q, i) => <li key={q} style={at(i)}><span>{i + 1}</span>{q}</li>)}</ol>
    {data ? <Agents data={data} /> : <p className="sb-hint">Pick a world below, or tap the alert on the phone. Byte Bot answers six questions before it acts.</p>}
    {data && !run && <p className="sb-hint">On the phone, choose <b>Ask Byte Bot</b>, then <b>Analyze &amp; prepare report</b>.</p>}
  </div>;
}
