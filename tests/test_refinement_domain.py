import pytest

from app.nlp.readability import accepted, measure
from app.nlp.refinement import fidelity_ok, lexical, refine, split_domain_clauses
from app.nlp.segmentation import words


def test_contextual_pairs_and_whitespace_do_not_corrupt_agreement_or_acronyms():
    assert lexical("UE TDAH Stollen Bratwurst") == "UE TDAH Stollen Bratwurst"
    assert lexical("participación e involucración") == "participación y compromiso"
    assert lexical("Una nave de gran envergadura.") == "Una nave de gran envergadura."
    assert "capacidad de cambiar" in lexical("la capacidad  de alterar")
    assert "actuar del mismo modo ante" in lexical("para un abordaje homogéneo de")
    assert (
        lexical("Tiene un abordaje homogéneo de la materia.")
        == "Tiene un abordaje similar de la materia."
    )


def test_goal_nominalizations_remain_goals_and_keep_qualifiers():
    source = "Su objetivo es crear un plan para la salud, mejorando su detección, diagnóstico temprano, prevención, evaluación y manejo."
    candidate = refine(source)
    assert "El fin es mejorar cómo se hace un diagnóstico temprano." in candidate
    assert "El fin es mejorar cómo se previene." in candidate
    assert fidelity_ok(source, candidate)
    qualified = "Su fin es crear un plan, mejorando su posible detección y evaluación limitada."
    assert split_domain_clauses(qualified) == qualified
    negative = "Su fin no es crear un plan, mejorando su detección y evaluación."
    assert split_domain_clauses(negative) == negative


def test_restrictive_relative_and_concession_are_not_turned_into_assertions():
    source = "Aunque puede afectar a niños, la enfermedad no se detecta en todos los adultos."
    assert refine(source) == source
    restrictive = "El alumno que usa libros aprende cosas nuevas."
    assert refine(restrictive) == restrictive


def test_explicit_glosses_preserve_entities_and_refuse_conditional_parentheses():
    source = "El mercado ofrece Stollen (pan dulce) y Bratwurst (salchichas)."
    candidate = refine(source)
    assert "Con Stollen, el texto se refiere a pan dulce." in candidate
    assert "Con Bratwurst, el texto se refiere a salchichas." in candidate
    assert fidelity_ok(source, candidate)
    for text in ["Stollen (pan si llueve)", "Stollen (pan sin gluten)", "Ana (no está enferma)"]:
        assert split_domain_clauses(text) == text


@pytest.mark.parametrize("change", ["number", "negation", "entity", "actor"])
def test_structural_references_do_not_authorize_other_content_changes(change):
    source = "El informe recoge las medidas de seguridad en el trabajo más urgentes para la vuelta de 20 personas y tiene como prioridad la salud de los profesionales que no trabajan en ese campo."
    candidate = refine(source)
    assert fidelity_ok(source, candidate)
    mutations = {
        "number": candidate.replace("20", "30"),
        "negation": candidate.replace("no trabajan", "trabajan"),
        "entity": candidate + " La OMS aprueba este tratamiento.",
        "actor": candidate.replace("El informe pone", "Los profesionales ponen"),
    }
    assert not fidelity_ok(source, mutations[change])


def test_negative_temporal_coordination_keeps_each_predicate_negated():
    source = (
        "Los alumnos no utilizan 20 libros y posteriormente no realizan 10 actividades con sus amigos en la escuela. "
        * 2
    ).strip()
    candidate = refine(source, 1)
    assert words(candidate).count("no") == 4
    assert candidate.count("20") == 2 and candidate.count("10") == 2
    assert "Los alumnos después no hacen" in candidate
    assert fidelity_ok(source, candidate) and accepted(measure(source), measure(candidate))
