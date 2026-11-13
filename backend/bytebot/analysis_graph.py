"""One typed four-node graph. PostgreSQL stores durable stage checkpoints."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .guidance import resolve
from .analysis_store import fenced, save_stage, publish
from .investigation_store import confirmed_evidence
from .investigation_schemas import Context
from .extraction import extract
from .intelligence import lookup
from .risk_rules import assess


class InvestigationState(TypedDict, total=False):
    run: dict
    outputs: dict
    transaction: dict | None
    context: dict
    evidence: list[dict]
    result: dict


def build_graph(pool, provider):
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
        save_stage(pool, run, 'transaction_context', {'status': transaction['status'] if transaction else 'unavailable'})
        return {'transaction': transaction, 'context': context, 'evidence': evidence}

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
            result = assess(state['transaction'], state['context'], state['evidence'], outputs['message_analysis'], matches)
            save_stage(pool, run, 'risk_investigation', result)
        return {'result': result}

    async def incident_resolution(state):
        run = state['run']
        save_stage(pool, run, 'incident_resolution')
        # Only schema-validated, source-bound rule output is displayed. No free
        # model narrative, report, external submission, or case status action.
        result = resolve(state['result'], state['transaction'], state['context'])
        save_stage(pool, run, 'incident_resolution', {'ready': True})
        publish(pool, run, result)
        return {'result': result}

    graph = StateGraph(InvestigationState)
    nodes = [('transaction_context', transaction_context), ('message_analysis', message_analysis),
             ('risk_investigation', risk_investigation), ('incident_resolution', incident_resolution)]
    previous = START
    for name, function in nodes:
        graph.add_node(name, function)
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile()
