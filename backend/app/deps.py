from typing import Annotated
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .db import get_db
from . import models as m

DB = Annotated[Session, Depends(get_db)]
DEMO_USER_ID = 'demo-user'


def get_record(db, model, id):
    obj = db.get(model, id)
    if not obj:
        raise HTTPException(404, 'Record not found')
    return obj


def organization(db, id):
    obj = get_record(db, m.Organization, id)
    if obj.owner_id != DEMO_USER_ID:
        raise HTTPException(404, 'Organization not found')
    return obj


def product(db, id):
    obj = get_record(db, m.Product, id)
    organization(db, obj.organization_id)
    return obj


def prd_record(db, id):
    obj = get_record(db, m.PRD, id)
    product(db, obj.product_id)
    return obj


def require_state(prd, *states):
    if prd.status not in states:
        raise HTTPException(409, f'Action requires {", ".join(states)}; current state is {prd.status}')
