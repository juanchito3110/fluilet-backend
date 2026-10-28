"""Guard release provenance, source-grounded support and real reported metrics."""

import hashlib
import json

import pytest

from app.encyclopedia import ARTICLES
from app.nlp.pipeline import pipeline
from app.nlp.readability import measure
from app.services.ranker import ASSET, checkpoint, model_info
from app.services.scaffolding import supports
from app.services.selection_gate import NAMES, decision


def test_frozen_gate_and_retained_lexical_head_have_measured_provenance():
    parent = json.loads(ASSET.with_name("context-ranker-v2.2.json").read_text())
    model = checkpoint()["sari_ranker"]
    assert model["lexical_weights"] == parent["sari_ranker"]["lexical_weights"]
    assert model["selective_gate"]["features"] == list(NAMES)
    info = model_info()
    fit = info["gate_fit"]
    assert fit["training_samples"] > 0 and fit["validation_samples"] == 402
    assert not fit["test_opened_for_fitting"]
    assert info["test_selection_sha256"] == info["frozen_selection_sha256"]
    assert (
        info["parent_model_sha256"]
        == hashlib.sha256(ASSET.with_name("context-ranker-v2.2.json").read_bytes()).hexdigest()
    )
    assert (
        info["retrained_metrics"]["lexical_top1"]
        == parent["metrics"]["retrained_metrics"]["lexical_top1"]
    )


def test_selective_gate_requires_both_learned_margins_and_syllable_floor():
    gate = dict(
        gain_weights=[1.0] + [0.0] * (len(NAMES) - 1),
        positive_weights=[0.0] * len(NAMES),
        gain_margin=0.2,
        ranker_margin=0.1,
        positive_threshold=0,
        syllable_floor=-0.025,
        trees=[],
        tree_rate=0.12,
    )
    x = [0.0] * len(NAMES)
    x[0], x[1], x[2] = 1, 0.2, 0.05
    assert decision(gate, x)
    for index, value in ((0, 0.2), (1, 0.1), (2, -0.025)):
        blocked = list(x)
        blocked[index] = value
        assert not decision(gate, blocked)


@pytest.mark.parametrize(
    "source",
    [
        "Si el plan no resulta útil, no debe aplicarse.",
        "Aunque el aparato puede fallar, no siempre se produce daño.",
        "Un texto nuevo de un tema desconocido que no tiene evidencia local.",
        "Y aunque también puede afectar a niños y personas mayores, el 10 por 100 de los nuevos casos se detectan en personas de entre 50 y 60 años de edad y, en 3 de cada 4 pacientes, en mujeres.",
    ],
)
def test_no_unlicensed_support_for_unknown_or_changed_conditions(source):
    assert supports(source) == []


async def test_support_metrics_are_distinct_from_core_and_persisted(client, make_user):
    source = ARTICLES["antiguo egipto"].text
    result = await pipeline.run(source, 1)
    supported = [p for p in result.level_previews if p["pedagogical_support"]]
    assert supported
    for preview in supported:
        assert preview["pre_support_text"]
        assert (
            preview["pre_support_readability_score"] == measure(preview["pre_support_text"]).score
        )
        assert preview["readability_score"] == measure(preview["adapted_text"]).score
        assert all(f["evidence"] in source for f in preview["pedagogical_support"])
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": source, "level": 1}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pedagogical_support"] == data["level_previews"][0]["pedagogical_support"]
    assert data["pedagogical_support"]
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


@pytest.mark.parametrize("mutation", ["weight", "feature", "margin", "tree"])
def test_malformed_gate_is_rejected_before_inference(tmp_path, monkeypatch, mutation):
    from app.config import settings

    artifact = json.loads(ASSET.read_text())
    gate = artifact["sari_ranker"]["selective_gate"]
    if mutation == "weight":
        gate["gain_weights"].pop()
    elif mutation == "feature":
        gate["features"][0] = "wrong"
    elif mutation == "margin":
        gate["gain_margin"] = float("nan")
    else:
        gate["trees"] = [
            dict(feature=999, threshold=0, left={"value": [0] * 4}, right={"value": [0] * 4})
        ]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(artifact))
    monkeypatch.setattr(settings, "RANKER_CHECKPOINT", str(path))
    monkeypatch.setattr(settings, "RANKER_CHECKPOINT_SHA256", None)
    checkpoint.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="selective gate"):
            checkpoint()
    finally:
        checkpoint.cache_clear()
