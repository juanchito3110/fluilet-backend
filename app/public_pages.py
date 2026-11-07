"""Public, script-free privacy resources; no credentials or tracking assets."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["privacy"])
_TEMPLATES = Path(__file__).with_name("templates")
_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
}


def page(name, title):
    layout = (_TEMPLATES / "public_base.html").read_text(encoding="utf-8")
    content = (_TEMPLATES / name).read_text(encoding="utf-8")
    return HTMLResponse(
        layout.replace("__TITLE__", title).replace("__CONTENT__", content), headers=_HEADERS
    )


@router.get("/privacy", response_class=HTMLResponse)
@router.get("/privacidad", response_class=HTMLResponse, include_in_schema=False)
def privacy_policy():
    return page("privacy.html", "Política de privacidad")


@router.get("/delete-account", response_class=HTMLResponse)
@router.get("/eliminar-cuenta", response_class=HTMLResponse, include_in_schema=False)
def account_deletion():
    return page("delete_account.html", "Eliminar mi cuenta y datos")
