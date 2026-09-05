from typing import Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict, StringConstraints

Status = Literal['confirmed', 'assumed', 'unknown', 'rejected']
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Category = Literal['overview', 'industry', 'customers', 'business_model', 'products', 'metrics', 'technology', 'compliance', 'principles', 'terminology', 'rules', 'open_questions']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class OrganizationIn(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default='', max_length=20000)
    mode: Literal['established', 'limited', 'greenfield'] = 'established'


class ContextIn(StrictModel):
    category: Category
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=20000)
    status: Status = 'unknown'
    source: Literal['user', 'ai', 'document', 'prd', 'system'] = 'user'
    confidence: float = Field(default=0, ge=0, le=1)


class ContextPatch(StrictModel):
    content: str | None = Field(default=None, max_length=20000)
    status: Status | None = None


class RuleIn(StrictModel):
    kind: Literal['must', 'must_not']
    content: str = Field(min_length=3, max_length=2000)


class ProductIn(StrictModel):
    organization_id: str
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default='', max_length=10000)
    users: str = ''
    primary_goal: str = ''
    current_user_journey: str = ''
    major_features: str = ''
    business_metrics: str = ''
    constraints: str = ''
    technical_context: str = ''


class PRDIn(StrictModel):
    product_id: str
    title: str = Field(min_length=1, max_length=200)
    idea: str = Field(min_length=10, max_length=20000)
    ai_relevant: bool = False


class QuestionSpec(StrictModel):
    question: str
    reason: str
    category: str
    required: bool = True


class DiscoveryOutput(StrictModel):
    questions: list[QuestionSpec] = Field(min_length=3, max_length=7)


class AnswerIn(StrictModel):
    answer: str = Field(default='', max_length=20000)
    status: Literal['answered', 'unknown', 'skipped']


class AssumptionSpec(StrictModel):
    title: str
    content: str
    status: Literal['assumed', 'unknown']


class BriefContent(StrictModel):
    problem_statement: str
    target_users: str
    current_user_journey: str
    proposed_solution: str
    value_proposition: str
    goals: list[str]
    non_goals: list[str]
    assumptions: list[AssumptionSpec]
    open_questions: list[str]
    constraints: list[str]
    dependencies: list[str]
    success_metrics: list[str]


class RequirementSpec(StrictModel):
    requirement_code: str = Field(pattern=r'^[A-Z]+-\d{2,3}$')
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    type: Literal['functional', 'non_functional', 'data', 'ai_ml', 'analytics', 'security', 'compliance']
    priority: Literal['must', 'should', 'could', 'wont']
    acceptance_criteria: list[NonEmptyText] = Field(min_length=1)
    dependencies: list[NonEmptyText]
    edge_cases: list[NonEmptyText]


class AIBehavior(StrictModel):
    capability: str
    input: list[str]
    output: list[str]
    allowed_behavior: list[str]
    prohibited_behavior: list[str]
    confidence_behavior: str
    fallback_behavior: str
    human_review_requirements: str
    explainability_requirements: str
    evaluation_metrics: list[str]
    failure_modes: list[str]


class RequirementsOutput(StrictModel):
    requirements: list[RequirementSpec] = Field(min_length=1, max_length=40)
    ai_behavior: AIBehavior | None = None


class PRDOutput(StrictModel):
    executive_summary: str
    background: str
    user_stories: list[str]
    risks_and_mitigations: list[str]
    rollout_plan: list[str]


class IssueSpec(StrictModel):
    severity: Literal['info', 'warning', 'critical']
    category: str
    title: str
    description: str
    affected_section: str
    current_text: str
    suggested_change: str


class CriticOutput(StrictModel):
    issues: list[IssueSpec]


class ContextOutput(StrictModel):
    items: list[ContextIn] = Field(max_length=40)


class ExtractIn(StrictModel):
    text: str = Field(min_length=1, max_length=100000)
    name: str = Field(default='Pasted documentation', max_length=200)


class HelpIn(StrictModel):
    stage: str = Field(min_length=1, max_length=100)
    idea: str = Field(max_length=20000)


class HelpOutput(StrictModel):
    suggestion: str
    rationale: str


class IssueAction(StrictModel):
    action: Literal['accept', 'edit', 'ignore']
    replacement: str | None = Field(default=None, max_length=20000)
