"""Public, script-free privacy resources; no credentials or tracking assets."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.config import settings

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


@router.get("/install", response_class=HTMLResponse)
@router.head("/install", response_class=HTMLResponse, include_in_schema=False)
@router.get("/instalar", response_class=HTMLResponse, include_in_schema=False)
@router.head("/instalar", response_class=HTMLResponse, include_in_schema=False)
def install():
    return page("install.html", "Instalar Fluilet")


@router.get("/descargar/fluilet.apk", response_class=FileResponse)
@router.head("/descargar/fluilet.apk", response_class=FileResponse, include_in_schema=False)
def download_apk():
    path = Path(os.environ.get("FLUILET_APK_PATH", settings.FLUILET_APK_PATH))
    if not path.is_file():
        raise HTTPException(404, "El APK de Fluilet no está disponible.")
    # PrivacyMiddleware adds nosniff to both GET and HEAD, as for other routes.
    return FileResponse(
        path, media_type="application/vnd.android.package-archive", filename="fluilet.apk"
    )
