import json
from typing import Protocol, TypeVar
import httpx
from pydantic import BaseModel
from .db import settings
from . import schemas as s

T = TypeVar('T', bound=BaseModel)


class ProviderResponseError(Exception):
    pass


class LLMProvider(Protocol):
    async def generate(self, workflow: str, prompt: str, payload: dict, schema: type[T]) -> T: ...


class CompatibleProvider:
    async def generate(self, workflow, prompt, payload, schema):
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(settings.llm_base_url.rstrip('/') + '/chat/completions', headers={'Authorization': f'Bearer {settings.llm_api_key}'}, json={'model': settings.llm_model, 'messages': [{'role': 'system', 'content': prompt + '\nReturn JSON matching this schema: ' + json.dumps(schema.model_json_schema())}, {'role': 'user', 'content': json.dumps(payload, default=str)}], 'response_format': {'type': 'json_object'}, 'temperature': 0.2})
            response.raise_for_status()
            try:
                content = response.json()['choices'][0]['message']['content']
                if not isinstance(content, str):
                    raise ProviderResponseError('Missing structured content')
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise ProviderResponseError('Malformed provider envelope') from exc
            return schema.model_validate_json(content)


class MockProvider:
    """Deterministic demo proposals, derived from supplied inputs; never fabricated company facts."""
    async def generate(self, workflow, prompt, payload, schema):
        context = payload.get('context', {})
        product = context.get('product') or {}
        idea = payload.get('idea', '')
        rules = context.get('rules', [])
        answers = payload.get('answers', [])
        def answer(category, fallback='Unknown — not decided'):
            return next((a['answer'] for a in answers if a['category'] == category and a['status'] == 'answered'), fallback)
        if workflow == 'context':
            lines = [line.strip() for line in payload['text'].splitlines() if line.strip()][:30]
            result = {'items': [{'category': 'overview', 'title': line.split(':')[0][:100] if ':' in line else 'Imported statement', 'content': line, 'status': 'assumed', 'source': 'document', 'confidence': .5} for line in lines]}
        elif workflow == 'help':
            result = {'suggestion': f"Proposed starting point for {payload['stage']}: interview 5 prospective users about '{payload['idea'][:180]}' and record evidence before choosing an answer.", 'rationale': 'This is an unvalidated discovery suggestion, not an organization fact.'}
        elif workflow == 'discovery':
            questions = [s.QuestionSpec(question=f"What user problem should '{payload['title']}' solve, and what is outside scope?", reason='An initiative needs a bounded problem even when company context is known.', category='problem'), s.QuestionSpec(question='What does the current journey look like, including failure or abandonment points?', reason='The proposed flow must improve on the existing alternative.', category='journey'), s.QuestionSpec(question=f"Which measurable outcome and target will demonstrate success{(' against ' + product['business_metrics']) if product.get('business_metrics') else ''}?", reason='A metric needs a unit, target, and observation window.', category='metrics'), s.QuestionSpec(question='Which data sources and services are available, and who owns these dependencies?', reason='Dependencies must be validated before implementation.', category='dependencies')]
            if not product.get('users'):
                questions.append(s.QuestionSpec(question='Who is the primary user, and is the buyer a different person?', reason='No primary user is established in this product context.', category='users'))
            if rules:
                rule = rules[0]
                questions.append(s.QuestionSpec(question=f"How will this initiative satisfy the rule: {rule['content']}?", reason=f"Organization rule {rule['id']} ({rule['kind']}) applies to this initiative.", category='rules'))
            if payload.get('ai_relevant'):
                questions.append(s.QuestionSpec(question='What may the AI decide, what requires human review, and what happens when evidence is missing?', reason='AI behavior requires explicit limits and fallback behavior.', category='ai'))
            result = {'questions': [q.model_dump() for q in questions[:7]]}
        elif workflow == 'brief':
            unknown = [a['question'] for a in answers if a['status'] != 'answered']
            result = dict(problem_statement=answer('problem', idea), target_users=product.get('users') or answer('users'), current_user_journey=answer('journey', product.get('current_user_journey') or 'Unknown — current journey requires validation'), proposed_solution=idea, value_proposition='Proposed: reduce effort in the user journey; validate with user research.', goals=[answer('metrics', 'Unknown — measurable outcome not decided')], non_goals=['Proposed: no expansion beyond this initiative without a scope review.'], assumptions=[{'title': 'Value proposition', 'content': 'The proposed solution will reduce user effort; user research is still required.', 'status': 'assumed'}], open_questions=unknown, constraints=[r['content'] for r in rules] + ([product['constraints']] if product.get('constraints') else []), dependencies=[answer('dependencies')], success_metrics=[answer('metrics', 'Unknown — target and measurement window not decided')])
        elif workflow == 'requirements':
            brief = payload['brief']
            def req(code, title, description, kind, criteria, edges):
                return dict(requirement_code=code, title=title, description=description, type=kind, priority='must', acceptance_criteria=criteria, dependencies=brief['dependencies'], edge_cases=edges)
            requirements = [req('FR-01', payload['title'], brief['proposed_solution'], 'functional', ['The user can start, inspect, and complete the proposed flow.', 'Invalid input shows an actionable message without losing entered data.', 'A failed operation can be retried without duplicate effects.'], ['Empty input', 'Network failure', 'Repeated submission']), req('AN-01', 'Measure the core journey', 'Record consent-appropriate start, completion, and failure events.', 'analytics', ['Events include a pseudonymous session ID, event name, and timestamp.', 'No sensitive financial data or personal identifiers enter event payloads.'], ['Analytics service unavailable']), req('SEC-01', 'Protect sensitive information', 'Restrict access to authorized users and redact sensitive information from logs.', 'security', ['Unauthorized requests are denied.', 'Sensitive input is absent from application logs.'], ['Expired session', 'Malformed payload'])]
            behavior = None
            if payload.get('ai_relevant'):
                requirements.append(req('AI-01', 'Grounded output with human control', 'Provide evidence with every AI output and abstain when required inputs are unavailable.', 'ai_ml', ['Missing required evidence produces an explicit unavailable state.', 'Every recommendation includes an explanation and human review action.', 'The AI respects all listed organization rules.'], ['Insufficient evidence', 'Provider timeout', 'Contradictory inputs']))
                behavior = dict(capability=payload['title'], input=['User-provided inputs', 'Confirmed context'], output=['Structured recommendation', 'Evidence and uncertainties'], allowed_behavior=['Summarize available evidence', 'Recommend human review'], prohibited_behavior=[r['content'] for r in rules if r['kind'] == 'must_not'] + ['Invent facts', 'Execute irreversible actions'], confidence_behavior='Do not display uncalibrated numerical confidence. Label insufficient or conflicting evidence.', fallback_behavior='Abstain and preserve input when evidence is missing or the provider fails.', human_review_requirements='User approval required before acting on recommendations.', explainability_requirements='Cite the input evidence and applicable organization rules.', evaluation_metrics=['Proposed: groundedness, abstention accuracy, and task completion; targets unresolved.'], failure_modes=['Provider timeout', 'Invalid structured output', 'Missing data', 'Prompt injection'])
            result = {'requirements': requirements, 'ai_behavior': behavior}
        elif workflow == 'prd':
            result = {'executive_summary': payload['brief']['proposed_solution'], 'background': context.get('organization', {}).get('description') or 'Unknown — background requires validation.', 'user_stories': [f"As {payload['brief']['target_users']}, I want {idea}, so I can address the stated problem."], 'risks_and_mitigations': ['Proposed: validate unresolved assumptions with users before rollout.', 'Proposed: test service failure recovery before enabling the feature.'], 'rollout_plan': ['Proposed: internal validation against acceptance criteria.', 'Proposed: limited pilot after dependency and assumption review.', 'Proposed: expand only after success metrics and rollback criteria are approved.']}
        elif workflow == 'critic':
            result = {'issues': []}  # Deterministic checks are composed by the critic service.
        else:
            raise ValueError('Unsupported workflow')
        return schema.model_validate(result)


def get_provider() -> LLMProvider:
    if settings.llm_provider == 'mock' or not settings.llm_api_key:
        return MockProvider()
    if settings.llm_provider == 'compatible':
        return CompatibleProvider()
    raise ValueError('LLM_PROVIDER must be mock or compatible')
