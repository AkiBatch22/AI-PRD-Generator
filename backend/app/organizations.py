from io import BytesIO
from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlalchemy import select
from pypdf import PdfReader
from . import models as m, schemas as s
from .deps import DB, organization, product, get_record, DEMO_USER_ID
from .context import record, maturity, RulesContextRetriever
from .workflows import OrganizationContextService, DiscoveryHelpService

router = APIRouter()


@router.get('/organizations')
def organizations(db: DB):
    return [record(o) for o in db.scalars(select(m.Organization).where(m.Organization.owner_id == DEMO_USER_ID).order_by(m.Organization.created_at))]


@router.post('/organizations', status_code=201)
def create_organization(data: s.OrganizationIn, db: DB):
    org = m.Organization(**data.model_dump(), owner_id=DEMO_USER_ID)
    db.add(org)
    db.flush()
    return record(org)


@router.get('/organizations/{id}')
def get_organization(id: str, db: DB):
    org = organization(db, id)
    items = db.scalars(select(m.OrganizationContextItem).where(m.OrganizationContextItem.organization_id == id)).all()
    return {**record(org), 'maturity': maturity(items)}


@router.get('/organizations/{id}/context')
def list_context(id: str, db: DB):
    organization(db, id)
    return [record(i) for i in db.scalars(select(m.OrganizationContextItem).where(m.OrganizationContextItem.organization_id == id).order_by(m.OrganizationContextItem.created_at))]


@router.post('/organizations/{id}/context', status_code=201)
def add_context(id: str, data: s.ContextIn, db: DB):
    organization(db, id)
    item = m.OrganizationContextItem(organization_id=id, **data.model_dump())
    db.add(item)
    db.flush()
    return record(item)


@router.patch('/organizations/{id}/context/{item_id}')
def update_context(id: str, item_id: str, data: s.ContextPatch, db: DB):
    organization(db, id)
    item = get_record(db, m.OrganizationContextItem, item_id)
    if item.organization_id != id:
        raise HTTPException(404, 'Context item not found')
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    if item.status == 'confirmed' and not item.content.strip():
        raise HTTPException(422, 'Confirmed facts need content')
    db.flush()
    return record(item)


@router.delete('/organizations/{id}/context/{item_id}', status_code=204)
def delete_context(id: str, item_id: str, db: DB):
    organization(db, id)
    item = get_record(db, m.OrganizationContextItem, item_id)
    if item.organization_id != id:
        raise HTTPException(404, 'Context item not found')
    for assumption in db.scalars(select(m.Assumption).where(m.Assumption.promoted_context_id == item_id)):
        assumption.promoted_context_id = None
    db.delete(item)


@router.post('/organizations/{id}/validate')
def validate_blueprint(id: str, db: DB):
    org = organization(db, id)
    items = db.scalars(select(m.OrganizationContextItem).where(m.OrganizationContextItem.organization_id == id)).all()
    if not any(i.status == 'confirmed' and i.content.strip() for i in items):
        raise HTTPException(409, 'Confirm at least one context item before validating the blueprint')
    org.blueprint_validated = True
    db.flush()
    return record(org)


@router.get('/organizations/{id}/rules')
def list_rules(id: str, db: DB):
    organization(db, id)
    return [record(r) for r in db.scalars(select(m.OrganizationRule).where(m.OrganizationRule.organization_id == id))]


@router.post('/organizations/{id}/rules', status_code=201)
def add_rule(id: str, data: s.RuleIn, db: DB):
    organization(db, id)
    rule = m.OrganizationRule(organization_id=id, **data.model_dump())
    db.add(rule)
    db.flush()
    return record(rule)


@router.delete('/organizations/{id}/rules/{rule_id}', status_code=204)
def delete_rule(id: str, rule_id: str, db: DB):
    organization(db, id)
    rule = get_record(db, m.OrganizationRule, rule_id)
    if rule.organization_id != id:
        raise HTTPException(404, 'Rule not found')
    db.delete(rule)


async def ingest(id, data, db, media_type='text/plain'):
    organization(db, id)
    output = await OrganizationContextService().run({'text': data.text})
    doc = m.SourceDocument(organization_id=id, name=data.name, content=data.text, media_type=media_type)
    db.add(doc)
    for candidate in output.items:
        values = candidate.model_dump()
        values.update(source='document', status='unknown' if candidate.status == 'unknown' else 'assumed')
        db.add(m.OrganizationContextItem(organization_id=id, **values))
    db.flush()
    return {'document_id': doc.id, 'candidates': len(output.items)}


@router.post('/organizations/{id}/import')
async def import_text(id: str, data: s.ExtractIn, db: DB):
    return await ingest(id, data, db)


@router.post('/organizations/{id}/documents')
async def upload(id: str, db: DB, file: UploadFile = File(...)):
    organization(db, id)
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Files must be 5 MB or smaller')
    name = file.filename or 'document.txt'
    try:
        if name.lower().endswith('.pdf'):
            reader = PdfReader(BytesIO(raw))
            if len(reader.pages) > 100:
                raise HTTPException(413, 'PDFs must have 100 pages or fewer')
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif name.lower().endswith(('.md', '.txt')):
            text = raw.decode('utf-8')
        else:
            raise HTTPException(415, 'Use a text, Markdown, or PDF document')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'Unable to extract text from this document')
    if not text.strip() or len(text) > 100000:
        raise HTTPException(422, 'Document needs extractable text, at most 100,000 characters')
    return await ingest(id, s.ExtractIn(text=text, name=name), db, file.content_type or 'text/plain')


@router.post('/organizations/{id}/help')
async def discovery_help(id: str, data: s.HelpIn, db: DB):
    organization(db, id)
    return await DiscoveryHelpService().run(data.model_dump())


@router.get('/products')
def products(organization_id: str, db: DB):
    organization(db, organization_id)
    return [record(p) for p in db.scalars(select(m.Product).where(m.Product.organization_id == organization_id))]


@router.post('/products', status_code=201)
def add_product(data: s.ProductIn, db: DB):
    org = organization(db, data.organization_id)
    if not org.blueprint_validated:
        raise HTTPException(409, 'Validate the company blueprint first')
    obj = m.Product(**data.model_dump())
    db.add(obj)
    db.flush()
    return record(obj)


@router.get('/products/{id}')
def get_product(id: str, db: DB):
    return record(product(db, id))


@router.put('/products/{id}')
def edit_product(id: str, data: s.ProductIn, db: DB):
    obj = product(db, id)
    if obj.organization_id != data.organization_id:
        raise HTTPException(422, 'Cannot move a product between organizations')
    for key, value in data.model_dump().items():
        setattr(obj, key, value)
    db.flush()
    return record(obj)


@router.get('/products/{id}/context')
def product_context(id: str, db: DB, query: str = ''):
    p = product(db, id)
    return RulesContextRetriever(db).get_context(p.organization_id, id, query, ['industry', 'customers', 'metrics', 'technology'])
