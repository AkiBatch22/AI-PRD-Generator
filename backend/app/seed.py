from sqlalchemy import select
from . import models as m
from .deps import DEMO_USER_ID
from .context import RulesContextRetriever


def seed(db, demo=True):
    if not db.get(m.User, DEMO_USER_ID):
        db.add(m.User(id=DEMO_USER_ID, name='Demo user', email='demo@example.test'))
        db.flush()
    if not demo or db.scalar(select(m.Organization).limit(1)):
        return
    org = m.Organization(name='FinEdge', owner_id=DEMO_USER_ID, description='A fictional consumer lending company helping people understand their borrowing readiness.', mode='established', blueprint_validated=True)
    db.add(org)
    db.flush()
    for category, title, content, status in [('overview', 'Company mission', 'Make borrowing decisions clearer and more informed.', 'confirmed'), ('industry', 'Industry & market', 'Consumer lending / FinTech · India', 'confirmed'), ('customers', 'Primary customers', 'First-time borrowers in India', 'confirmed'), ('business_model', 'Revenue model', 'Lender referral commissions may fund the marketplace.', 'assumed'), ('products', 'Product portfolio', 'Consumer Loan Marketplace and Credit Readiness Engine', 'confirmed'), ('metrics', 'Business outcomes', 'Readiness assessment completion rate', 'confirmed'), ('technology', 'Application stack', 'Technical architecture needs validation.', 'unknown'), ('compliance', 'Financial information', 'Treat personal and financial information as sensitive.', 'confirmed'), ('principles', 'User control', 'Explain recommendations and keep the user in control.', 'confirmed'), ('terminology', 'Readiness', 'Readiness is an educational indicator, not credit approval.', 'confirmed')]:
        db.add(m.OrganizationContextItem(organization_id=org.id, category=category, title=title, content=content, status=status, source='system', confidence=1 if status == 'confirmed' else .3))
    for kind, content in [('must_not', 'Never guarantee loan approval'), ('must', 'AI recommendations must be explainable'), ('must_not', 'Sensitive financial information cannot be logged'), ('must', 'Every feature requires analytics events')]:
        db.add(m.OrganizationRule(organization_id=org.id, kind=kind, content=content))
    product = m.Product(organization_id=org.id, name='Consumer Loan Marketplace', description='Help borrowers explore lending options with clear eligibility information.', users='First-time home buyers in India', primary_goal='Help users understand borrowing readiness', current_user_journey='Compare lender websites, collect documents, and request eligibility checks.', business_metrics='Readiness assessment completion rate', constraints='No approval guarantees')
    db.add(product)
    db.add(m.Product(organization_id=org.id, name='Credit Readiness Engine', description='Explain the factors affecting borrowing readiness.', users='Prospective borrowers', primary_goal='Make readiness understandable'))
    db.flush()
    p = m.PRD(product_id=product.id, title='Home Loan Readiness Score', idea='Build an AI readiness assessment that explains the factors affecting home loan eligibility without guaranteeing approval.', ai_relevant=True, status='draft', context_snapshot=RulesContextRetriever(db).get_context(org.id, product.id, 'home loan AI readiness', ['industry', 'customers', 'metrics']))
    db.add(p)
    db.commit()
