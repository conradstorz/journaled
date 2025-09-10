from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from loguru import logger
from ..models import Check, CheckStatus
from .reversal import create_reversing_entry

def void_check(db: Session, check_id: int, reversal_date: date, memo: str | None = None, create_reversal: bool = True) -> None:
    chk = db.get(Check, check_id)
    if not chk:
        raise ValueError(f"Check {check_id} not found")
    if chk.status == CheckStatus.VOID:
        logger.info(f"Check {check_id} already void")
        return
    chk.status = CheckStatus.VOID
    db.add(chk)
    db.flush()
    if create_reversal and chk.transaction_id:
        create_reversing_entry(db, chk.transaction_id, reversal_date, memo or f"Void check {chk.check_no}")
    db.commit()
    logger.success(f"Voided check {check_id}")
