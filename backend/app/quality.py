import re
from .schemas import IssueSpec


def meaningful(text):
    return bool(text and str(text).strip() and not re.search(r'unknown|not decided|unresolved|not yet', str(text), re.I))


def measurable(text):
    return meaningful(text) and bool(re.search(r'\d', text)) and bool(re.search(r'%|seconds?|minutes?|hours?|days?|weeks?|months?|rate|score|CSAT|ms\b', text, re.I))


def issue(category, title, section, current='', suggestion='', severity='warning'):
    return IssueSpec(severity=severity, category=category, title=title, description=title, affected_section=section, current_text=current, suggested_change=suggestion)


def evaluate_rules(rules, sections, requirements):
    """Conservative deterministic checks; arbitrary prose rules require human review."""
    issues = []
    text = ' '.join(str(v) for k, v in sections.items() if k not in {'constraints', 'background', 'assumptions', 'open_questions'}).lower()
    text += ' ' + ' '.join(r.description.lower() for r in requirements)
    for rule in rules:
        content = rule.content.lower()
        if rule.kind == 'must_not' and 'guarantee' in content and 'approval' in content:
            if re.search(r'(?<!not )(?<!never )(?<!cannot )guarantee(?:s|d)? (?:loan )?approval', text):
                issues.append(issue('organization_rule', 'Potential loan approval guarantee: ' + rule.content, 'proposed_solution', sections.get('proposed_solution', ''), severity='critical'))
        elif rule.kind == 'must' and 'analytics' in content:
            if not any(r.type == 'analytics' for r in requirements):
                issues.append(issue('organization_rule', 'Missing analytics requirement: ' + rule.content, 'requirements', severity='critical'))
        elif rule.kind == 'must' and 'explain' in content:
            if 'ai' in content and not sections.get('ai_behavior') and not any(r.type == 'ai_ml' for r in requirements):
                continue
            if not any(re.search(r'explain|explanation', str(r.acceptance_criteria), re.I) for r in requirements):
                issues.append(issue('organization_rule', 'Explainability is not testable: ' + rule.content, 'requirements', severity='critical'))
        else:
            issues.append(issue('rule_attestation', 'Verify organization rule: ' + rule.content, 'requirements', severity='warning'))
    return issues


def deterministic_review(prd, brief, requirements, assumptions, rules):
    issues = evaluate_rules(rules, prd.sections, requirements)
    for metric in brief.get('success_metrics', []):
        if not measurable(metric):
            issues.append(issue('metrics', 'Define a metric with a numeric target and measurement window', 'success_metrics', metric))
    for req in requirements:
        if not req.acceptance_criteria:
            issues.append(issue('acceptance_criteria', f'{req.requirement_code} has no acceptance criteria', 'requirements', severity='critical'))
        if not req.edge_cases:
            issues.append(issue('edge_cases', f'{req.requirement_code} has no edge cases', 'requirements'))
        if any(not meaningful(d) for d in req.dependencies):
            issues.append(issue('dependencies', f'{req.requirement_code} depends on an unresolved service or data source', 'requirements'))
    for a in assumptions:
        if a.status in {'assumed', 'unknown'}:
            issues.append(issue('assumption', 'Unvalidated: ' + a.title, 'assumptions', a.content))
    if brief.get('open_questions'):
        issues.append(issue('open_questions', 'Discovery still contains unresolved questions', 'open_questions'))
    if prd.ai_relevant and not prd.sections.get('ai_behavior', {}).get('fallback_behavior'):
        issues.append(issue('ai_safety', 'AI fallback behavior is missing', 'ai_behavior', severity='critical'))
    return issues


def quality_score(prd, brief, requirements, assumptions, issues):
    coverage = lambda field: round(100 * sum(bool(getattr(r, field)) for r in requirements) / len(requirements)) if requirements else 0
    metrics = brief.get('success_metrics', [])
    breakdown = {'problem_clarity': 100 if meaningful(brief.get('problem_statement')) else 0, 'user_definition': 100 if meaningful(brief.get('target_users')) else 0, 'scope': 50 * bool(brief.get('goals') and all(meaningful(g) for g in brief['goals'])) + 50 * bool(brief.get('non_goals')), 'requirements': coverage('acceptance_criteria'), 'success_metrics': round(100 * sum(measurable(v) for v in metrics) / len(metrics)) if metrics else 0, 'edge_cases': coverage('edge_cases'), 'risk_coverage': 100 if prd.sections.get('risks_and_mitigations') else 0, 'assumptions': max(0, 100 - 20 * sum(a.status in {'assumed', 'unknown'} for a in assumptions)), 'organization_rules': max(0, 100 - 25 * sum(i.category in {'organization_rule', 'rule_attestation'} and i.status == 'open' for i in issues))}
    if prd.ai_relevant:
        breakdown['ai_fallback'] = 100 if prd.sections.get('ai_behavior', {}).get('fallback_behavior') else 0
    return {'overall': round(sum(breakdown.values()) / len(breakdown)), 'breakdown': breakdown, 'issues': sum(i.status == 'open' for i in issues)}
