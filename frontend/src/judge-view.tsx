import { Link } from 'react-router-dom';
import { Activity, Bot, CheckCircle2, Clock3 } from 'lucide-react';
import type { ClaimResult, Investigation } from './investigation-types';
import { FraudGraph, Gauge, STATE_LABEL } from './agent-ui';
import { NODE_LABELS, OUTCOMES, STAGES } from './stage/storyboard';
import { money, date } from './transaction-ui';
import { highlightedFindings } from './findings';

const SIGNAL_LABELS: Record<string, string> = { same_destination: 'Same UPI ID · zero risk reduction', destination_mismatch: 'Different repayment destination', threat: 'Threats', bank_avoidance: 'Asked to avoid the bank' };
const TASKS: Record<string, { title: string; detail: string }> = {
  transaction_context: { title: 'Verify the original payment', detail: 'Read the saved payment status, amount and sender. Separate completed credits from pending or failed payments.' },
  message_analysis: { title: 'Review the customer’s evidence', detail: 'Extract repayment requests, destinations and pressure tactics from confirmed, redacted evidence.' },
  risk_investigation: { title: 'Check risk and fraud intelligence', detail: 'Compare payment destinations, check simulated intelligence and apply the Python risk rules.' },
  gather_context: { title: 'Check for missing information', detail: 'Identify unanswered questions that could change the decision or require a human handoff.' },
  plan_actions: { title: 'Plan protective steps', detail: 'Choose relevant protective actions from the fixed playbook.' },
  policy_gate: { title: 'Check permissions before acting', detail: 'Decide which steps may run automatically and which need customer consent or human approval.' },
  escalate: { title: 'Prepare the human handoff', detail: 'Package the case findings, escalation reason and pending approvals for the support team.' },
  incident_resolution: { title: 'Prepare guidance and the report', detail: 'Assemble the sourced assessment, safe next steps and any approved private report.' },
};

function currentTask(data?: Investigation, claim?: ClaimResult) {
  if (claim) return { title: 'Payment history checked', detail: claim.headline.message };
  if (!data) return { title: 'Choose a payment to investigate', detail: 'The phone supplies the original payment. Byte Bot then reviews evidence, checks risk and requests permission for protective steps.' };
  const run = data.analysis;
  if (!run) {
    const confirmed = data.evidence.filter(e => e.review_state === 'confirmed').length;
    const pending = data.evidence.length - confirmed;
    return { title: pending ? 'Waiting for evidence confirmation' : 'Waiting for the customer to start the check', detail: `${confirmed} evidence item${confirmed === 1 ? '' : 's'} confirmed.${pending ? ` ${pending} still need review before analysis.` : ' Saved payment details and answers are ready for review on the phone.'}` };
  }
  if (run.state === 'queued') return { title: 'Waiting for an analysis worker', detail: 'The request is queued for this saved revision. No completed assessment is available yet.' };
  if (run.state === 'running') return TASKS[run.stage] ?? { title: 'Processing the saved case', detail: 'The timeline below shows the backend decisions recorded so far.' };
  if (run.state === 'failed') return { title: 'Analysis needs a retry', detail: 'The saved context and evidence remain available. The customer can retry from the phone.' };
  const agent = run.agent;
  const questions = agent?.follow_ups.filter(q => q.state === 'open') ?? [];
  const actions = agent?.actions.filter(a => a.state !== 'revoked') ?? [];
  if (questions.length) return { title: 'Waiting for missing customer details', detail: `${questions.length} follow-up question${questions.length === 1 ? '' : 's'} on the phone. Answers let the supervisor reassess the case before proceeding.` };
  const human = actions.filter(a => a.state === 'awaiting_human').length;
  if (data.escalation && data.escalation.state !== 'resolved') return { title: 'Waiting for human review', detail: `${data.escalation.priority} priority handoff. ${human ? `${human} protective step${human === 1 ? '' : 's'} need human approval.` : 'The support team has the case findings and escalation reasons.'}` };
  const consent = actions.filter(a => a.state === 'awaiting_consent').length;
  if (consent) return { title: 'Waiting for customer approval', detail: `${consent} protective step${consent === 1 ? '' : 's'} need consent on the phone. These steps stay pending until the customer approves or declines.` };
  if (human) return { title: 'Protective steps still need human approval', detail: `${human} step${human === 1 ? '' : 's'} remain pending. A resolved escalation does not execute unapproved actions.` };
  if (actions.some(a => a.state === 'failed')) return { title: 'A simulated action needs attention', detail: 'The assessment is saved. Review the failed action and its recorded state below.' };
  if (actions.some(a => a.state === 'approved')) return { title: 'Approved protective steps are ready', detail: 'Permission has been granted. Completion is shown only after the simulated system returns a receipt.' };
  if (run.prepare_report && !run.report_id) return { title: 'Assessment saved; report needs retry', detail: 'The customer can retry preparing the private report from the phone.' };
  const done = actions.filter(a => a.state === 'executed').length;
  return { title: 'Payment check complete', detail: `${done} simulated action${done === 1 ? '' : 's'} completed.${run.report_id ? ' The private report is ready to download.' : ' The assessment and safe next steps are saved.'} The customer records any external follow-up.` };
}

export function JudgeView({ data, claim, mode }: { data?: Investigation; claim?: ClaimResult; mode?: string }) {
  const run = data?.analysis;
  const result = run?.state === 'complete' ? run.result : null;
  const agent = run?.agent;
  const actions = (agent?.actions ?? []).filter(a => a.state !== 'revoked');
  const task = currentTask(data, claim);
  const status = claim ? 'Payment claim checked' : !data ? 'Waiting for a payment' : !run ? 'Ready for customer review' : { queued: 'Analysis queued', running: 'Analysis in progress', failed: 'Analysis failed', complete: 'Analysis complete' }[run.state];
  return <div className="judge-view">
    <div className="judge-case"><div><small>CURRENT CASE</small><h2>{claim ? 'Did the credit arrive?' : data ? `${money(data.transaction)} · ${data.transaction.sender_name}` : 'The customer is browsing'}</h2><p role="status"><Activity size={15} aria-hidden="true" />{status}</p></div>{result && <span className="judge-category">{result.category}</span>}</div>
    <p className="judge-provenance">Synthetic payments · Simulated intelligence and systems · {mode === 'fixture' ? 'Fixture extraction' : mode === 'sarvam' ? 'Live Sarvam extraction' : mode === 'gemini' ? 'Live Gemini extraction' : 'Loading provider mode'}</p>
    <section className="judge-current-task" aria-label="Current backend task" aria-live="polite"><small>CURRENT TASK</small><h3>{task.title}</h3><p>{task.detail}</p></section>
    {result && <ul className="judge-signals" aria-label="Key findings">{highlightedFindings(result.findings).slice(0, 3).map((finding, index) => <li key={index}>{SIGNAL_LABELS[finding.kind] ?? finding.text}<small>{finding.source}</small></li>)}</ul>}
    {claim ? <><section className="judge-section"><h3>History lookup</h3><p>{claim.headline.message}</p><p>Result: <code>{claim.status}</code> · {claim.matches.length} matching payments</p><p>Owner-scoped history check. No AI call, case or evidence stored.</p></section><details className="judge-details"><summary>Story checks</summary><ul>{claim.story.map(s => <li key={s.id}><strong>{s.question}</strong><p>{s.answer}</p></li>)}</ul></details></>
      : !data ? <div className="judge-idle"><Bot size={34} aria-hidden="true" /><h3>Watch Byte Bot work</h3><p>Open a payment on the phone, or load a scenario below. Agent decisions and policy checks appear here as the backend returns them.</p></div> : <>
        <section className="judge-section"><h3>Agent timeline <small>{run ? `Revision ${run.input_revision}` : 'Not started'}</small></h3>
          <ol className="judge-timeline" aria-label="Backend decision timeline">
            {agent?.trace.length ? agent.trace.map(step => {
              const active = run?.state === 'running' && run.stage === step.node;
              const keyTask = active || ['plan_actions', 'policy_gate', 'escalate'].includes(step.node);
              return <li key={step.seq} className={active ? 'is-current-task' : undefined} aria-current={active ? 'step' : undefined}><CheckCircle2 size={17} aria-hidden="true" /><div><strong>{keyTask ? <mark className="judge-task-highlight">{NODE_LABELS[step.node] ?? step.node}</mark> : NODE_LABELS[step.node] ?? step.node}</strong>{active && <span className="judge-task-label">In progress</span>}<p>{step.reason}</p></div><time dateTime={step.created_at}>{new Date(step.created_at).toLocaleTimeString('en-IN', { timeStyle: 'medium' })}</time></li>;
            }) : STAGES.map(stage => {
              const active = run?.state === 'running' && run.stage === stage.id;
              return <li key={stage.id} className={active ? 'is-current-task' : undefined} aria-current={active ? 'step' : undefined}><Clock3 size={17} aria-hidden="true" /><div><strong>{stage.title}</strong><p>{active ? 'In progress' : 'Not started'} · {TASKS[stage.id].detail}</p></div></li>;
            })}
          </ol>
          {run?.state === 'running' && <p role="status">Current stage: {NODE_LABELS[run.stage] ?? run.stage}</p>}
          {run?.state === 'failed' && <p role="alert">The run failed ({run.error_code ?? 'unavailable'}). Saved evidence is retained; retry from the phone.</p>}
          {agent?.outcome && <p className="judge-outcome">Outcome: {OUTCOMES[agent.outcome] ?? agent.outcome}</p>}
        </section>
        <section className="judge-section"><h3>Policy &amp; simulated actions <small>{agent?.policy_version ?? 'Awaiting analysis'}</small></h3>
          {actions.length ? <ul className="judge-actions">{actions.map(action => <li key={action.id} className={['awaiting_consent', 'awaiting_human', 'failed'].includes(action.state) ? 'needs-attention' : undefined}><div><strong>{action.label}</strong><span className={`judge-action-state state-${action.state}`}>{STATE_LABEL[action.state]}</span></div><p>{action.system_label} · <code>{action.verdict}</code> · actor: {action.actor}</p><p>{action.reason}</p>{action.system_reference && <p className="judge-receipt"><code>{action.system_reference}</code>{action.detail && ` · ${action.detail}`}</p>}</li>)}</ul> : <p>{run?.state === 'complete' ? 'No active system actions.' : 'Actions appear after planning and the Python policy check.'}</p>}
          {data.escalation && <p>Human handoff: {data.escalation.state} · {data.escalation.priority} priority · SLA {date(data.escalation.sla_due_at)} IST. <a href={`/console/cases/${data.escalation.id}`} target="_blank" rel="noopener">Open human console ↗</a></p>}
          <div className="judge-saved"><span>Report: <b>{run?.report_id ? 'Ready to download' : run?.prepare_report ? run.state === 'complete' ? 'Needs retry' : 'Approved, awaiting result' : 'Not requested'}</b></span><span>Customer status: <b>{data.case_status}</b></span></div>
        </section>
        {result && <details className="judge-details"><summary>Findings, evidence &amp; technical details</summary>
          <div className="judge-detail-body"><p>{result.summary}</p><p>{result.rule_version} · {result.extraction_status} extraction{run?.duration_seconds != null && ` · ${run.duration_seconds.toFixed(2)} s`}</p>
            <ul>{result.findings.map((finding, i) => <li key={i}><strong>{finding.text}</strong><p>{finding.source} · {finding.rule_id}</p>{finding.quote && <blockquote>{finding.quote}</blockquote>}{data.evidence.some(e => e.id === finding.reference) && <Link to={`/investigations/${data.id}#evidence-${finding.reference}`}>Review source evidence</Link>}</li>)}</ul>
            {result.risk_score != null && <Gauge value={result.risk_score} tone={({ "High concern": "high", "Needs verification": "medium", "No strong indicators found": "low", "Unable to assess": "neutral" })[result.category]} />}
            <p>The score summarizes supported signals; Python rules decide the category.</p>
            {result.story?.map(step => <p key={step.id}><strong>{step.question}</strong><br />{step.answer}</p>)}
            {!!result.graph_links?.length && <FraudGraph caseId={data.id} variant="stage" senderVpa={data.transaction.sender_vpa} />}
            <h4>Limitations</h4><ul>{result.limitations.map(line => <li key={line}>{line}</li>)}</ul>
          </div></details>}
      </>}
  </div>;
}
