import re
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models as m

CATEGORIES = ['overview', 'industry', 'customers', 'business_model', 'products', 'metrics', 'technology', 'compliance', 'principles', 'terminology', 'rules', 'open_questions']


def record(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class ContextRetriever(Protocol):
    def get_context(self, organization_id: str, product_id: str | None, query: str, categories: list[str]) -> dict: ...


class RulesContextRetriever:
    def __init__(self, db: Session):
        self.db = db

    def get_context(self, organization_id, product_id, query, categories):
        org = self.db.get(m.Organization, organization_id)
        product = self.db.get(m.Product, product_id) if product_id else None
        if not org or (product and product.organization_id != organization_id):
            raise ValueError('Product does not belong to organization')
        tokens = set(re.findall(r'\w+', query.lower())) - {'the', 'and', 'for', 'with', 'that'}
        items = self.db.scalars(select(m.OrganizationContextItem).where(m.OrganizationContextItem.organization_id == organization_id, m.OrganizationContextItem.status != 'rejected')).all()
        def rank(item):
            matches = len(tokens & set(re.findall(r'\w+', (item.title + ' ' + item.content).lower())))
            return (item.status == 'confirmed', matches)
        relevant = [i for i in items if i.category in {'overview', 'principles', 'compliance'} | set(categories) or tokens & set(re.findall(r'\w+', (i.title + ' ' + i.content).lower()))]
        chosen = sorted(relevant, key=rank, reverse=True)[:18] if org.blueprint_validated else []
        rules = self.db.scalars(select(m.OrganizationRule).where(m.OrganizationRule.organization_id == organization_id)).all()
        product_items = self.db.scalars(select(m.ProductContextItem).where(m.ProductContextItem.product_id == product_id, m.ProductContextItem.status != 'rejected')).all() if product else []
        return {'organization': {'id': org.id, 'name': org.name, 'description': org.description}, 'items': [{'id': i.id, 'category': i.category, 'title': i.title, 'content': i.content, 'status': i.status, 'source': i.source, 'confidence': i.confidence} for i in chosen], 'product': {k: v for k, v in record(product).items() if k not in ('created_at', 'updated_at')} if product else None, 'product_items': [{'title': i.title, 'content': i.content, 'status': i.status} for i in product_items[:12]], 'rules': [{'id': r.id, 'kind': r.kind, 'content': r.content} for r in rules]}


def maturity(items):
    result = {}
    for category in CATEGORIES[:-1]:
        group = [i for i in items if i.category == category and i.status != 'rejected']
        result[category] = 'complete' if any(i.status == 'confirmed' and i.content.strip() for i in group) else 'partial' if any(i.status == 'assumed' and i.content.strip() for i in group) else 'missing'
    return {'overall': round(sum({'complete': 1, 'partial': .5, 'missing': 0}[v] for v in result.values()) / len(result) * 100), 'categories': result}
