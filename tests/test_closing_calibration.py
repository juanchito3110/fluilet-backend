"""Independent scoring, bounded grammar/scope and production Android contracts."""

import os
import re
import subprocess
import sys
from collections import Counter

import pytest

from app.nlp.readability import measure
from app.services.analytic_es import analytic
from app.services.calibration import pack, purpose_clauses, regroup, statistical_clauses
from app.services.pedagogy import lexical
from app.services.ranker import checkpoint, quality
from app.services.residual import lexical_summary, vector
from tests.test_retrained_model import UNSEEN


def test_analytic_periphrases_keep_agreement_and_do_not_guess_suffixes():
    assert (
        analytic("Después se explica la alimentación y el funcionamiento.")
        == "Después se explica lo que se come y la forma en que va."
    )
    assert (
        analytic("La gestión, la canción y la ciudad son nombres.")
        == "La gestión, la canción y la ciudad son nombres."
    )
    # No broad density rule may equate energy and force or guess word senses.
    assert analytic("La energía no es una fuerza.") == "La energía no es una fuerza."
    assert (
        analytic("Con esas instrucciones puede hacer tareas.")
        == "Con esos pasos puede hacer tareas."
    )
    assert (
        analytic("Sus resultados pueden tener errores.")
        == "Lo que da al usarlo puede tener errores."
    )
    assert "ciencia y lo" in analytic("Mezcla ciencia e imaginación.")


@pytest.mark.parametrize(
    "text",
    [
        "Los niños no usan libros para entender las plantas.",
        "Si los niños usan libros para entender las plantas, pueden aprender.",
        "Aunque los niños usan libros para entender las plantas, tienen dudas.",
        "Los niños que usan libros para entender las plantas hacen preguntas.",
        "Los niños pueden usar libros para entender las plantas.",
        "Quienes estudian y usan libros pueden aprender.",
    ],
)
def test_purpose_split_keeps_negation_modality_and_restrictive_scope(text):
    assert purpose_clauses(text) == text


def test_purpose_does_not_claim_a_successful_result_or_change_tense():
    source = "Los niños usarán libros para entender las plantas."
    result = purpose_clauses(source)
    assert result == "Los niños usarán libros. El fin es entender las plantas."
    assert "entendieron" not in result
    assert "no no" not in lexical("El frío no impide que salgan los niños.", 1)


def test_statistics_retain_quantities_and_do_not_escape_a_condition():
    source = "El 70 por 100 de los nuevos casos se detectan en personas de entre 20 y 40 años de edad y, en 3 de cada 4 pacientes, en mujeres."
    result = statistical_clauses(source)
    assert Counter(re.findall(r"\d+", source)) == Counter(re.findall(r"\d+", result))
    assert "De cada 4 pacientes, 3 son mujeres." in result
    conditional = "Si se confirma el dato, " + source[0].lower() + source[1:]
    assert statistical_clauses(conditional) == conditional


def test_compound_grouping_only_uses_complete_statement_boundaries():
    source = "El mar tiene agua. La Luna refleja luz. El Sol es una estrella. La Tierra gira."
    result = regroup(source, 2)
    assert measure(result).sentence_count == 2
    assert Counter(re.findall(r"\w+", source.casefold())) == Counter(
        re.findall(r"\w+", result.casefold())
    )
    assert pack("¿Hay agua? La Luna refleja luz.", 100) == "¿Hay agua? La Luna refleja luz."


def test_long_reading_reuses_clauses_and_preserves_each_numeric_occurrence(monkeypatch):
    from app.services import pedagogy

    original = pedagogy._choose_levels
    calls = []

    def observed(text, *args):
        calls.append(text)
        return original(text, *args)

    monkeypatch.setattr(pedagogy, "_choose_levels", observed)
    unit = "Los alumnos utilizan 2 mapas para observar las plantas. Los alumnos explican 3 hechos del estudio."
    source = " ".join([unit] * 20)
    _, previews, _ = pedagogy.choose_levels(source)
    assert len(calls) == 2
    for preview in previews:
        assert preview["readability_score"] == measure(preview["adapted_text"]).score
        assert Counter(re.findall(r"\d+", source)) == Counter(
            re.findall(r"\d+", preview["adapted_text"])
        )


def test_measurement_session_has_identical_scores_and_clears_private_word_cache():
    from app.nlp.readability import _SYLLABLES, measurement_session

    source = "La Luna refleja la luz del Sol en 2020."
    expected = measure(source)
    assert _SYLLABLES.get() is None
    with measurement_session():
        assert measure(source) == measure(source) == expected
    assert _SYLLABLES.get() is None
    with pytest.raises(RuntimeError), measurement_session():
        measure(source)
        raise RuntimeError("controlled")
    assert _SYLLABLES.get() is None


def test_five_level_outputs_are_reproducible_across_python_hash_seeds():
    script = """import hashlib,json
from app.encyclopedia import ARTICLES
from app.services.pedagogy import choose_levels
rows=[ARTICLES[k].text for k in ('atletismo','abejas','antiguo egipto')]
rows.append('Los historiadores utilizan documentos antiguos para comprender los cambios de las ciudades y posteriormente proporcionan explicaciones sobre sus habitantes.')
data=[choose_levels(text)[1] for text in rows]
print(hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest())"""
    results = [
        subprocess.run(
            [sys.executable, "-B", "-c", script],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
            timeout=45,
        ).stdout.strip()
        for seed in ("1", "2")
    ]
    assert results[0] == results[1]


def test_lexical_ranker_is_independent_of_level_and_reuses_identical_features():
    model = checkpoint()["sari_ranker"]
    source = "Los niños utilizan mapas. Los niños explican los cambios."
    target = "Los niños usan mapas. Los niños explican los cambios."
    assert quality(source, target, 1) == quality(source, target, 5)
    assert vector(source, target, model["priors"]) == vector(
        source, target.replace(". Los", "; los"), model["priors"]
    )
    assert lexical_summary(model, source, target) == lexical_summary(
        model, source, target, base=vector(source, target, model["priors"])
    )


@pytest.mark.parametrize("level", range(1, 6))
async def test_txt_primary_metrics_and_retained_version(client, make_user, level):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/file?level=" + str(level),
        headers={**headers, "Content-Type": "text/plain"},
        content=UNSEEN[0]["source"].encode(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["adapted_text"] == data["level_previews"][level - 1]["adapted_text"]
    assert data["readability_score"] == measure(data["adapted_text"]).score
    for field in (
        "readability_gain",
        "original_avg_sentence_length",
        "adapted_avg_sentence_length",
        "original_syllables_per_word",
        "adapted_syllables_per_word",
        "lexical_replacements",
        "model_version",
        "checkpoint_name",
    ):
        assert field in data
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": "private input", "level": 0},
        {"text": "private input", "level": 6},
        {"text": "private input", "level": True},
    ],
)
async def test_clear_input_errors_never_echo_request_text(client, make_user, body):
    _, headers, _ = await make_user()
    response = await client.post("/api/v1/adaptations/text", headers=headers, json=body)
    assert response.status_code == 422 and "private input" not in response.text
    assert response.json()["errors"][0]["message"]


async def test_unsupported_upload_and_native_cors(client, make_user):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/file",
        headers={**headers, "Content-Type": "image/png"},
        content=b"private-file",
    )
    assert response.status_code == 415 and "PDF o TXT" in response.json()["detail"]
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200
    preflight = await client.options(
        "/api/v1/adaptations/text",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost"
    rejected = await client.options(
        "/api/v1/adaptations/text",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
    )
    assert rejected.status_code == 400 and "access-control-allow-origin" not in rejected.headers
