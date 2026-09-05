import asyncio
from types import SimpleNamespace
from sqlalchemy import select
from app import models as m, schemas as s
from app.context import RulesContextRetriever, maturity
from app.llm import MockProvider
from app.quality import evaluate_rules, quality_score, measurable


def post(client, path, data=None):
    response = client.post(path, json=data) if data is not None else client.post(path)
    assert response.status_code in (200, 201), response.text
    return response.json()


def seed_prd(client):
    org = client.get('/organizations').json()[0]
    return client.get('/prds', params={'organization_id': org['id']}).json()[0]


def to_brief(client, unknown=False):
    p = seed_prd(client)
    p = post(client, f'/prds/{p["id"]}/discovery')
    for q in p['questions']:
        answer = 'Increase assessment completion from 40% to 60% within 90 days' if q['category'] == 'metrics' else 'Use validated user inputs with explicit human review and scoped eligibility education.'
        response = client.patch(f'/prds/{p["id"]}/discovery/{q["id"]}', json={'status': 'unknown' if unknown else 'answered', 'answer': '' if unknown else answer})
        assert response.status_code == 200, response.text
    return post(client, f'/prds/{p["id"]}/brief')


def to_review(client):
    p = to_brief(client)
    post(client, f'/prds/{p["id"]}/brief/approve')
    post(client, f'/prds/{p["id"]}/requirements')
    return post(client, f'/prds/{p["id"]}/generate')


def test_context_crud_and_blueprint_gate(client):
    org = post(client, '/organizations', {'name': 'NewCo', 'mode': 'greenfield'})
    product = {'organization_id': org['id'], 'name': 'Pilot', 'description': 'A new product'}
    assert client.post('/products', json=product).status_code == 409
    assert client.post(f'/organizations/{org["id"]}/validate').status_code == 409
    context = post(client, f'/organizations/{org["id"]}/context', {'category': 'customers', 'title': 'User', 'content': 'Local shop owners', 'status': 'assumed'})
    assert client.patch(f'/organizations/{org["id"]}/context/{context["id"]}', json={'status': 'confirmed'}).status_code == 200
    assert client.get(f'/organizations/{org["id"]}/context').json()[0]['status'] == 'confirmed'
    post(client, f'/organizations/{org["id"]}/validate')
    post(client, '/products', product)
    assert client.delete(f'/organizations/{org["id"]}/context/{context["id"]}').status_code == 204
    assert client.get(f'/organizations/{org["id"]}/context').json() == []


def test_cross_organization_context_isolation(client):
    orgs = client.get('/organizations').json()
    item = client.get(f'/organizations/{orgs[0]["id"]}/context').json()[0]
    other = post(client, '/organizations', {'name': 'Other'})
    assert client.patch(f'/organizations/{other["id"]}/context/{item["id"]}', json={'status': 'rejected'}).status_code == 404


def test_import_candidates_never_silently_confirmed(client):
    org = client.get('/organizations').json()[0]
    post(client, f'/organizations/{org["id"]}/import', {'text': 'Market: India\nBusiness model: Undecided'})
    imported = [i for i in client.get(f'/organizations/{org["id"]}/context').json() if i['source'] == 'document']
    assert len(imported) == 2
    assert all(i['status'] == 'assumed' for i in imported)
    assert client.post(f'/organizations/{org["id"]}/documents', files={'file': ('bad.exe', b'hello')}).status_code == 415


def test_state_guards(client):
    p = seed_prd(client)
    for step in ['brief', 'brief/approve', 'requirements', 'generate', 'review', 'finalize']:
        assert client.post(f'/prds/{p["id"]}/{step}').status_code == 409
    post(client, f'/prds/{p["id"]}/discovery')
    assert client.post(f'/prds/{p["id"]}/discovery').status_code == 409
    assert client.post(f'/prds/{p["id"]}/brief').status_code == 409


def test_unknown_answers_survive_generation(client):
    p = to_brief(client, unknown=True)
    assert len(p['brief']['content']['open_questions']) == len(p['questions'])
    assert any(a['status'] == 'unknown' for a in p['assumptions'])
    assert not p['brief']['approved']


def test_assumption_transitions_and_promotion(client):
    p = to_brief(client)
    a = p['assumptions'][0]
    path = f'/prds/{p["id"]}/assumptions/{a["id"]}'
    assert client.post(path + '/promote').status_code == 409
    for status in ['rejected', 'unknown', 'assumed', 'confirmed']:
        response = client.patch(path, json={'status': status})
        assert response.status_code == 200
        assert response.json()['assumptions'][0]['status'] == status
    first = post(client, path + '/promote')['assumptions'][0]['promoted_context_id']
    assert post(client, path + '/promote')['assumptions'][0]['promoted_context_id'] == first
    assert client.patch(path, json={'status': 'rejected'}).status_code == 409


def test_full_workflow_requirements_critic_finalize(client):
    p = to_review(client)
    assert p['status'] == 'review'
    assert len(p['requirements']) >= 3
    assert p['sections']['ai_behavior']['fallback_behavior']
    assert client.post(f'/prds/{p["id"]}/finalize').status_code == 409
    p = post(client, f'/prds/{p["id"]}/review')
    for i in p['review_issues']:
        assert i['severity'] != 'critical', i
        assert client.patch(f'/prds/{p["id"]}/review/{i["id"]}', json={'action': 'ignore'}).status_code == 200
    p = post(client, f'/prds/{p["id"]}/finalize')
    assert p['status'] == 'final'
    assert 0 <= p['quality']['overall'] <= 100
    assert client.post(f'/prds/{p["id"]}/review').status_code == 409
    exported = client.get(f'/prds/{p["id"]}/export').text
    assert 'Acceptance criteria' in exported and 'Assumptions ledger' in exported


def test_requirement_edits_invalidate_review(client):
    p = to_review(client)
    post(client, f'/prds/{p["id"]}/review')
    r = p['requirements'][0]
    data = {k: r[k] for k in s.RequirementSpec.model_fields}
    data['acceptance_criteria'] = ['Validated edit with testable success behavior']
    updated = client.put(f'/prds/{p["id"]}/requirements/{r["id"]}', json=data)
    assert updated.status_code == 200, updated.text
    assert not updated.json()['sections'].get('_reviewed')
    assert client.post(f'/prds/{p["id"]}/finalize').status_code == 409


def test_manual_requirement_creation(client):
    p = to_brief(client)
    post(client, f'/prds/{p["id"]}/brief/approve')
    data = {'requirement_code': 'FR-01', 'title': 'Upload', 'description': 'Upload valid documents', 'type': 'functional', 'priority': 'must', 'acceptance_criteria': ['Reject invalid files'], 'dependencies': ['Document store'], 'edge_cases': ['Empty file']}
    post(client, f'/prds/{p["id"]}/requirements/manual', data)
    assert client.post(f'/prds/{p["id"]}/requirements/manual', json=data).status_code == 409


def test_context_retrieval_prioritizes_and_excludes(db):
    org = db.scalar(select(m.Organization))
    p = db.scalar(select(m.Product))
    db.add(m.OrganizationContextItem(organization_id=org.id, category='terminology', title='Irrelevant', content='ZXQ', status='confirmed'))
    db.add(m.OrganizationContextItem(organization_id=org.id, category='overview', title='Rejected', content='Never use', status='rejected'))
    db.flush()
    result = RulesContextRetriever(db).get_context(org.id, p.id, 'loan readiness', ['customers'])
    assert 'Rejected' not in [i['title'] for i in result['items']]
    assert 'Irrelevant' not in [i['title'] for i in result['items']]
    assert result['items'][0]['status'] == 'confirmed'
    assert result['rules'] and result['product']['id'] == p.id


def test_rule_evaluation():
    rules = [SimpleNamespace(kind='must', content='Every feature requires analytics events'), SimpleNamespace(kind='must_not', content='Never guarantee loan approval')]
    violations = evaluate_rules(rules, {'proposed_solution': 'We guarantee loan approval'}, [])
    assert len(violations) == 2 and all(i.severity == 'critical' for i in violations)
    safe = evaluate_rules([rules[1]], {'proposed_solution': 'Never guarantee loan approval'}, [])
    assert not safe


def test_quality_and_maturity_are_deterministic():
    p = SimpleNamespace(sections={}, ai_relevant=False)
    assert quality_score(p, {}, [], [], []) == quality_score(p, {}, [], [], [])
    assert measurable('Increase completion to 60% within 90 days')
    assert not measurable('Improve customer satisfaction')
    assert not measurable('Unknown target of 60%')
    assert maturity([])['overall'] == 0
    assert maturity([SimpleNamespace(category='overview', status='confirmed', content='Fact')])['overall'] > 0


def test_mock_outputs_validate():
    provider = MockProvider()
    output = asyncio.run(provider.generate('discovery', '', {'title': 'Checkout', 'idea': 'Improve checkout', 'context': {}}, s.DiscoveryOutput))
    assert 3 <= len(output.questions) <= 7
    assert all(q.reason for q in output.questions)
