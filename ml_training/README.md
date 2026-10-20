# Offline mT5/EASIER training

Use a separate Python 3.12 environment and install `ml_training/requirements.txt`
from the repository root. No GPU training, downloaded checkpoint or validated
clinical model is included in this commit. API traffic is never used for training.

Official data: https://github.com/LURMORENO/EASIER_CORPUS
Paper: https://doi.org/10.1371/journal.pone.0283622
The source declares CC BY-NC-ND 4.0. Confirm your research/training/distribution
rights before using it; this project does not redistribute the corpus, derived
training files or weights. Code works with a locally supplied SGSS.csv and does
not automatically download licensed datasets. Temporary dataset/checkpoint
artifacts are separate from the API's zero-retention user-document policy.

EASIER supplies complex-word annotations and proposed synonyms, not a clinically
validated parallel corpus of full syntactic rewrites for children with TDAH or
dyslexia. Generated pairs are explicitly tagged derived_lexical_substitution.
Syntactic supervision and target-population validation need additional reviewed
data; do not fabricate either with automatic replacements.

The official file has semicolon-delimited columns document_id, word_id, word,
sentence and Sinónimos, with mixed UTF-8/legacy CP1252 encoding. The loader supports this and
UTF-8/TSV, requires an unambiguous single target-word occurrence, keeps all variants
of a source sentence together and partitions by document. A manifest records input
SHA-256, seed and counts. Duplicate sources in other documents retain one owner.

```sh
python -m ml_training.prepare_easier --sgss datasets/EASIER/SGSS.csv --output ml_training/data
python -m ml_training.train --config ml_training/configs/mt5_small.yaml --data ml_training/data --output checkpoints/mt5-fluilet
python -m ml_training.evaluate --data ml_training/data/test.jsonl --checkpoint checkpoints/mt5-fluilet
```

All partitions must be nonempty. Training checks cross-partition source/document
leakage, sets seeds, filters rather than truncates over-budget examples, uses the
same inference prefix, saves tokenizer/weights and a training manifest with test
loss. Reproducibility is best-effort across GPU hardware/kernels; record hardware
and package versions in experiment records. Run training separately from serving.

Evaluation prints aggregate raw scores, acceptance rate, reference unigram F1 and
lexical-guard rate. These are not semantic or clinical proofs. Include blinded
human review of grammar, facts, negation, entities, meaning and comprehension with
the intended population before claiming clinical efficacy. A base-model inference
run is not evidence of a trained or validated simplifier. Complete the runtime
chunk/document gate even when offline sentence metrics look good.

## Reproducible lightweight run

`configs/mt5_small_smoke.yaml` pins google/mt5-small revision and configures a CPU
LoRA experiment (rank 4, q/v/lm_head modules, 120 steps). It is a pipeline validation run,
not a clinical model. Use `python -m ml_training.select_subset --help` to select
24/4/6 document-disjoint examples (20–45 words, at most 96 tokens) after preparation.
The loader handles the official file's mixed UTF-8/CP1252 encoding per line; malformed
annotations are counted/rejected explicitly. We use the slow SentencePiece tokenizer
to preserve byte fallback and avoid conversion-induced unknown tokens.

Training verifies finite loss/parameters, changed trainable-weight hashes and saves
adapter plus merged checkpoint. The optional resource/RSS measurement is supported
on macOS/Linux and omitted on Windows. Evaluation adds original scores, strict
>=15 AND >=65 rate, maintenance rate, valid-output counts, measured inference times
and optional --hybrid evaluation through the actual API pipeline. Raw model control
markers (for example extra_id sentinels) are invalid outputs with no readability
score; they count as failures in rates. See docs/ml-evaluation.md for the observed
experiment and exact reproduction commands. The observed checkpoint did not produce
acceptable simplifications on the six exploratory test cases; it was not activated
in the API. No API traffic is used for training.

## Complete-system evaluation

`evaluate.py --hybrid` measures raw model generation and the actual complete API
pipeline on the same inputs, with separately reported acceptance coverage,
abstention, strict compliance among accepted non-maintenance outputs, maintenance
counts and lexical-guard compliance. It also records model generation calls and
expert attribution: a result produced by rules is never credited to mT5. The
production policy tries a deterministic candidate first, then mT5 and refinement.
Readability/fidelity gates still apply at both chunk and document level.

The frozen six-example EASIER set is retained. The separately reported
`fixtures/hybrid_es.json` contains 14 synthetic developer diagnostic cases,
including unsupported inputs, negation, numbers, syntax and maintenance. It is
not EASIER, a blind holdout or clinical evidence. Its reference is the original
text; reference unigram F1 therefore measures overlap rather than quality against
a human simplification. Never pool it with EASIER to inflate acceptance coverage.

```sh
python -m ml_training.evaluate --data ml_training/data/easier-smoke/test.jsonl --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/easier-tuned-hybrid.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
python -m ml_training.evaluate --data ml_training/fixtures/hybrid_es.json --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/diagnostic-tuned-hybrid.json --max-input-tokens 512 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
```

Repeat both commands with the pinned local base-model snapshot as `--checkpoint`
to obtain the full comparison. See `docs/ml-evaluation.md` and
`docs/hybrid-evaluation-results.json` for the actual observations. The mathematical
gate guarantees compliance of returned adaptations (with the declared maintenance
exception); it cannot guarantee acceptance of every input or semantic equivalence.
