"""Reproducible v2 corpus, quarantined diagnostic documents and split audit.

Augmentation is explicitly synthetic supervision, never new EASIER annotation.
Families crossing document partitions are purged, not silently re-assigned.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from app.nlp.readability import measure
from app.nlp.segmentation import words
from app.nlp.syllables import count_syllables
from app.services.morphology import entries, family
from ml_training.prepare_easier import load_rows, normalized, prepare, split_for

SPLITS = ("train", "validation", "test")
DOMAINS = {
    "science": ("Los científicos", "los datos del clima"),
    "history": ("Los historiadores", "los mapas del pasado"),
    "legal": ("Los jueces", "las pruebas del caso"),
    "medical": ("Los médicos", "los datos del estudio"),
    "sports": ("Los técnicos", "los planes del equipo"),
    "school": ("Los docentes", "los libros de la clase"),
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def band(text):
    score = measure(text).score
    return next(
        (level for level, threshold in enumerate((82, 74, 65, 58), 1) if score >= threshold), 5
    )


def build(csv_path, benchmark_path, output, seed=20261027):
    raw_benchmark = benchmark_path.read_text()
    benchmark = (
        json.loads(raw_benchmark)
        if raw_benchmark.lstrip().startswith("[")
        else [json.loads(line) for line in raw_benchmark.splitlines() if line.strip()]
    )
    blocked_docs = {row["document_id"] for row in benchmark}
    blocked_sources = {normalized(" ".join(row["source"].split())) for row in benchmark}
    raw = list(load_rows(csv_path))
    blocked_families = {
        family(row["word"])
        for row in raw
        if row["document_id"] in blocked_docs
        or normalized(" ".join(row["source"].split())) in blocked_sources
    }
    rows, filtered = [], Counter()
    for row in raw:
        source, word, document = row["source"], row["word"], row["document_id"]
        if document in blocked_docs or normalized(" ".join(source.split())) in blocked_sources:
            filtered["quarantined_document"] += 1
            continue
        if not source or not word or not document:
            filtered["missing"] += 1
            continue
        matches = list(re.finditer(r"(?<!\w)" + re.escape(word) + r"(?!\w)", source, re.I))
        if len(matches) != 1:
            filtered["ambiguous_span"] += 1
            continue
        for target in row["synonyms"].split(","):
            target = target.strip().strip("\"'[] ")
            if (
                not re.fullmatch(r"[^\W\d_]+(?:[ -][^\W\d_]+){0,4}", target)
                or len(target) >= len(word)
                or sum(count_syllables(w) for w in words(target))
                >= sum(count_syllables(w) for w in words(word))
            ):
                filtered["not_shorter_or_noisy"] += 1
                continue
            group = family(word)
            if group in blocked_families:
                filtered["quarantined_family"] += 1
                continue
            match = matches[0]
            if source[match.start()].isupper():
                target = target.capitalize()
            rows.append(
                dict(
                    source=source,
                    target=source[: match.start()] + target + source[match.end() :],
                    word=word,
                    replacement=target,
                    document_id="easier:" + document,
                    family=group,
                    provenance="EASIER_filtered_annotation",
                    morphology="observed",
                )
            )

    # Explicit inflections only; all descendants of a lemma share one group/document.
    persons = ("Yo", "Tú", "Él", "Nosotros", "Vosotros", "Ellos")
    for lemma, source, target, tense, person in entries():
        if lemma in blocked_families or source == target:
            continue
        for domain, (subject, obj) in DOMAINS.items():
            if tense == "participle":
                prefix = ("El libro fue", "La carta fue", "Los libros fueron", "Las cartas fueron")[
                    person
                ]
                text, simple = f"{prefix} {source}.", f"{prefix} {target}."
            elif tense == "gerund":
                text, simple = (
                    f"{subject} están {source} {obj}.",
                    f"{subject} están {target} {obj}.",
                )
            elif tense == "infinitive":
                text, simple = (
                    f"{subject} pueden {source} {obj}.",
                    f"{subject} pueden {target} {obj}.",
                )
            elif tense in ("gender_number", "nominalization"):
                # Lexical morphology records, not fictitious parallel prose.
                text, simple = source, target
            else:
                text, simple = (
                    f"{persons[person]} {source} {obj}.",
                    f"{persons[person]} {target} {obj}.",
                )
            # Some verbs cannot take these objects (e.g. colaborar): lexical-only supervision.
            if lemma in {"retornar", "colaborar", "dialogar", "aminorar", "adicionar"}:
                text, simple = source, target
            rows.append(
                dict(
                    source=text,
                    target=simple,
                    word=source,
                    replacement=target,
                    document_id="morph:" + lemma,
                    family=lemma,
                    provenance="authored_morphological_augmentation",
                    morphology=tense,
                    domain=domain,
                )
            )

    for domain, (subject, obj) in DOMAINS.items():
        for _operation, (complex_verb, simple_verb) in enumerate(
            [
                ("utilizan", "usan"),
                ("observan", "miran"),
                ("elaboran", "crean"),
                ("finalizan", "acaban"),
                ("incrementan", "aumentan"),
            ]
        ):
            lemma = family(complex_verb)
            if lemma in blocked_families:
                continue
            for detail in ("durante la mañana", "en la sala del centro", "con ayuda del equipo"):
                source = f"{subject} {complex_verb} {obj} {detail} y explican su trabajo al grupo, por lo que todos conocen los pasos del plan."
                target = f"{subject} {simple_verb} {obj} {detail}. {subject} explican su trabajo al grupo. Por eso, todos conocen los pasos del plan."
                rows.append(
                    dict(
                        source=source,
                        target=target,
                        word=complex_verb,
                        replacement=simple_verb,
                        document_id="morph:" + lemma,
                        family=lemma,
                        provenance="authored_syntactic_parallel",
                        morphology="syntax",
                        domain=domain,
                    )
                )

    # Union duplicate source sentences into one document component before splitting.
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    sources = {}
    for row in rows:
        key = normalized(" ".join(row["source"].split()))
        doc = row["document_id"]
        owner = sources.setdefault(key, doc)
        first, second = find(doc), find(owner)
        parent[max(first, second)] = min(first, second)
    for row in rows:
        row["document_id"] = find(row["document_id"])
        row["split"] = split_for(row["document_id"], seed)
    # A family occurring in more than one partition is quarantined to its
    # lexicographically first document's partition; other occurrences are dropped.
    owners = {}
    for row in sorted(rows, key=lambda r: r["document_id"]):
        owners.setdefault(row["family"], row["split"])
    partitions, seen = {name: [] for name in SPLITS}, set()
    for row in rows:
        if row["split"] != owners[row["family"]]:
            filtered["cross_partition_family"] += 1
            continue
        key = (row["source"], row["target"])
        if key in seen:
            continue
        seen.add(key)
        row["level"] = band(row["target"])
        row["age_group"] = {1: "6-8", 2: "6-8", 3: "9-11", 4: "12+", 5: "12+"}[row["level"]]
        partitions[row["split"]].append(row)
    assert all(partitions.values()), "Empty partition; choose another recorded seed"
    for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("document_id", "family", "source"):
            assert not (
                {row[key] for row in partitions[first]} & {row[key] for row in partitions[second]}
            ), key
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, values in partitions.items():
        path = output / (name + ".jsonl")
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values)
        )
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    values = [row for group in partitions.values() for row in group]
    manifest = dict(
        version="fluilet-dataset-v2",
        seed=seed,
        source_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        v1={
            "raw_rows": len(raw),
            "previous_smoke_pairs": 34,
            "full_unfiltered_derived_pairs": sum(map(len, prepare(csv_path).values())),
        },
        v2={
            "total_pairs": len(values),
            "lexical_pairs": sum(row["morphology"] != "syntax" for row in values),
            "syntactic_parallel": sum(row["morphology"] == "syntax" for row in values),
            "morphology": dict(Counter(row["morphology"] for row in values)),
            "levels": dict(Counter(row["level"] for row in values)),
            "partitions": {name: len(value) for name, value in partitions.items()},
            "provenance": dict(Counter(row["provenance"] for row in values)),
        },
        filtered=dict(filtered),
        split_sha256=hashes,
        quarantine_documents=sorted(blocked_docs),
        quarantine_family_count=len(blocked_families),
        leakage_audit="document/source/family intersections empty",
        limitations=[
            "SGSS labels are lexical proposals, not certified sentence paraphrases",
            "synthetic contexts and regular-verb forms are weak supervision, not clinical observations",
            "the six legacy diagnostics informed v1 rules: not an unseen independent benchmark",
        ],
        license="EASIER source declares CC BY-NC-ND 4.0; local research derivatives remain untracked",
    )
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("datasets/EASIER/SGSS.csv"))
    parser.add_argument(
        "--benchmark", type=Path, default=Path("ml_training/fixtures/easier_diagnostic.json")
    )
    parser.add_argument("--output", type=Path, default=Path("ml_training/data/enhanced-v2"))
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.benchmark, args.output)["v2"]))


if __name__ == "__main__":
    main()
