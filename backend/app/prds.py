import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, delete
from . import models as m, schemas as s
from .deps import DB, product, organization, prd_record, get_record, require_state
from .context import record, RulesContextRetriever
from .workflows import DiscoveryService, ProductBriefService, RequirementGenerationService, PRDGenerationService, PRDCriticService
from .quality import deterministic_review, quality_score

router = APIRouter()


def children(db, model, id):
    return db.scalars(select(model).where(model.prd_id == id)).all()


def brief_record(db, id):
    brief = db.scalar(select(m.ProductBrief).where(m.ProductBrief.prd_id == id))
    if not brief:
        raise HTTPException(409, 'Generate a product brief first')
    return brief


def payload(db, p):
    return {'title': p.title, 'idea': p.idea, 'ai_relevant': p.ai_relevant, 'context': p.context_snapshot, 'answers': [record(q) for q in children(db, m.DiscoveryQuestion, p.id)], 'assumptions': [record(a) for a in children(db, m.Assumption, p.id)]}


def detail(db, p):
    brief = db.scalar(select(m.ProductBrief).where(m.ProductBrief.prd_id == p.id))
    requirements = children(db, m.Requirement, p.id)
    assumptions = children(db, m.Assumption, p.id)
    issues = children(db, m.ReviewIssue, p.id)
    return {**record(p), 'document_sections': document_sections(p, requirements, assumptions), 'questions': [record(q) for q in children(db, m.DiscoveryQuestion, p.id)], 'brief': record(brief) if brief else None, 'requirements': [record(r) for r in requirements], 'assumptions': [record(a) for a in assumptions], 'review_issues': [record(i) for i in issues], 'quality': quality_score(p, brief.content if brief else {}, requirements, assumptions, issues)}


def document_sections(p, requirements, assumptions):
    if p.status not in {'review', 'final'}:
        return {}
    sections = p.sections
    grouped = lambda kind: [{'code': r.requirement_code, 'title': r.title, 'description': r.description, 'priority': r.priority} for r in requirements if r.type == kind]
    result = {'executive_summary': sections.get('executive_summary', ''), 'background_context': sections.get('background', ''), 'problem_statement': sections.get('problem_statement', ''), 'target_users_personas': sections.get('target_users', ''), 'current_user_journey': sections.get('current_user_journey', ''), 'proposed_solution': sections.get('proposed_solution', ''), 'goals': sections.get('goals', []), 'non_goals': sections.get('non_goals', []), 'functional_requirements': grouped('functional'), 'user_stories': sections.get('user_stories', []), 'acceptance_criteria': {r.requirement_code: r.acceptance_criteria for r in requirements}, 'edge_cases': {r.requirement_code: r.edge_cases for r in requirements}, 'non_functional_requirements': grouped('non_functional') + grouped('security') + grouped('compliance'), 'data_requirements': grouped('data')}
    if p.ai_relevant:
        result['ai_ml_requirements'] = {'requirements': grouped('ai_ml'), 'behavior_specification': sections.get('ai_behavior', {})}
    result.update(success_metrics=sections.get('success_metrics', []), analytics_events_to_track=grouped('analytics'), dependencies=sections.get('dependencies', []), risks_and_mitigations=sections.get('risks_and_mitigations', []), rollout_plan=sections.get('rollout_plan', []), open_questions=sections.get('open_questions', []), assumptions=[{'title': a.title, 'content': a.content, 'status': a.status} for a in assumptions if a.status != 'rejected'])
    return result


@router.get('/prds')
def list_prds(organization_id: str, db: DB):
    organization(db, organization_id)
    result = db.scalars(select(m.PRD).join(m.Product, m.PRD.product_id == m.Product.id).where(m.Product.organization_id == organization_id).order_by(m.PRD.updated_at.desc())).all()
    return [detail(db, p) for p in result]


@router.post('/prds', status_code=201)
def create_prd(data: s.PRDIn, db: DB):
    prod = product(db, data.product_id)
    if not organization(db, prod.organization_id).blueprint_validated:
        raise HTTPException(409, 'Validate organization context before creating a PRD')
    values = data.model_dump()
    values['ai_relevant'] = data.ai_relevant or bool(re.search(r'\bAI\b|\bML\b|machine learning|large language model|\bLLM\b', data.idea, re.I))
    p = m.PRD(**values, context_snapshot=RulesContextRetriever(db).get_context(prod.organization_id, prod.id, data.idea, ['industry', 'customers', 'metrics', 'technology']))
    db.add(p)
    db.flush()
    return detail(db, p)


@router.get('/prds/{id}')
def get_prd(id: str, db: DB):
    return detail(db, prd_record(db, id))


@router.post('/prds/{id}/discovery')
async def start_discovery(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'draft')
    output = await DiscoveryService().run(payload(db, p))
    for q in output.questions:
        db.add(m.DiscoveryQuestion(prd_id=id, **q.model_dump()))
    p.status = 'discovery'
    db.flush()
    return detail(db, p)


@router.patch('/prds/{id}/discovery/{question_id}')
def answer_question(id: str, question_id: str, data: s.AnswerIn, db: DB):
    p = prd_record(db, id)
    require_state(p, 'discovery')
    q = get_record(db, m.DiscoveryQuestion, question_id)
    if q.prd_id != id:
        raise HTTPException(404, 'Question not found')
    if data.status == 'answered' and not data.answer.strip():
        raise HTTPException(422, 'Provide an answer or explicitly leave this unresolved')
    q.answer = data.answer if data.status == 'answered' else ''
    q.status = data.status
    db.flush()
    return record(q)


@router.post('/prds/{id}/brief')
async def generate_brief(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'discovery')
    questions = children(db, m.DiscoveryQuestion, id)
    if not questions or any(q.required and q.status == 'unanswered' for q in questions):
        raise HTTPException(409, 'Answer required questions or explicitly mark them unknown/skipped')
    output = await ProductBriefService().run(payload(db, p))
    content = output.model_dump()
    content['open_questions'] = list(dict.fromkeys(content['open_questions'] + [q.question for q in questions if q.status != 'answered']))
    db.add(m.ProductBrief(prd_id=id, content=content))
    for a in output.assumptions:
        db.add(m.Assumption(prd_id=id, **a.model_dump()))
    for question in content['open_questions']:
        db.add(m.Assumption(prd_id=id, title='Unresolved discovery', content=question, status='unknown', source='system'))
    p.status = 'brief_review'
    db.flush()
    return detail(db, p)


@router.put('/prds/{id}/brief')
def edit_brief(id: str, data: s.BriefContent, db: DB):
    p = prd_record(db, id)
    require_state(p, 'brief_review')
    b = brief_record(db, id)
    b.content, b.approved = data.model_dump(), False
    # The ledger is authoritative; edits cannot silently erase assumptions.
    existing = {(a.title, a.content) for a in children(db, m.Assumption, id)}
    for a in data.assumptions:
        if (a.title, a.content) not in existing:
            db.add(m.Assumption(prd_id=id, **a.model_dump()))
    db.flush()
    return detail(db, p)


@router.post('/prds/{id}/brief/approve')
def approve_brief(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'brief_review')
    brief_record(db, id).approved = True
    p.status = 'requirements'
    db.flush()
    return detail(db, p)


@router.post('/prds/{id}/requirements')
async def generate_requirements(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'requirements')
    b = brief_record(db, id)
    if not b.approved:
        raise HTTPException(409, 'Approve the brief first')
    if children(db, m.Requirement, id):
        raise HTTPException(409, 'Requirements already exist; edit them individually')
    output = await RequirementGenerationService().run({**payload(db, p), 'brief': b.content})
    codes = [r.requirement_code for r in output.requirements]
    if len(codes) != len(set(codes)) or (p.ai_relevant and not output.ai_behavior):
        raise HTTPException(502, 'AI output contains duplicate codes or lacks required AI behavior')
    for r in output.requirements:
        db.add(m.Requirement(prd_id=id, **r.model_dump()))
    if p.ai_relevant:
        p.sections = {'ai_behavior': output.ai_behavior.model_dump()}
    db.flush()
    return detail(db, p)


@router.post('/prds/{id}/requirements/manual', status_code=201)
def add_requirement(id: str, data: s.RequirementSpec, db: DB):
    p = prd_record(db, id)
    require_state(p, 'requirements')
    if any(r.requirement_code == data.requirement_code for r in children(db, m.Requirement, id)):
        raise HTTPException(409, 'Requirement code already exists')
    r = m.Requirement(prd_id=id, source='user', **data.model_dump())
    db.add(r)
    db.flush()
    return record(r)


@router.put('/prds/{id}/requirements/{requirement_id}')
def edit_requirement(id: str, requirement_id: str, data: s.RequirementSpec, db: DB):
    p = prd_record(db, id)
    require_state(p, 'requirements', 'review')
    r = get_record(db, m.Requirement, requirement_id)
    if r.prd_id != id:
        raise HTTPException(404, 'Requirement not found')
    if any(other.id != r.id and other.requirement_code == data.requirement_code for other in children(db, m.Requirement, id)):
        raise HTTPException(409, 'Requirement code already exists')
    for key, value in data.model_dump().items():
        setattr(r, key, value)
    # Review results are stale after edits; run critic again before finalization.
    db.execute(delete(m.ReviewIssue).where(m.ReviewIssue.prd_id == id))
    p.sections = {k: v for k, v in p.sections.items() if k != '_reviewed'}
    db.flush()
    return detail(db, p)


@router.patch('/prds/{id}/assumptions/{assumption_id}')
def update_assumption(id: str, assumption_id: str, data: s.ContextPatch, db: DB):
    p = prd_record(db, id)
    require_state(p, 'brief_review', 'requirements', 'review')
    a = get_record(db, m.Assumption, assumption_id)
    if a.prd_id != id:
        raise HTTPException(404, 'Assumption not found')
    if a.promoted_context_id:
        raise HTTPException(409, 'This assumption is promoted; edit the organization context directly')
    previous_content = a.content
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(a, key, value)
    if a.status == 'confirmed' and not a.content.strip():
        raise HTTPException(422, 'Confirmed assumptions require content')
    db.flush()
    brief = brief_record(db, id)
    content = dict(brief.content)
    content['assumptions'] = [{'title': item.title, 'content': item.content, 'status': item.status} for item in children(db, m.Assumption, id) if item.status in {'assumed', 'unknown'}]
    if a.status in {'confirmed', 'rejected'}:
        content['open_questions'] = [q for q in content['open_questions'] if q != previous_content]
    brief.content = content
    if p.status == 'review':
        p.sections = {**p.sections, 'open_questions': content['open_questions']}
    p.sections = {k: v for k, v in p.sections.items() if k != '_reviewed'}
    db.flush()
    return detail(db, p)


@router.post('/prds/{id}/assumptions/{assumption_id}/promote')
def promote(id: str, assumption_id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'brief_review', 'requirements', 'review')
    a = get_record(db, m.Assumption, assumption_id)
    if a.prd_id != id:
        raise HTTPException(404, 'Assumption not found')
    if a.status != 'confirmed':
        raise HTTPException(409, 'Only confirmed assumptions can become organization context')
    if not a.promoted_context_id:
        item = m.OrganizationContextItem(organization_id=product(db, p.product_id).organization_id, category='overview', title=a.title, content=a.content, status='confirmed', source='prd', confidence=1)
        db.add(item)
        db.flush()
        a.promoted_context_id = item.id
    db.flush()
    return detail(db, p)


def assemble(p, brief, output, assumptions):
    sections = {**p.sections, **brief, **output.model_dump()}
    sections['assumptions'] = [{'title': a.title, 'content': a.content, 'status': a.status} for a in assumptions if a.status != 'rejected']
    if not p.ai_relevant:
        sections.pop('ai_behavior', None)
    return sections


@router.post('/prds/{id}/generate')
async def generate_prd(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'requirements')
    requirements = children(db, m.Requirement, id)
    if not requirements:
        raise HTTPException(409, 'Create requirements first')
    brief = brief_record(db, id).content
    output = await PRDGenerationService().run({**payload(db, p), 'brief': brief, 'requirements': [record(r) for r in requirements]})
    p.sections = assemble(p, brief, output, children(db, m.Assumption, id))
    p.status = 'review'
    db.flush()
    return detail(db, p)


@router.post('/prds/{id}/review')
async def review(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'review')
    requirements = children(db, m.Requirement, id)
    assumptions = children(db, m.Assumption, id)
    org_id = product(db, p.product_id).organization_id
    rules = db.scalars(select(m.OrganizationRule).where(m.OrganizationRule.organization_id == org_id)).all()
    # Rules are evaluated fresh even when the PRD retains its original context snapshot.
    sections = {**p.sections, 'assumptions': [{'title': a.title, 'content': a.content, 'status': a.status} for a in assumptions if a.status != 'rejected']}
    p.sections = sections
    output = await PRDCriticService().run({**payload(db, p), 'sections': sections, 'requirements': [record(r) for r in requirements], 'current_rules': [record(r) for r in rules]})
    found = deterministic_review(p, brief_record(db, id).content, requirements, assumptions, rules) + output.issues
    previous = {i.title: i.status for i in children(db, m.ReviewIssue, id)}
    db.execute(delete(m.ReviewIssue).where(m.ReviewIssue.prd_id == id))
    seen = set()
    for i in found:
        if i.title not in seen:
            db.add(m.ReviewIssue(prd_id=id, **i.model_dump(), status='ignored' if previous.get(i.title) == 'ignored' and i.severity != 'critical' else 'open'))
            seen.add(i.title)
    p.sections = {**sections, '_reviewed': True, '_rule_snapshot': sorted((r.id, r.kind, r.content) for r in rules)}
    db.flush()
    return detail(db, p)


@router.patch('/prds/{id}/review/{issue_id}')
def resolve_issue(id: str, issue_id: str, data: s.IssueAction, db: DB):
    p = prd_record(db, id)
    require_state(p, 'review')
    i = get_record(db, m.ReviewIssue, issue_id)
    if i.prd_id != id:
        raise HTTPException(404, 'Review issue not found')
    if data.action == 'ignore':
        if i.severity == 'critical':
            raise HTTPException(409, 'Critical issues must be resolved, not ignored')
        i.status = 'ignored'
    else:
        replacement = data.replacement if data.action == 'edit' else i.suggested_change
        if not replacement or not i.current_text:
            raise HTTPException(409, 'Edit the affected requirement or ledger item directly, then rerun review')
        current = p.sections.get(i.affected_section)
        if isinstance(current, str) and i.current_text in current:
            updated = current.replace(i.current_text, replacement)
        elif isinstance(current, list) and i.current_text in current:
            updated = [replacement if value == i.current_text else value for value in current]
        else:
            raise HTTPException(409, 'The source changed; edit it directly and rerun review')
        p.sections = {**p.sections, i.affected_section: updated, '_reviewed': False}
        brief = brief_record(db, id)
        if i.affected_section in brief.content:
            candidate = {**brief.content, i.affected_section: updated}
            brief.content = s.BriefContent.model_validate(candidate).model_dump()
        i.status = 'accepted'
    db.flush()
    return detail(db, p)


@router.post('/prds/{id}/finalize')
def finalize(id: str, db: DB):
    p = prd_record(db, id)
    require_state(p, 'review')
    if not p.sections.get('_reviewed'):
        raise HTTPException(409, 'Run the critic after the latest changes')
    rules = db.scalars(select(m.OrganizationRule).where(m.OrganizationRule.organization_id == product(db, p.product_id).organization_id)).all()
    if [tuple(r) for r in p.sections.get('_rule_snapshot', [])] != sorted((r.id, r.kind, r.content) for r in rules):
        raise HTTPException(409, 'Organization rules changed; rerun review')
    if any(i.status == 'open' for i in children(db, m.ReviewIssue, id)):
        raise HTTPException(409, 'Resolve or explicitly acknowledge all review issues before finalizing')
    p.status = 'final'
    db.flush()
    return detail(db, p)


@router.get('/prds/{id}/export', response_class=PlainTextResponse)
def export_prd(id: str, db: DB):
    p = prd_record(db, id)
    data = detail(db, p)
    parts = [f'# {p.title}', f'Status: {p.status} | Quality: {data["quality"]["overall"]}/100']
    for key, value in document_sections(p, children(db, m.Requirement, id), children(db, m.Assumption, id)).items():
        if not key.startswith('_') and key != 'assumptions':
            parts.extend(['## ' + key.replace('_', ' ').title(), str(value) if not isinstance(value, list) else '\n'.join('- ' + str(v) for v in value)])
    parts.append('## Requirements')
    for r in data['requirements']:
        parts.extend([f'### {r["requirement_code"]}: {r["title"]} ({r["priority"]})', r['description'], 'Acceptance criteria:\n' + '\n'.join('- ' + c for c in r['acceptance_criteria']), 'Edge cases: ' + ', '.join(r['edge_cases']), 'Dependencies: ' + ', '.join(r['dependencies'])])
    parts.append('## Assumptions ledger')
    parts.extend(f'- [{a["status"]}] {a["title"]}: {a["content"]}' for a in data['assumptions'])
    return '\n\n'.join(parts)
