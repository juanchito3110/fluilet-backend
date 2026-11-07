"""Permanent account deletion; the caller owns the transaction and row lock."""

from fastapi import HTTPException
from sqlalchemy import delete, select

from app import models


async def erase_account(user, db):
    """Use database cascades, including child logins that are separate users.

    Do not commit here: deleting the parent and its linked child accounts must
    either succeed together or be rolled back together. Bulk DELETE avoids ORM
    relationships setting nullable document references instead of cascading.
    """
    if user.email.casefold() == "admin@fluilet.com":
        raise HTTPException(403, "La cuenta maestra del administrador no puede eliminarse.")
    linked = list(
        (
            await db.scalars(
                select(models.ChildProfile.user_id).where(
                    models.ChildProfile.tutor_id == user.id,
                    models.ChildProfile.user_id.is_not(None),
                )
            )
        ).all()
    )
    await db.execute(delete(models.User).where(models.User.id == user.id))
    if linked:
        await db.execute(
            delete(models.User).where(
                models.User.id.in_(linked), models.User.role == models.UserRole.NINO
            )
        )
