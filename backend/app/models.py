from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base, Record


class User(Record, Base):
    __tablename__ = 'users'
    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)


class Organization(Record, Base):
    __tablename__ = 'organizations'
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str]
    description: Mapped[str] = mapped_column(default='')
    mode: Mapped[str] = mapped_column(default='established')
    blueprint_validated: Mapped[bool] = mapped_column(default=False)
    products: Mapped[list['Product']] = relationship(back_populates='organization')
    context_items: Mapped[list['OrganizationContextItem']] = relationship()


class ContextFields:
    category: Mapped[str]
    title: Mapped[str]
    content: Mapped[str]
    status: Mapped[str] = mapped_column(default='unknown')
    source: Mapped[str] = mapped_column(default='user')
    confidence: Mapped[float] = mapped_column(default=0)


class OrganizationContextItem(Record, ContextFields, Base):
    __tablename__ = 'organization_context'
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)


class OrganizationRule(Record, Base):
    __tablename__ = 'organization_rules'
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    kind: Mapped[str]
    content: Mapped[str]


class Product(Record, Base):
    __tablename__ = 'products'
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    name: Mapped[str]
    description: Mapped[str]
    users: Mapped[str] = mapped_column(default='')
    primary_goal: Mapped[str] = mapped_column(default='')
    current_user_journey: Mapped[str] = mapped_column(default='')
    major_features: Mapped[str] = mapped_column(default='')
    business_metrics: Mapped[str] = mapped_column(default='')
    constraints: Mapped[str] = mapped_column(default='')
    technical_context: Mapped[str] = mapped_column(default='')
    organization: Mapped[Organization] = relationship(back_populates='products')
    context_items: Mapped[list['ProductContextItem']] = relationship()


class ProductContextItem(Record, ContextFields, Base):
    __tablename__ = 'product_context'
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), index=True)


class SourceDocument(Record, Base):
    __tablename__ = 'source_documents'
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'))
    name: Mapped[str]
    content: Mapped[str]
    media_type: Mapped[str]


class PRD(Record, Base):
    __tablename__ = 'prds'
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), index=True)
    title: Mapped[str]
    idea: Mapped[str]
    status: Mapped[str] = mapped_column(default='draft')
    ai_relevant: Mapped[bool] = mapped_column(default=False)
    sections: Mapped[dict] = mapped_column(JSON, default=dict)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    requirements: Mapped[list['Requirement']] = relationship()
    questions: Mapped[list['DiscoveryQuestion']] = relationship()


class DiscoveryQuestion(Record, Base):
    __tablename__ = 'discovery_questions'
    prd_id: Mapped[str] = mapped_column(ForeignKey('prds.id'), index=True)
    question: Mapped[str]
    reason: Mapped[str]
    category: Mapped[str]
    required: Mapped[bool] = mapped_column(default=True)
    answer: Mapped[str] = mapped_column(default='')
    status: Mapped[str] = mapped_column(default='unanswered')


class ProductBrief(Record, Base):
    __tablename__ = 'product_briefs'
    prd_id: Mapped[str] = mapped_column(ForeignKey('prds.id'), unique=True)
    content: Mapped[dict] = mapped_column(JSON)
    approved: Mapped[bool] = mapped_column(default=False)


class Requirement(Record, Base):
    __tablename__ = 'requirements'
    __table_args__ = (UniqueConstraint('prd_id', 'requirement_code'),)
    prd_id: Mapped[str] = mapped_column(ForeignKey('prds.id'), index=True)
    requirement_code: Mapped[str]
    title: Mapped[str]
    description: Mapped[str]
    type: Mapped[str]
    priority: Mapped[str]
    status: Mapped[str] = mapped_column(default='proposed')
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    edge_cases: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(default='ai')


class Assumption(Record, Base):
    __tablename__ = 'assumptions'
    prd_id: Mapped[str] = mapped_column(ForeignKey('prds.id'), index=True)
    title: Mapped[str]
    content: Mapped[str]
    status: Mapped[str] = mapped_column(default='assumed')
    source: Mapped[str] = mapped_column(default='ai')
    promoted_context_id: Mapped[str | None] = mapped_column(ForeignKey('organization_context.id'), nullable=True)


class ReviewIssue(Record, Base):
    __tablename__ = 'review_issues'
    prd_id: Mapped[str] = mapped_column(ForeignKey('prds.id'), index=True)
    severity: Mapped[str]
    category: Mapped[str]
    title: Mapped[str]
    description: Mapped[str]
    affected_section: Mapped[str]
    current_text: Mapped[str]
    suggested_change: Mapped[str]
    status: Mapped[str] = mapped_column(default='open')
