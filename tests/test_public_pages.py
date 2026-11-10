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
    assert "Inicio → Cuenta, privacidad y eliminación de datos → Eliminar mi cuenta y datos" in html
    assert "Cuenta y privacidad" not in html
    assert "Inicio → 🛡️" not in html
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
        "Inicio → Cuenta, privacidad y eliminación de datos → Eliminar mi cuenta y datos",
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


class InstallLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = (dict(attrs), [])

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            attrs, parts = self.current
            self.links[" ".join("".join(parts).split())] = attrs
            self.current = None


@pytest.mark.parametrize("path", ["/instalar", "/install"])
async def test_install_pages_are_complete_html_with_the_existing_csp(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    for notice in (
        "Join group",
        "No tienes permiso",
        "descárgala en Google Play",
        "No se encontró el elemento",
    ):
        assert notice in response.text
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.text.lower().startswith("<!doctype html>")
    assert response.text.rstrip().endswith("</html>")
    markup = Markup()
    markup.feed(response.text)
    assert ("html", {"lang": "es"}) in markup.tags
    assert any(tag == "meta" and attrs.get("name") == "viewport" for tag, attrs in markup.tags)
    assert sum(tag == "h1" for tag, _ in markup.tags) == 1
    assert not any(tag in {"script", "iframe", "img"} for tag, _ in markup.tags)
    assert any(tag == "svg" for tag, _ in markup.tags)
    assert any(tag == "a" and attrs.get("href") == "/instalar" for tag, attrs in markup.tags)


@pytest.mark.parametrize("path", ["/instalar", "/install"])
async def test_install_buttons_keep_the_approved_labels_and_destinations(client, path):
    page = await client.get(path)
    markup = InstallLinks()
    markup.feed(page.text)
    for label, destination in (
        ("1. Habilitar acceso en Google Groups", "https://groups.google.com/g/evaluadores-fluilet"),
        (
            "2. Confirmar acceso en Google Play",
            "https://play.google.com/apps/testing/com.fluilet.app",
        ),
    ):
        attrs = markup.links[label]
        assert attrs["href"] == destination
        assert attrs["target"] == "_blank" and "noopener" in attrs["rel"].split()
    native = markup.links["Abrir ficha en pantalla completa en Google Play"]
    assert native["href"] == "market://details?id=com.fluilet.app"
    assert "target" not in native
    labels = list(markup.links)
    assert labels.index("Abrir ficha en pantalla completa en Google Play") == (
        labels.index("2. Confirmar acceso en Google Play") + 1
    )
    assert markup.links["Descargar APK directo"]["href"] == "/descargar/fluilet.apk"


@pytest.mark.parametrize("path", ["/instalar", "/install"])
async def test_install_page_head_supports_qr_link_probes(client, path):
    head = await client.head(path)
    get = await client.get(path)
    assert head.status_code == 200 and head.content == b""
    for header in ("content-type", "content-length", "content-security-policy"):
        assert head.headers[header] == get.headers[header]


@pytest.mark.parametrize("method", ["GET", "HEAD"])
async def test_apk_download_streams_the_configured_file(client, tmp_path, monkeypatch, method):
    payload = b"PK\x03\x04Fluilet APK test bytes\x00\xff"
    apk = tmp_path / "release.apk"
    apk.write_bytes(payload)
    monkeypatch.setenv("FLUILET_APK_PATH", str(apk))
    response = await client.request(method, "/descargar/fluilet.apk")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert response.headers["content-disposition"] == 'attachment; filename="fluilet.apk"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert int(response.headers["content-length"]) == len(payload)
    assert response.content == (payload if method == "GET" else b"")


@pytest.mark.parametrize("method", ["GET", "HEAD"])
async def test_missing_apk_is_a_controlled_404(client, tmp_path, monkeypatch, method):
    path = tmp_path / "missing.apk"
    monkeypatch.setenv("FLUILET_APK_PATH", str(path))
    response = await client.request(method, "/descargar/fluilet.apk")
    assert response.status_code == 404
    assert str(path) not in response.text


async def test_apk_download_does_not_serve_a_directory(client, tmp_path, monkeypatch):
    monkeypatch.setenv("FLUILET_APK_PATH", str(tmp_path))
    assert (await client.get("/descargar/fluilet.apk")).status_code == 404
