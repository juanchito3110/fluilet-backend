"""Measured diagnostic contracts; no universal/readability or efficacy assertion."""

import hashlib
import io
import json
from pathlib import Path

import pytest

from app.nlp.pipeline import pipeline
from app.nlp.readability import measure
from app.services.morphology import FORMS, form
from app.services.ranker import ASSET, checkpoint, model_info
from ml_training.build_enhanced_dataset import build
from ml_training.metrics import sari

FIXTURES = Path(__file__).parents[1] / "ml_training/fixtures"
EASIER = json.loads((FIXTURES / "easier_diagnostic.json").read_text())
UNSEEN = json.loads((FIXTURES / "unseen_v2.json").read_text())


def pdf_bytes(text):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    encoded = (
        text.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    )
    content.set_data(b"BT /F1 12 Tf 50 500 Td (" + encoded + b") Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_real_checkpoint_fitted_weights_and_report():
    info = model_info()
    assert info["active"] and info["epochs"] == 36
    assert info["weights_sha256_before"] != info["weights_sha256_after"]
    assert info["dataset_v1_size"] == 7704 and info["dataset_v2_size"] == 4738
    assert len(info["history"]) == info["epochs"]
    assert min(r["val_loss"] for r in info["history"]) < info["history"][0]["val_loss"]
    assert info["easier_benchmark_after"] == "6/6"
    assert info["sari_score"] == info["retrained_metrics"]["sari_score"]
    assert info["artifact_sha256"] == hashlib.sha256(ASSET.read_bytes()).hexdigest()
    assert len(checkpoint()["sari_ranker"]["lexical_weights"]) == 37


def test_morphological_agreement_and_spelling():
    assert form("utilizar", "é") == "utilicé"
    for a, b in [
        ("utilizaron", "usaron"),
        ("utilizarán", "usarán"),
        ("utilizando", "usando"),
        ("utilizadas", "usadas"),
        ("numerosas", "muchas"),
        ("beneficiosas", "buenas"),
    ]:
        assert FORMS[a] == b


@pytest.mark.parametrize("row", EASIER + UNSEEN, ids=lambda row: row["document_id"])
async def test_fixed_diagnostics_have_five_real_progressive_outputs(row):
    result = await pipeline.run(row["source"], 1)
    assert result.model_version == "context-ranker-es-v2.2"
    assert result.checkpoint_name == "context-ranker-v2.2"
    assert result.original_text == row["source"]
    scores = [measure(p["adapted_text"]).score for p in result.level_previews]
    assert scores == [p["readability_score"] for p in result.level_previews]
    assert result.level_progression_met
    assert all(a > b for a, b in zip(scores, scores[1:], strict=False))
    assert scores[0] - measure(row["source"]).score >= 15


@pytest.mark.parametrize("media", ["text/plain", "application/pdf"])
async def test_trained_model_applies_to_files_and_preserved_get(client, make_user, media):
    _, headers, _ = await make_user()
    source = UNSEEN[0]["source"]
    content = source.encode() if media == "text/plain" else pdf_bytes(source)
    response = await client.post(
        "/api/v1/adaptations/file?nivel_simplificacion_nlp=1",
        headers={**headers, "Content-Type": media},
        content=content,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model_version"] == "context-ranker-es-v2.2"
    assert data["checkpoint_name"] == "context-ranker-v2.2"
    assert data["level_progression_met"] and data["lexical_replacements"]
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


async def test_model_info_route_precedes_uuid_and_requires_auth(client, make_user):
    assert (await client.get("/api/v1/adaptations/model-info")).status_code == 401
    _, headers, _ = await make_user()
    response = await client.get("/api/v1/adaptations/model-info", headers=headers)
    assert response.status_code == 200
    info = response.json()
    assert info["model_version"] == "context-ranker-es-v2.2"
    assert info["easier_benchmark_before"] == "0/6"
    assert info["easier_benchmark_after"] == "6/6"
    assert info["benchmark_definition"].startswith("strict five-level")
    assert info["retrained_metrics"]["lexical_top1"] < 1


def test_dataset_build_is_deterministic_and_has_no_group_leakage(tmp_path):
    corpus = tmp_path / "sgss.csv"
    rows = ["document_id;word_id;word;sentence;Sinónimos"]
    for i in range(80):
        suffix = chr(97 + i // 26) + chr(97 + i % 26)
        term = "instrumentos" + suffix
        rows.append(
            f"{1000 + i};1;{term};Los alumnos usan {term} para observar las plantas en la sala.;útiles, excesivamente largo"
        )
    rows.append("120;1;aroma;Un aroma en el mercado.;olor")
    corpus.write_text("\n".join(rows))
    first, second = tmp_path / "first", tmp_path / "second"
    manifest = build(corpus, FIXTURES / "easier_diagnostic.json", first)
    other = build(corpus, FIXTURES / "easier_diagnostic.json", second)
    assert manifest == other
    assert manifest["filtered"]["quarantined_document"] == 1
    assert manifest["filtered"]["not_shorter_or_noisy"] >= 80
    partitions = {
        name: [json.loads(line) for line in (first / (name + ".jsonl")).read_text().splitlines()]
        for name in ("train", "validation", "test")
    }
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("document_id", "family", "source"):
            assert not ({r[key] for r in partitions[a]} & {r[key] for r in partitions[b]})
    assert all(
        1 <= r["level"] <= 5 and r["age_group"] in {"6-8", "9-11", "12+"}
        for rows in partitions.values()
        for r in rows
    )


def test_sari_single_reference_perfect_and_identity():
    source = "Los alumnos utilizan instrumentos para observar las plantas."
    target = "Los alumnos usan herramientas para mirar las plantas."
    assert sari(source, target, target) == 100
    assert sari(source, source, target) < 100


def test_runtime_corpus_cannot_read_validation_labels_or_frequencies(tmp_path, monkeypatch):
    from app.services import ranker, resources

    source = "Los alumnos utilizan instrumentos para observar las plantas en el aula."
    path = tmp_path / "sgss.csv"
    path.write_text(
        "document_id;word_id;word;sentence;Sinónimos\n1;1;instrumentos;" + source + ";útiles\n"
    )
    index = resources.load_resources(path, root=tmp_path)
    monkeypatch.setattr(resources, "resources", lambda: index)
    model = {
        "training_document_hashes": [],
        "training_family_hashes": [],
        "training_target_counts": {},
    }
    monkeypatch.setattr(ranker, "checkpoint", lambda: model)
    assert resources.choose_corpus("instrumentos", source, 1, training_only=True) is None
    model["training_document_hashes"] = [hashlib.sha256(b"easier:1").hexdigest()]
    model["training_family_hashes"] = [hashlib.sha256(b"instrumentos").hexdigest()]
    assert resources.choose_corpus("instrumentos", source, 1, training_only=True) is None
    model["training_target_counts"] = {hashlib.sha256("útiles".encode()).hexdigest(): 1}
    assert resources.choose_corpus("instrumentos", source, 1, training_only=True) == "útiles"
