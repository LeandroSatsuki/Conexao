from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.integrations.validator import validate_transformation_rule
from app.models.field_mapping import FieldMapping
from app.schemas.field_mapping import FieldMappingRead, FieldMappingUpdate

router = APIRouter(prefix="/mappings", tags=["mappings"])


def _mapping_to_read(mapping: FieldMapping) -> FieldMappingRead:
    return FieldMappingRead.model_validate(mapping)


@router.patch("/{mapping_id}", response_model=FieldMappingRead)
def update_mapping(mapping_id: str, payload: FieldMappingUpdate, db: Session = Depends(get_db)) -> FieldMappingRead:
    mapping = db.get(FieldMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")

    changes = payload.model_dump(exclude_unset=True)
    if "transformation_rule" in changes:
        validate_transformation_rule(changes["transformation_rule"])

    for field_name, value in changes.items():
        setattr(mapping, field_name, value)

    db.commit()
    db.refresh(mapping)
    return _mapping_to_read(mapping)


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping(mapping_id: str, db: Session = Depends(get_db)) -> None:
    mapping = db.get(FieldMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    db.delete(mapping)
    db.commit()
