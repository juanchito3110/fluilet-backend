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
sentence and Sinónimos, with legacy CP1252 encoding. The loader supports this and
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
