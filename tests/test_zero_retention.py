import io
import tempfile

from sqlalchemy import event, func, select

from app import models
from app.config import settings
from tests.conftest import SOURCE


async def test_only_metadata_in_sql_and_duplicate_telemetry_is_upserted(
    client, db, make_user, caplog
):
    _, headers, _ = await make_user()
    captured = []

    def record(connection, cursor, statement, parameters, context, executemany):
        captured.append(repr(parameters))

    event.listen(db.bind.sync_engine, "before_cursor_execute", record)
    try:
        first = await client.post(
            "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE}
        )
        assert first.status_code == 200, first.text
        second = await client.post(
            "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE}
        )
        assert second.status_code == 200
        assert first.json()["document"]["id"] == second.json()["document"]["id"]
        assert await db.scalar(select(func.count()).select_from(models.Document)) == 1
        assert await db.scalar(select(func.count()).select_from(models.AdaptationChunk)) == 1
        assert SOURCE not in "\n".join(captured) and SOURCE not in caplog.text
        assert first.json()["adapted_text"] not in "\n".join(captured)
        forbidden = {"text", "original_text", "adapted_text", "storage_path", "file_name"}
        assert not any(
            forbidden & set(table.columns.keys()) for table in models.Base.metadata.tables.values()
        )
        assert first.headers["cache-control"] == "no-store"
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", record)


async def test_failed_adaptation_does_not_persist_or_expose_content(client, db, make_user, caplog):
    _, headers, _ = await make_user()
    private = "confidential-unprocessable-marker"
    response = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": private}
    )
    assert response.status_code == 422
    assert private not in response.text and private not in caplog.text
    assert await db.scalar(select(func.count()).select_from(models.Document)) == 0
    response = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": {"secret-key-name": private}}
    )
    assert response.status_code == 422
    assert private not in response.text and "secret-key-name" not in response.text


async def test_raw_txt_no_spooled_file_and_multipart_rejected(client, make_user, monkeypatch):
    _, headers, _ = await make_user()

    def forbidden(*args, **kwargs):
        raise AssertionError("Spooling forbidden")

    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", forbidden)
    response = await client.post(
        "/api/v1/adaptations/file?nivel_simplificacion_nlp=1",
        headers={**headers, "Content-Type": "text/plain"},
        content=SOURCE.encode(),
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/adaptations/file", headers=headers, files={"file": ("private.txt", b"private")}
    )
    assert response.status_code == 415 and "private.txt" not in response.text


async def test_stream_limit_enforced_without_content_length(client, make_user, monkeypatch):
    _, headers, _ = await make_user()
    monkeypatch.setattr(settings, "MAX_BODY_BYTES", 64)

    async def body():
        yield b"x" * 40
        yield b"y" * 40

    response = await client.post(
        "/api/v1/adaptations/file",
        headers={**headers, "Content-Type": "text/plain"},
        content=body(),
    )
    assert response.status_code == 413


def pdf_bytes(text):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F1 12 Tf 50 500 Td (" + text.encode("ascii") + b") Tj ET")
    page[NameObject("/Contents")] = writer._add_object(contents)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


async def test_pdf_extracts_in_memory_and_invalid_pdf_is_sanitized(client, make_user):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/file",
        headers={**headers, "Content-Type": "application/pdf"},
        content=pdf_bytes(SOURCE),
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/adaptations/file",
        headers={**headers, "Content-Type": "application/pdf"},
        content=b"%PDF-malformed-private",
    )
    assert response.status_code == 422 and "private" not in response.text


async def test_rate_limit_no_username_bucket(client, make_user, monkeypatch):
    _, headers, _ = await make_user()
    monkeypatch.setattr(settings, "REQUESTS_PER_MINUTE", 1)
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 429 and response.headers["retry-after"] == "60"


async def test_database_refuses_noncompliant_telemetry(db, make_user):
    import pytest
    from sqlalchemy.exc import IntegrityError

    user, _, _ = await make_user()
    document = models.Document(
        owner_id=user.id,
        file_type=models.DocumentType.TXT,
        file_size_bytes=20,
        original_szigriszt_score=60.0,
        adapted_szigriszt_score=65.0,
        score_delta=5.0,
        original_word_count=20,
        adapted_word_count=20,
        original_syllable_count=30,
        original_sentence_count=2,
        syllable_count=25,
        sentence_count=3,
        maintenance_exception=False,
    )
    db.add(document)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
