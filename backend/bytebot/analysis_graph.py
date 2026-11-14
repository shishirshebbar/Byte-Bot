"""Supervisor-led LangGraph. PostgreSQL stores durable stage checkpoints.

One main agent (the supervisor) routes between four specialists: Transaction
Context, Message Analysis, Risk Investigation, and Incident Resolution. Between
assessment and resolution it asks for missing context, plans playbook steps,
gates every step through Python policy, and escalates to a person when needed.
Routing is deterministic: the rule category, never a model, decides what happens.
"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .guidance import resolve
from .analysis_store import fenced, save_stage, publish, record_trace
from .investigation_store import confirmed_evidence
from .investigation_schemas import Context
from .extraction import extract
from .intelligence import lookup, graph_links
from .risk_rules import assess
from . import planner, policy

SPECIALISTS = ('transaction_context', 'message_analysis', 'risk_investigation', 'incident_resolution')
NODES = SPECIALISTS + ('gather_context', 'plan_actions', 'policy_gate', 'escalate')


class InvestigationState(TypedDict, total=False):
    run: dict
    outputs: dict
    transaction: dict | None
    context: dict
    evidence: list[dict]
    follow_up_rounds: int
    result: dict
    agent: dict
    trace: list
    next: str


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def route(state):
    """Return the supervisor's next node and a customer-safe reason."""
    outputs, agent = state.get('outputs', {}), state.get('agent', {})
    if 'transaction' not in state:
        return 'transaction_context', "Start with the original payment record and the customer's saved answers."
    if 'message_analysis' not in outputs:
        count = len(state['evidence'])
        if not count:
            return 'message_analysis', 'No evidence was shared, so record that extraction is not needed.'
        return 'message_analysis', f'Read {plural(count, "confirmed evidence item")} for scam tactics and identifiers.'
    if 'result' not in state:
        return 'risk_investigation', 'Correlate the payment, answers, evidence, and simulated intelligence using the Python risk rules.'
    category = state['result']['category']
    if 'follow_ups' not in agent:
        return 'gather_context', f'The rules returned "{category}". Check which missing answers could change that.'
    if 'plan' not in agent and not agent['blocking']:
        return 'plan_actions', f'Choose protective steps for "{category}" from the playbook.'
    if 'escalation_reasons' not in agent:
        if agent['blocking']:
            return 'policy_gate', 'Hold every action until the customer answers. Check whether a person is needed now.'
        return 'policy_gate', f'Check {plural(len(agent["plan"]), "planned step")} against {policy.POLICY_VERSION} and the escalation rules.'
    if agent['escalation_reasons'] and not agent.get('escalated'):
        labels = ' '.join(policy.REASONS[code][1] for code in agent['escalation_reasons'])
        return 'escalate', f'Hand off to a person. {labels}'
    states = [action['state'] for action in agent['actions']]
    if agent['escalation_reasons']:
        why = 'Publish the assessment and the handoff brief for the human teammate.'
    elif agent['blocking']:
        why = f'Publish what is known and ask {plural(len(agent["follow_ups"]), "follow-up question")}.'
    elif 'awaiting_consent' in states:
        why = f'Publish the assessment and ask consent for {plural(states.count("awaiting_consent"), "step")}.'
    elif states:
        why = 'Publish the assessment and the approved steps.'
    else:
        why = 'Publish the assessment. No account action is needed.'
    return 'incident_resolution', why


def build_graph(pool, provider, systems=None):
    if systems is None:
        from .systems import SimulatedSystems
        systems = SimulatedSystems()

    async def supervisor(state):
        node, reason = route(state)
        trace = state.get('trace', [])
        record_trace(pool, state['run'], len(trace), node, reason)
        return {'next': node, 'trace': trace + [{'node': node, 'reason': reason}]}

    async def transaction_context(state):
        run = state['run']
        save_stage(pool, run, 'transaction_context')
        with pool.connection() as conn:
            case = fenced(conn, run)
            transaction = conn.execute('SELECT * FROM transactions WHERE id=%s AND owner_id=%s',
                (case['transaction_id'], case['owner_id'])).fetchone()
            context = Context.model_validate(conn.execute('SELECT answers FROM investigation_context WHERE investigation_id=%s',
                (case['id'],)).fetchone()['answers']).model_dump()
            evidence = confirmed_evidence(conn, case['owner_id'], case['id'])
            rounds = conn.execute('SELECT count(DISTINCT input_revision) AS n FROM follow_up_questions '
                                  'WHERE investigation_id=%s AND input_revision<%s AND blocking',
                                  (case['id'], run['input_revision'])).fetchone()['n']
        save_stage(pool, run, 'transaction_context', {'status': transaction['status'] if transaction else 'unavailable'})
        return {'transaction': transaction, 'context': context, 'evidence': evidence, 'follow_up_rounds': rounds}

    async def message_analysis(state):
        run, outputs = state['run'], state['outputs']
        save_stage(pool, run, 'message_analysis')
        output = outputs.get('message_analysis')
        if output is None:
            output = await extract(provider, state['evidence'], state['transaction'] or {})
            save_stage(pool, run, 'message_analysis', output)
        return {'outputs': {**outputs, 'message_analysis': output}}

    async def risk_investigation(state):
        run, outputs = state['run'], state['outputs']
        save_stage(pool, run, 'risk_investigation')
        result = outputs.get('risk_investigation')
        if result is None:
            identifiers = []
            if state['transaction']:
                identifiers.append(('vpa', state['transaction']['sender_vpa']))
            if state['context'].get('requested_vpa'):
                identifiers.append(('vpa', state['context']['requested_vpa']))
            for item in outputs['message_analysis']['claims']:
                if item['kind'] in ('vpa', 'phone') and item.get('intel_relevant'):
                    identifiers.append((item['kind'], item['value']))
            with pool.connection() as conn:
                fenced(conn, run)
                matches = lookup(conn, identifiers)
                links = graph_links(conn, identifiers)
            result = assess(state['transaction'], state['context'], state['evidence'], outputs['message_analysis'], matches, links)
            save_stage(pool, run, 'risk_investigation', result)
        return {'result': result, 'agent': {}}

    async def gather_context(state):
        questions, blocking = planner.follow_ups(state['context'], state['result'], state['outputs']['message_analysis'])
        return {'agent': {**state['agent'], 'follow_ups': questions, 'blocking': blocking}}

    async def plan_actions(state):
        steps = planner.plan(state['transaction'], state['context'], state['result'])
        return {'agent': {**state['agent'], 'plan': steps}}

    async def policy_gate(state):
        agent = state['agent']
        reasons = policy.escalation_reasons(
            state['transaction'], state['context'], state['evidence'], state['result'],
            state['outputs']['message_analysis'], blocking=agent['blocking'],
            questions=agent['follow_ups'], follow_up_rounds=state['follow_up_rounds'])
        actions = []
        for step in agent.get('plan', []):
            verdict, why = policy.verdict(step['action_type'], state['transaction'], escalating=bool(reasons))
            actions.append({**step, 'verdict': verdict, 'state': policy.STATES[verdict],
                            'reason': f"{step['reason']} {why}"})
        return {'agent': {**agent, 'actions': actions, 'escalation_reasons': reasons,
                          'priority': policy.priority(reasons)}}

    async def escalate(state):
        return {'agent': {**state['agent'], 'escalated': True}}

    async def incident_resolution(state):
        run = state['run']
        save_stage(pool, run, 'incident_resolution')
        # Publish source-bound guidance, the agent's decisions, and any approved private report.
        result = resolve(state['result'], state['transaction'], state['context'])
        save_stage(pool, run, 'incident_resolution', {'ready': True})
        agent = state['agent']
        publish(pool, run, result, {'follow_ups': agent['follow_ups'], 'blocking': agent['blocking'],
                                    'actions': agent['actions'], 'escalation_reasons': agent['escalation_reasons'],
                                    'priority': agent['priority']}, systems)
        return {'result': result}

    graph = StateGraph(InvestigationState)
    graph.add_node('supervisor', supervisor)
    functions = {'transaction_context': transaction_context, 'message_analysis': message_analysis,
                 'risk_investigation': risk_investigation, 'gather_context': gather_context,
                 'plan_actions': plan_actions, 'policy_gate': policy_gate, 'escalate': escalate,
                 'incident_resolution': incident_resolution}
    for name, function in functions.items():
        graph.add_node(name, function)
        graph.add_edge(name, END if name == 'incident_resolution' else 'supervisor')
    graph.add_edge(START, 'supervisor')
    graph.add_conditional_edges('supervisor', lambda state: state['next'], {name: name for name in NODES})
    return graph.compile().with_config(recursion_limit=50)
