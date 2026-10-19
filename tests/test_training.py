import csv
import io

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
