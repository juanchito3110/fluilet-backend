"""Training-only shared regression trees; runtime uses plain Python JSON nodes."""


def fit_tree(x, residual, depth=3, minimum=20):
    import numpy as np

    def build(indices, remaining):
        average = residual[indices].mean(axis=0)
        if remaining == 0 or len(indices) < minimum * 2:
            return {"value": average.tolist()}
        best = None
        for feature in range(x.shape[1]):
            values = x[indices, feature]
            for threshold in np.unique(np.quantile(values, (0.1, 0.25, 0.5, 0.75, 0.9))):
                left = indices[values <= threshold]
                right = indices[values > threshold]
                if min(len(left), len(right)) < minimum:
                    continue
                error = sum(
                    ((residual[group] - residual[group].mean(axis=0)) ** 2).sum()
                    for group in (left, right)
                )
                if best is None or error < best[0]:
                    best = (error, feature, float(threshold), left, right)
        if best is None:
            return {"value": average.tolist()}
        _, feature, threshold, left, right = best
        return {
            "feature": feature,
            "threshold": threshold,
            "left": build(left, remaining - 1),
            "right": build(right, remaining - 1),
        }

    return build(np.arange(len(x)), depth)


def tree_outputs(tree, x):
    import numpy as np

    result = np.empty((len(x), 4))

    def visit(node, indices):
        if "value" in node:
            result[indices] = node["value"]
            return
        mask = x[indices, node["feature"]] <= node["threshold"]
        visit(node["left"], indices[mask])
        visit(node["right"], indices[~mask])

    visit(tree, np.arange(len(x)))
    return result


def fit(model, samples, history, rounds=25):
    import numpy as np

    from app.services.joint import sari_vector

    names = ("keep", "add", "delete", "utility")
    matrices = {
        name: (
            np.array([x for x, _ in values]),
            np.array([[y[k] for k in names] for _, y in values]),
        )
        for name, values in samples.items()
    }
    heads = np.array([model["heads"][name] for name in names])
    invariant = {
        name: np.array([sari_vector(row) for row in x]) for name, (x, _) in matrices.items()
    }
    predictions = {
        name: np.column_stack((invariant[name] @ heads[:3].T, x @ heads[3]))
        for name, (x, _) in matrices.items()
    }
    trees = []
    best = None
    records = []
    for iteration in range(1, rounds + 1):
        tree = fit_tree(invariant["train"], matrices["train"][1] - predictions["train"])
        trees.append(tree)
        for name in matrices:
            predictions[name] += 0.12 * tree_outputs(tree, invariant[name])
        record = dict(
            epoch=len(history) + iteration,
            stage="joint_residual_trees",
            train_loss=float(((predictions["train"] - matrices["train"][1]) ** 2).mean()),
            val_loss=float(((predictions["validation"] - matrices["validation"][1]) ** 2).mean()),
        )
        records.append(record)
        print(record, flush=True)
        if best is None or record["val_loss"] < best[0]:
            best = (record["val_loss"], len(trees))
    model["trees"] = trees[: best[1]]
    model["tree_rate"] = 0.12
    history.extend(records)
    return dict(rounds_executed=rounds, selected_trees=best[1], val_loss=best[0])
