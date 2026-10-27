import asyncio

import pytest

from app.config import settings
from app.nlp.chunking import conservative_tokens
from app.nlp.mt5 import ModelUnavailable, MT5Runtime
from app.nlp.pipeline import AdaptationPipeline
from app.nlp.refinement import fidelity_ok, refine
from tests.conftest import SOURCE


class Offline:
    async def prepare(self):
        raise ModelUnavailable()

    count_tokens = staticmethod(conservative_tokens)


async def test_rules_work_without_torch_and_keep_strict_conditions():
    result = await AdaptationPipeline(Offline()).run(SOURCE)
    assert result.metrics["score_delta"] >= 15
    assert result.metrics["adapted_szigriszt_score"] >= 65
    assert not result.metrics["maintenance_exception"]
    assert result.method == "rules"
    assert fidelity_ok(SOURCE, result.adapted_text)


async def test_passing_rules_candidate_avoids_model_generation():
    class Loaded:
        async def prepare(self):
            pass

        count_tokens = staticmethod(conservative_tokens)

        async def generate(self, text, attempt):
            raise AssertionError("Passing deterministic candidate should short-circuit generation")

    result = await AdaptationPipeline(Loaded()).run(SOURCE)
    assert result.method == "rules"
    assert result.metrics["score_delta"] >= 15
    assert result.metrics["adapted_szigriszt_score"] >= 65


async def test_missing_rule_coverage_attempts_model_before_best_effort():
    class Loaded:
        calls = 0

        async def prepare(self):
            pass

        count_tokens = staticmethod(conservative_tokens)

        async def generate(self, text, attempt):
            self.calls += 1
            return "<extra_id_0>."

    model = Loaded()
    result = await AdaptationPipeline(model).run(
        "La espectrointerferometría analiza matrices hiperdimensionales extraordinariamente sofisticadas. "
        * 4
    )
    assert result.quality_status == "best_effort"
    assert model.calls == settings.MAX_GENERATION_ATTEMPTS


async def test_extremely_simple_input_maintenance():
    text = "El sol da luz. " * 5
    result = await AdaptationPipeline(Offline()).run(text)
    assert result.metrics["maintenance_exception"]
    assert result.metrics["score_delta"] == pytest.approx(0)
    assert result.metrics["adapted_szigriszt_score"] >= 85


async def test_no_fabricated_success_when_rules_cannot_improve():
    text = (
        "La espectrointerferometría analiza matrices hiperdimensionales extraordinariamente sofisticadas. "
        * 4
    )
    result = await AdaptationPipeline(Offline()).run(text)
    assert not result.meets_readability_target
    assert result.metrics["score_delta"] == 0
    assert result.adapted_text.strip() == text.strip()
    assert result.method == "original"


async def test_bounded_model_attempts_and_fidelity(monkeypatch):
    class Hallucinating:
        calls = 0

        async def prepare(self):
            pass

        count_tokens = staticmethod(conservative_tokens)

        async def generate(self, text, attempt):
            self.calls += 1
            return "El sol da luz. " * 5

    fake = Hallucinating()
    monkeypatch.setattr(settings, "ALLOW_RULE_BASED_FALLBACK", False)
    source = (
        "La espectrointerferometría analiza matrices hiperdimensionales extraordinariamente sofisticadas. "
        * 4
    )
    result = await AdaptationPipeline(fake).run(source)
    assert result.adapted_text.strip() == source.strip()
    assert result.quality_status == "best_effort"
    assert fake.calls == settings.MAX_GENERATION_ATTEMPTS


def test_guard_preserves_numbers_negation_and_argument_order():
    assert not fidelity_ok("El perro muerde al niño.", "El niño muerde al perro.")
    assert not fidelity_ok("El niño no lee 20 libros.", "El niño lee 20 libros.")
    assert not fidelity_ok("El niño lee 20 libros.", "El niño lee 30 libros.")
    assert "Los sujetos" in refine("Los individuos utilizan libros.")


async def test_model_load_is_lazy_and_missing_dependencies_safe():
    model = MT5Runtime()
    assert model.state == "not_loaded"
    with pytest.raises(ModelUnavailable):
        await model.prepare()
    assert model.state == "unavailable"


async def test_timeout_does_not_release_native_generation_slot(monkeypatch):
    import threading

    model = MT5Runtime()
    model._model = object()
    monkeypatch.setattr(settings, "MT5_TIMEOUT_SECONDS", 0.02)
    entered, release = threading.Event(), threading.Event()

    def blocked(text, attempt):
        entered.set()
        release.wait(2)
        return "done"

    monkeypatch.setattr(model, "_generate_sync", blocked)
    with pytest.raises(ModelUnavailable):
        await model.generate("synthetic", 0)
    assert entered.is_set() and model._slots.locked()
    with pytest.raises(ModelUnavailable):
        await model.generate("synthetic", 1)
    release.set()
    await asyncio.wait_for(model.close(), 2)
    assert not model._slots.locked()


def test_explanatory_relative_becomes_explicit_subject_sentences():
    text = (
        "El alumno, que utiliza muchos libros de cuentos para estudiar con sus amigos "
        "cada tarde en la escuela, aprende cosas nuevas para su clase de ciencias."
    )
    candidate = refine(text)
    assert ". El alumno aprende" in candidate
    assert "que usa" not in candidate
    assert fidelity_ok(text, candidate)
    ambiguous = "El alumno que usa libros aprende cosas nuevas."
    assert refine(ambiguous) == ambiguous


async def test_lazy_checkpoint_load_runs_off_event_loop(monkeypatch, tmp_path):
    import importlib.util
    import sys
    import threading
    from types import SimpleNamespace

    from app.nlp import mt5

    model = MT5Runtime()
    calls = []
    main_thread = threading.get_ident()

    class FakeModel:
        def eval(self):
            return self

    class FakeLoader:
        @staticmethod
        def from_pretrained(source, **kwargs):
            calls.append((source, kwargs, threading.get_ident()))
            return FakeModel()

    monkeypatch.setattr(settings, "MT5_ENABLED", True)
    monkeypatch.setattr(settings, "MT5_CHECKPOINT", str(tmp_path))
    original_find = importlib.util.find_spec
    monkeypatch.setattr(
        mt5.importlib.util,
        "find_spec",
        lambda name: (
            object() if name in {"torch", "transformers", "sentencepiece"} else original_find(name)
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(__version__="2.6.0", set_num_threads=lambda value: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoTokenizer=FakeLoader, AutoModelForSeq2SeqLM=FakeLoader),
    )
    assert not calls
    await model.prepare()
    assert len(calls) == 2 and model.state == "loaded"
    assert all(source == str(tmp_path) and thread != main_thread for source, _, thread in calls)
    assert calls[1][1]["weights_only"] is True
    assert calls[1][1]["local_files_only"] is True
    await model.close()


def test_rewriter_avoids_noun_gender_mismatches():
    assert (
        refine("La utilización tiene un objetivo y un obstáculo.")
        == "La utilización tiene un objetivo y un obstáculo."
    )
    assert "Los sujetos interesados" in refine("Los individuos interesados utilizan libros.")


def test_guard_refuses_added_facts_even_when_lexical_overlap_is_high():
    source = SOURCE * 4
    assert not fidelity_ok(source, source + " Este fármaco cura cáncer.")


def test_younger_readers_use_shorter_safe_clause_boundaries():
    source = "El robot usa sensores para observar el terreno y recibe datos de otros robots."
    assert refine(source, level=5) == source
    younger = refine(source, level=5, child_age=7)
    middle = refine(source, level=5, child_age=10)
    assert ". El robot recibe" in younger
    assert younger == middle
    assert fidelity_ok(source, younger)
    assert refine(source, level=5, child_age=12) == source
