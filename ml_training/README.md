# Offline mT5/EASIER training

Use a separate Python 3.12 environment and install `ml_training/requirements.txt`
from the repository root. No GPU training, downloaded checkpoint or validated
clinical model is included in this commit. API traffic is never used for training.

Official data: https://github.com/LURMORENO/EASIER_CORPUS
Paper: https://doi.org/10.1371/journal.pone.0283622
The source declares CC BY-NC-ND 4.0. Confirm your research/training/distribution
rights before using it; this project does not redistribute the full corpus,
derived training files or large transformer weights. Six unchanged public
diagnostic rows are retained in `fixtures/easier_diagnostic.json`, with EASIER
provenance and its declared license, for reproducible regression checks.
Code works with a locally supplied SGSS.csv and does
not automatically download licensed datasets. Temporary dataset/checkpoint
artifacts are separate from the API's explicitly authorized, owner-scoped lesson
retention. Retained user lessons are never consumed by these training scripts.

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

The six-example EASIER set is retained and now explicitly informs rule calibration;
it is no longer a holdout. The separately reported
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


Calibration on 2026-10-20 used short contextual lexical pairs plus bounded clause,
goal and explicit-gloss templates. EASIER calibration improved from 0/6 to 5/6;
the synthetic developer diagnostic improved from 8/14 to 10/14. No model weights
or mathematical thresholds changed. The separate 12-document internal audit
(seed 314159; exclude six calibration documents; reuse select_rows with 96-token
budget and 20–45 words) remains 0/12. Do not present in-sample rule calibration
as generalization or human semantic validation. Exact selection commands and
six real base/checkpoint comparisons are recorded in docs/ml-evaluation.md and
docs/easier-calibration-results.json. Previous numeric evidence remains unchanged.


## Runtime lexical integration and graded evaluation

`app/services/resources.py` reuses this package's SGSS reader to cache every valid
locally supplied candidate with annotation context and frequency. Runtime replacements
require sentence overlap and agreement-safe curated forms. The complete index
includes contexts from the old six-case calibration subset: do not claim it as a
held-out evaluation. The full corpus and large checkpoints remain outside Git.

`python -m ml_training.evaluate_levels --output docs/pedagogical-evaluation-results.json`
measures five actual outputs on the 31 authored/aligned bank references. Optional
`--data` evaluates existing source JSON/JSONL separately. The script does not train
on API traffic, load weights, store source text in its report, or declare clinical
validity. The failed 120-step checkpoint is inventoried, not silently activated.
See `docs/pedagogical-simplification.md` for calibration provenance and limits.

## Reproducible v2 ranking model

`build_enhanced_dataset.py` filters SGSS, quarantines the six legacy diagnostic
documents/families, adds declared regular Spanish inflections and synthetic
sentence pairs, and audits document/source/registered-family partition separation.
`train_ranker.py` fits 52 logistic coefficients by real CPU SGD for 20 epochs,
records loss/F1/reference metrics and verifies changed finite weights. It does
not require Torch and is not a new mT5 fine-tune. `evaluate_baseline.py` executes
the archived v1 code with identical inputs; `evaluate_retrained.py` evaluates the
current complete system and packages the checkpoint/metrics for production.

The small JSON ranker is intentionally distributed in `app/services/assets/`,
byte-identical to `checkpoints/context-ranker-v2/model.json`. Only numeric
`checkpoints/retraining_metrics.json` is whitelisted under checkpoints in Git.
SGSS inference candidates and their frequencies are restricted to the recorded
training documents/families/targets. Full data derivatives remain ignored; no
API traffic is training data. See [the complete report](../docs/model-retraining-report.md)
for reproduction, held-out limitations, low lexical F1 and the absence of an
aggregate SARI improvement from the learned weights alone.


## Historical v2.1 joint fit and release

Use `build_enhanced_dataset`, `train_joint --epochs 35`, then `export_joint`.
The builder now yields 4,738 pairs (4,108/402/228), with 21 explicitly regular verb
families and grouped document/source/family split audits. Joint training fits
keep/add/delete, multi-objective utility and lexical pairwise heads, followed by
25 depth-3 shared residual-tree rounds. NumPy is training-only. Compression policy
and SARI/utility mixture use validation; `joint_policy.frozen` runs the fc12a7a
baseline in an isolated archived checkout. A full Git history containing that
commit is required to reproduce it.

`export_joint` selects the newly fitted checkpoint in a temporary evaluation
context, independent of any serving checkpoint configured in the environment.
It publishes the small JSON model, actual band counts and numeric report. Only
`checkpoints/retraining_metrics.json` is whitelisted in that directory for Git;
the release copy is `app/services/assets/context-ranker-v2.1.json`. Inference is
pure Python and needs neither NumPy nor Torch.

Results do **not** support a 100 percent closure: 44.529 SARI versus 44.544 baseline;
top-1 and band distance improve, while exact five-band compliance remains 4/31
local articles, 1/6 known EASIER diagnostics and 0/6 controlled developer inputs.
The API exposes `acceptance_criteria_met=false`. The [v2.1 report](../docs/model-retraining-v2.1.md)
retains this negative result and separates it from 31/31 and 6/6 monotonicity.
SGSS lexical proposals and synthetic inflections are not five reviewed child-age
paraphrases of each source. Do not relabel them as independent gold supervision.


## Historical v2.2: independent lexical/SARI selection

```sh
python -m pip install 'numpy>=2,<3'
python -m ml_training.build_enhanced_dataset
python -m ml_training.train_separated
python -m ml_training.calibrate_lexical
MT5_ENABLED=false python -m ml_training.export_separated
```

The unchanged 4,108/402/228 partitions are hash-audited. Fit uses train only;
validation selects residual-tree count, lexical epoch, confidence weights, edit
cost and margin. Corpus candidate ranks and word frequencies come exclusively
from train. Frequencies are sample counts, not a representative Spanish norm.
The selected source candidates never contain an inserted validation/test label.
Structural calibration is a separate measured search over complete clauses and
explicit Spanish periphrases. Its target bands and requested age/level never
enter the lexical scoring features. NumPy is only needed to train; the released
JSON runs with the lightweight API dependencies.

The new asset is `app/services/assets/context-ranker-v2.2.json`, copied unchanged
to `checkpoints/context-ranker-v2.2/model.json`. The report includes failed trials
and exact comparisons. The test split has been observed repeatedly during this
project; no test label is used for gradients, priors, epoch or margin fitting,
but these results are not an independent blind evaluation. Obtain a newly locked
external test set before claiming generalization or efficacy. SGSS lexical
annotations and synthetic inflections do not validate child comprehension.

Final SARI remains below baseline (44.5396647 vs 44.5438479), while lexical top-1
improves to 73.25%. The API keeps `acceptance_criteria_met=false`. Full report:
[model-retraining-report.md](../docs/model-retraining-report.md).


## Current v2.3: frozen selective gate and grounded controller

Run `python -m ml_training.fit_selection_gate`, then
`python -m ml_training.evaluate_selection_gate`, then
`python -m ml_training.export_gate`. Fit reads only the hash-verified train and
validation partitions; the evaluator checks the frozen selection hash before
opening test. Source-only train alternatives and document weighting yield 2,933
non-agreement comparisons. Thirty features, regularized gain regression, 80
residual rounds (one selected) and validation margins are recorded in the release.
The lexical head is retained byte for byte. Final margins are permissive; the
validation-fitted syllable veto is decisive, rather than an asserted independent
neural gain.

Measured SARI: **44.557636124674 > 44.543847868458**, lexical top-1 **73.245614%**.
All five bands and strict progression hold for **31/31 bank, 6/6 known EASIER,
6/6 controlled sources and 15/15 managed demos**. The separate length-based
`target_met` is not universally satisfied. The API exposes measured acceptance
true for those criteria. These known development cohorts and the repeatedly
observed legacy test are not blind external or clinical validation.

Source-grounded finite supports expose evidence and the score before support;
no repeated generic filler or arbitrary new-domain assertions are added. See
[the full protocol, negative trials and metrics](../docs/model-retraining-report.md).
The dependency-free runtime asset is under 2 MB; raw datasets, environments,
secrets and neural weights remain ignored.
