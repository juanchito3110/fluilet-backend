import csv
import io

import pytest

from ml_training.evaluate import evaluate_rows
from ml_training.prepare_easier import prepare


def test_official_semicolon_cp1252_format_and_no_split_leakage(tmp_path):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(["document_id", "word_id", "word", "sentence", "Sinónimos"])
    for index in range(100):
        writer.writerow(
            [str(index), "1", "utiliza", f"El alumno {index} utiliza libros.", "usa,emplea"]
        )
    # Duplicate source in another document must keep its first document owner.
    writer.writerow(["duplicate", "1", "utiliza", "El alumno 1 utiliza libros.", "usa,emplea"])
    path = tmp_path / "SGSS.csv"
    path.write_bytes(stream.getvalue().encode("cp1252"))
    partitions = prepare(path)
    assert all(partitions.values())
    assert sum(map(len, partitions.values())) == 200
    assert prepare(path) == partitions
    for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("document_id", "source"):
            assert not {row[key] for row in partitions[first]} & {
                row[key] for row in partitions[second]
            }
    assert all(
        row["annotation"] == "derived_lexical_substitution"
        for rows in partitions.values()
        for row in rows
    )


def test_evaluation_reports_acceptance_and_guard_separately():
    values = evaluate_rows(
        [
            {
                "source": "El niño no lee 20 libros.",
                "target": "El niño no lee 20 libros.",
                "prediction": "El niño lee 30 libros.",
            }
        ]
    )
    assert values["examples"] == 1
    assert values["lexical_fidelity_guard_rate"] == 0
    assert 0 <= values["reference_unigram_f1"] <= 1


def test_empty_generation_is_a_failed_evaluation_not_an_exception():
    result = evaluate_rows(
        [{"source": "El sol da luz.", "target": "El sol da luz.", "prediction": ""}]
    )
    assert result["acceptance_rate"] == 0
    assert result["adapted_score"] is None
    assert result["lexical_fidelity_guard_rate"] == 0


def test_official_legacy_undefined_bytes_are_rejected_explicitly(tmp_path):
    from ml_training.prepare_easier import prepare

    content = b"document_id;word_id;word;sentence;Sin\xf3nimos\n1;1;utiliza;El alumno utiliza libros.;usa\n2;1;utiliza;El alumno utiliza \x9d libros.;usa\n"
    path = tmp_path / "SGSS.csv"
    path.write_bytes(content)
    stats = {}
    result = prepare(path, stats=stats)
    assert stats["rows_read"] == 2 and stats["rejected_encoding_or_shape"] == 1
    assert sum(map(len, result.values())) == 1


def test_strict_rate_is_reported_separately_from_maintenance_exception():
    result = evaluate_rows(
        [{"source": "El sol da luz.", "target": "El sol da luz.", "prediction": "El sol da luz."}]
    )
    assert result["acceptance_rate"] == 1
    assert result["strict_double_condition_rate"] == 0
    assert result["maintenance_eligible_rate"] == 1
    assert result["original_score"] > 128.535


def test_mixed_utf8_and_cp1252_records_preserve_spanish_accents(tmp_path):
    from ml_training.prepare_easier import prepare

    path = tmp_path / "mixed.csv"
    path.write_bytes(
        "document_id;word_id;word;sentence;Sinónimos\n".encode("cp1252")
        + "1;1;utiliza;El niño utiliza libros.;usa\n".encode()
        + "2;1;utiliza;La niña utiliza libros.;usa\n".encode("cp1252")
    )
    stats = {}
    result = prepare(path, stats=stats)
    rows = [row for split in result.values() for row in split]
    assert len(rows) == 2
    assert {row["source"] for row in rows} == {"El niño utiliza libros.", "La niña utiliza libros."}
    assert stats.get("rejected_encoding_or_shape", 0) == 0


def test_model_sentinel_output_is_never_counted_as_readable_success():
    result = evaluate_rows(
        [
            {
                "source": "El niño lee libros en su casa.",
                "target": "El niño lee libros en su casa.",
                "prediction": "<extra_id_0>.",
            }
        ]
    )
    assert result["valid_predictions"] == 0
    assert result["adapted_score"] is None and result["score_delta"] is None
    assert result["strict_double_condition_rate"] == 0
    assert result["acceptance_rate"] == 0


def test_sentinel_mixed_with_source_is_rejected_by_runtime_fidelity_guard():
    from app.nlp.refinement import fidelity_ok

    source = "El sol da luz y el niño lee libros en casa."
    assert fidelity_ok(source, source)
    assert not fidelity_ok(source, source + " <extra_id_0>")


def test_subset_selection_is_deterministic_unique_and_budgeted():
    from ml_training.select_subset import select_rows

    class Tokenizer:
        @staticmethod
        def encode(text):
            return text.split()

    sentence = "El niño lee un libro en casa y su madre escucha el relato mientras la niña mira las hojas con calma."
    rows = [
        {"document_id": str(i // 2), "source": f"{sentence} {i}", "target": sentence}
        for i in range(20)
    ]
    rows.extend(
        [
            {"document_id": "short", "source": "El sol da luz.", "target": sentence},
            {"document_id": "long", "source": sentence, "target": sentence * 10},
        ]
    )
    first = select_rows(rows, Tokenizer(), 6, max_tokens=40)
    assert first == select_rows(list(reversed(rows)), Tokenizer(), 6, max_tokens=40)
    assert len({row["document_id"] for row in first}) == 6
    assert all(row["document_id"] not in {"short", "long"} for row in first)
    with pytest.raises(ValueError):
        select_rows(rows, Tokenizer(), 20, max_tokens=40)
    with pytest.raises(ValueError):
        select_rows(rows, Tokenizer(), 0)
