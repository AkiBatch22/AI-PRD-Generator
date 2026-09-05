from app import schemas as s
from app.workflows import ProductBriefService
from test_workflow import seed_prd, to_brief, to_review, post


def test_invalid_ai_response_rolls_back(client, monkeypatch):
    p = seed_prd(client)
    p = post(client, f'/prds/{p["id"]}/discovery')
    for q in p['questions']:
        client.patch(f'/prds/{p["id"]}/discovery/{q["id"]}', json={'status': 'unknown'})
    async def broken(self, payload):
        return s.BriefContent.model_validate({'invented': 'not a valid brief'})
    monkeypatch.setattr(ProductBriefService, 'run', broken)
    response = client.post(f'/prds/{p["id"]}/brief')
    assert response.status_code == 502
    saved = client.get(f'/prds/{p["id"]}').json()
    assert saved['status'] == 'discovery' and saved['brief'] is None and not saved['assumptions']


def test_blank_acceptance_criteria_rejected(client):
    p = to_brief(client)
    post(client, f'/prds/{p["id"]}/brief/approve')
    response = client.post(f'/prds/{p["id"]}/requirements/manual', json={'requirement_code': 'FR-01', 'title': 'Empty', 'description': 'Invalid criteria', 'type': 'functional', 'priority': 'must', 'acceptance_criteria': ['   '], 'dependencies': [], 'edge_cases': []})
    assert response.status_code == 422


def test_document_has_full_structure(client):
    p = to_review(client)
    assert len(p['document_sections']) == 22
    assert p['document_sections']['acceptance_criteria']
    assert p['document_sections']['ai_ml_requirements']['behavior_specification']['fallback_behavior']


def test_rule_changes_invalidate_finalization(client):
    p = to_review(client)
    p = post(client, f'/prds/{p["id"]}/review')
    for issue in p['review_issues']:
        client.patch(f'/prds/{p["id"]}/review/{issue["id"]}', json={'action': 'ignore'})
    org = client.get('/organizations').json()[0]
    post(client, f'/organizations/{org["id"]}/rules', {'kind': 'must', 'content': 'Review accessibility with users'})
    assert client.post(f'/prds/{p["id"]}/finalize').status_code == 409


def test_non_ai_document_excludes_ai_sections(client):
    original = seed_prd(client)
    p = post(client, '/prds', {'product_id': original['product_id'], 'title': 'Settings export', 'idea': 'Allow users to export account settings as a text document.'})
    p = post(client, f'/prds/{p["id"]}/discovery')
    for q in p['questions']:
        client.patch(f'/prds/{p["id"]}/discovery/{q["id"]}', json={'status': 'unknown'})
    post(client, f'/prds/{p["id"]}/brief')
    post(client, f'/prds/{p["id"]}/brief/approve')
    post(client, f'/prds/{p["id"]}/requirements')
    p = post(client, f'/prds/{p["id"]}/generate')
    assert len(p['document_sections']) == 21
    assert 'ai_ml_requirements' not in p['document_sections']
    assert 'ai_behavior' not in p['sections']
