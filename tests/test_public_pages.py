"""Unauthenticated store-listing resources, including a path without the app."""

from html.parser import HTMLParser

import pytest


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("path", ["/privacy", "/privacidad", "/delete-account", "/eliminar-cuenta"])
async def test_public_pages_are_complete_responsive_html_without_auth(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    html = response.text
    assert html.lower().startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert "__CONTENT__" not in html and "__TITLE__" not in html
    assert "Fluilet" in html and "fluilet123@gmail.com" in html
    assert (
        "Inicio → 🛡️ Cuenta, privacidad y eliminación de datos → Eliminar mi cuenta y datos" in html
    )
    assert "Cuenta y privacidad" not in html
    assert "@media" in html and "no-store" in response.headers["cache-control"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    markup = Markup()
    markup.feed(html)
    assert ("html", {"lang": "es"}) in markup.tags
    assert any(t == "meta" and a.get("name") == "viewport" for t, a in markup.tags)
    assert any(t == "main" and a.get("id") == "contenido" for t, a in markup.tags)
    assert sum(t == "h1" for t, _ in markup.tags) == 1
    assert not any(t in {"script", "iframe", "img"} for t, _ in markup.tags)
    for _, attributes in markup.tags:
        for name in ("src", "href"):
            assert not attributes.get(name, "").startswith(("http:", "https:", "//"))


async def test_privacy_aliases_describe_actual_retention_and_technical_processors(client):
    page = await client.get("/privacy")
    assert page.content == (await client.get("/privacidad")).content
    for phrase in (
        "responsable del tratamiento",
        "TDAH",
        "dislexia",
        "fecha de nacimiento",
        "texto original",
        "no vende",
        "DigitalOcean",
        "Brevo",
        "hash",
        "únicamente código",
    ):
        assert phrase in page.text
    assert "no conserva dumps" in page.text


async def test_deletion_aliases_offer_direct_email_request_without_reinstalling(client):
    page = await client.get("/delete-account")
    assert page.content == (await client.get("/eliminar-cuenta")).content
    for phrase in (
        "Inicio → 🛡️ Cuenta, privacidad y eliminación de datos → Eliminar mi cuenta y datos",
        "inmediata y permanente",
        "Historial de lectura",
        "Adaptaciones guardadas",
        "Progreso y métricas",
        "sin volver a instalar",
        "verificará la titularidad",
        "no es una confirmación automática",
        "únicamente datos de ejemplo iniciales",
    ):
        assert phrase in page.text
    markup = Markup()
    markup.feed(page.text)
    assert any(
        tag == "a" and attrs.get("href", "").startswith("mailto:fluilet123@gmail.com?subject=")
        for tag, attrs in markup.tags
    )
