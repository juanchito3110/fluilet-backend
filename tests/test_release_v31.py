"""Release checks for complete reading spans and context-licensed vocabulary."""

import re

import pytest

from app import vocabulary
from app.ingestion import clean_text
from app.nlp.segmentation import sentences, words
from app.nlp.validation import reading_chunks
from app.services.comprehension import build_questions
from app.services.glossary_es import entries
from app.services.source_cleanup import sanitize


def test_glossary_rejects_trivial_tokens_and_conjugated_verbs():
    text = (
        "El Sol da luz y v no es un concepto. El robot utiliza sensores y motores. "
        "Su programa recibe datos y sigue instrucciones para realizar tareas."
    )
    items = vocabulary.key_vocabulary(text)
    assert len(items) == 4
    assert {v["word"].casefold() for v in items} <= {
        "robot",
        "sensores",
        "motores",
        "programa",
        "datos",
        "instrucciones",
    }
    for item in items:
        assert 10 <= len(words(item["definition"])) <= 22
        assert item["word"] in item["example"] and item["example"] in sentences(text)


def test_all_authored_definitions_are_complete_and_inside_word_limits():
    for _, definition in entries():
        assert 10 <= len(words(definition)) <= 22
        assert definition[0].isupper() and definition.endswith(".")
        assert not re.search(r"___|…|\.\.\.", definition)


def test_glossary_uses_the_mass_sense_in_the_actual_reading():
    physics = vocabulary.key_vocabulary("La masa indica la cantidad de materia de un cuerpo.")
    baking = vocabulary.key_vocabulary("La panadera prepara una masa para cocer pan en el horno.")
    assert "materia" in next(v["definition"] for v in physics if v["word"] == "masa")
    assert "panadería" in next(v["definition"] for v in baking if v["word"] == "masa")


def test_unknown_words_without_definitions_do_not_get_invented_glossary_meanings():
    assert vocabulary.key_vocabulary("El flurpilum trozbatea rápidamente.") == []


def test_ambiguous_noun_forms_do_not_become_keywords_when_used_as_verbs():
    text = "Él prueba la comida. Yo modelo figuras. El guardián vela por el pueblo. Yo paso por la escuela."
    assert not (
        {v["word"].casefold() for v in vocabulary.key_vocabulary(text)}
        & {"prueba", "modelo", "vela", "paso"}
    )


def test_glossary_examples_never_slice_long_sentences_at_a_character_offset():
    text = (
        "El telescopio "
        + "recoge luz de las estrellas y " * 20
        + "permite estudiar galaxias lejanas."
    )
    items = vocabulary.key_vocabulary(text)
    assert items and all(item["example"] == text for item in items)


def test_fun_fact_keeps_the_last_complete_sentence_instead_of_an_ellipsis():
    text = (
        "El telescopio "
        + ("recoge luz de las estrellas y " * 25)
        + "permite estudiar galaxias lejanas."
    )
    assert len(text) > 480
    fact = vocabulary.fun_fact(text)
    assert text in fact and "…" not in fact


def test_known_pdf_wrapped_words_and_soft_hyphens_are_restored():
    assert clean_text("crustá-\nceos y mamí\u00adferos.") == "crustáceos y mamíferos."
    assert "12-\n34" in clean_text("12-\n34")


def test_bounded_ocr_correction_never_removes_a_scientific_variable_or_roman_numeral():
    assert sanitize("Hay peces, crustáceos v mamíferos.")[0] == "Hay peces, crustáceos y mamíferos."
    clean, removed = sanitize("En el mar hay peces y crustáceos v.")
    assert clean.endswith("crustáceos.") and removed == ("crustáceos v",)
    for value in ("La velocidad se representa por v.", "El manuscrito es del siglo V."):
        assert sanitize(value)[0] == value


def test_long_reading_blocks_cover_every_complete_sentence_and_final_conjunction():
    unit = "El océano contiene algas, peces, moluscos, crustáceos y mamíferos."
    text = " ".join([unit] * 145)
    chunks = reading_chunks(text)
    assert len(chunks) > 1
    assert " ".join(chunks) == text
    assert all(part.endswith("crustáceos y mamíferos.") for part in chunks)
    assert sum(len(sentences(part)) for part in chunks) == 145


def test_unseen_fact_cause_and_concept_remain_distinct_with_whole_options():
    text = (
        "El vehículo Lince recorre 30 kilómetros. "
        "El motor no arranca porque no recibe energía. "
        "El robot gira alrededor del Sol."
    )
    questions = build_questions(text, 10)
    assert len({q["question"] for q in questions}) == 3
    assert any("kilómetros" in q["question"] for q in questions)
    assert any("Por qué" in q["question"] for q in questions)
    assert any("robot" in q["question"] for q in questions)
    for q in questions:
        assert len(q["options"]) == len(set(q["options"])) == 4
        assert all(3 <= len(words(o)) <= 12 for o in q["options"])
        evidence = re.search(r"La lectura explica: «(.+)»\.$", q["explanation"])[1]
        assert evidence in text


def test_dynamic_cause_distractors_keep_the_actual_energy_context():
    text = "El motor no arranca porque no recibe energía. El robot usa sensores."
    question = next(q for q in build_questions(text) if "Por qué" in q["question"])
    assert all("energía" in option for option in question["options"])
    assert all("Sol" not in option and "agua" not in option for option in question["options"])


def test_leading_year_and_semicolon_clauses_are_analyzed_without_truncation():
    text = (
        "En 1984, el observatorio Lince comenzó sus operaciones; "
        "el vehículo recorre 30 kilómetros. El motor no arranca porque no recibe energía."
    )
    questions = build_questions(text)
    year = next(q for q in questions if "año" in q["question"])
    assert year["options"][year["correct_option_index"]] == "En el año 1984"
    assert all(re.fullmatch(r"En el año \d{4}", o) for o in year["options"])


@pytest.mark.parametrize("text", ["Hola", "42"])
def test_insufficient_information_is_not_filled_with_fabricated_facts(text):
    # Reading stays available; neither four noun concepts nor a historical cause
    # can truthfully be extracted from a single greeting or a single number.
    assert vocabulary.key_vocabulary(text) == []
    assert all(text in q["explanation"] for q in build_questions(text))


@pytest.mark.parametrize("case", range(8))
def test_unseen_passages_keep_five_requested_bands_and_three_distinct_evidence_tasks(case):
    from collections import Counter

    from app.services.pedagogy import choose_levels
    from tests.open_readings import READINGS
    from tests.question_assertions import assert_grounded_questions
    from tests.test_best_effort import TEXT_A, TEXT_B

    source = (*READINGS, TEXT_A, TEXT_B)[case]
    _, previews, ordered = choose_levels(source)
    assert ordered
    scores = []
    bounds = {1: (6, 9), 2: (9, 12), 3: (12, 15), 4: (15, 19)}
    for p in previews:
        text = p["adapted_text"]
        average = len(words(text)) / len(sentences(text))
        if p["level"] <= 4:
            low, high = bounds[p["level"]]
            assert low <= average <= high
        else:
            if average <= 19:
                from difflib import SequenceMatcher

                assert len(sentences(text)) == len(sentences(source))
                assert (
                    SequenceMatcher(
                        None, words(text.casefold()), words(source.casefold()), autojunk=False
                    ).ratio()
                    >= 0.85
                )
        assert Counter(re.findall(r"\d+(?:[.,]\d+)*", text)) == Counter(
            re.findall(r"\d+(?:[.,]\d+)*", source)
        )
        assert len(vocabulary.key_vocabulary(text)) == 4
        questions = build_questions(text, 10, source)
        assert_grounded_questions(questions, text)
        assert len({q["question"] for q in questions}) == 3
        assert re.search(r"Por qué|Para qué|Qué permite|Qué hace", questions[1]["question"])
        scores.append(p["readability_score"])
    assert all(a > b for a, b in zip(scores, scores[1:], strict=False))


def test_source_date_transfer_requires_its_actual_actor_after_sentence_split():
    source = "La NASA comenzó a trabajar en 1958. Sus equipos usan telescopios para observar planetas. El Sol es una estrella."
    adapted = "La NASA empezó a trabajar. Eso fue en 1958. Sus equipos usan telescopios para observar planetas. El Sol es una estrella."
    questions = build_questions(adapted, 7, source)
    year = next(q for q in questions if "año" in q["question"])
    assert "NASA" in year["question"]
    assert year["options"][year["correct_option_index"]] == "En el año 1958"
    assert "La NASA empezó a trabajar. Eso fue en 1958." in year["explanation"]


def test_a_year_in_another_coordinated_subject_never_becomes_nasas_birth_year():
    text = "La NASA estudia el espacio y mi abuela nació en 1958. El Sol es una estrella."
    assert not any(
        "NASA" in q["question"] and "año" in q["question"] for q in build_questions(text)
    )


def test_negative_statement_never_becomes_a_positive_quiz_answer():
    text = "Un programa no contiene instrucciones. El robot gira alrededor del Sol."
    for q in build_questions(text):
        answer = q["options"][q["correct_option_index"]]
        assert answer != "Contiene instrucciones"
        assert "Un programa no" not in q["question"]


def test_olympic_program_and_computer_program_have_different_glossary_senses():
    olympic = vocabulary.key_vocabulary("El programa de los Juegos Olímpicos reúne deportes.")
    computer = vocabulary.key_vocabulary("Un robot sigue un programa con instrucciones.")
    assert "actividades" in next(v["definition"] for v in olympic if v["word"] == "programa")
    assert "instrucciones" in next(v["definition"] for v in computer if v["word"] == "programa")


def test_scientific_adjective_and_study_verb_are_not_noun_keywords():
    text = "Yo estudio y diseño. Los conocimientos científicos ayudan al alumno."
    assert not {"estudio", "diseño", "científicos"} & {
        v["word"] for v in vocabulary.key_vocabulary(text)
    }


def test_noun_study_inside_a_subject_is_not_mistaken_for_its_finite_verb():
    from app.services.clear_spanish import _HEAD

    head = _HEAD.match("El grupo de estudio usó varios instrumentos.")
    assert head["subject"] == "El grupo de estudio" and head["verb"] == "usó"


def test_science_actor_agreement_keeps_a_different_coordinated_subject_plural():
    from app.services.clear_spanish import rewrite

    text = "Los investigadores usaron instrumentos y los alumnos miraron las plantas del jardín."
    adapted = rewrite(text, 1)
    assert "El grupo de estudio usó instrumentos" in adapted
    assert "los alumnos miraron" in adapted.lower()
