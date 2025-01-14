# Copyright ServiceNow, Inc. 2021 – 2022
# This source code is licensed under the Apache 2.0 license found in the LICENSE file
# in the root directory of this source tree.

from copy import deepcopy
from typing import Any, List

import numpy as np
import pytest

from azimuth.dataset_split_manager import DatasetSplitManager
from azimuth.modules.dataset_analysis.dataset_warnings import DatasetWarningsModule
from azimuth.types import DatasetSplitName, ModuleOptions


@pytest.mark.parametrize("remove_one_class", [True, False])
@pytest.mark.parametrize("rejection_class", [True, False])
def test_compute_on_dataset_split(
    simple_text_config, apply_mocked_startup_task, rejection_class, remove_one_class, monkeypatch
):
    mod = DatasetWarningsModule(
        dataset_split_name=DatasetSplitName.all,
        config=simple_text_config,
    )

    if rejection_class:
        add_rejection_class(mod, monkeypatch=monkeypatch)
        assert "NO_INTENT" in mod.get_dataset_split_manager(DatasetSplitName.eval).get_class_names(
            labels_only=True
        )
    if remove_one_class:
        original_length = len(mod.get_dataset_split(DatasetSplitName.eval))
        remove_one_cls(mod)
        assert original_length > len(mod.get_dataset_split(DatasetSplitName.eval))

    output = mod.compute_on_dataset_split()[0].warning_groups
    num_classes = mod.get_dataset_split_manager(DatasetSplitName.eval).get_num_classes(
        labels_only=True
    )

    assert isinstance(output, List)

    general_warnings: Any = output[0]
    syntactic_warnings: Any = output[1]
    assert general_warnings.name == "General Warnings"
    assert syntactic_warnings.name == "Syntactic Warnings"

    # Test general_warnings
    assert len(general_warnings.warnings) == 3

    # Test Number of samples per class
    nb_samples_class = general_warnings.warnings[0]
    nb_samples_class_train_values = [x.data[0].value for x in nb_samples_class.comparisons]
    nb_samples_class_eval_values = [x.data[1].value for x in nb_samples_class.comparisons]
    assert sum(nb_samples_class_train_values) == len(mod.get_dataset_split(DatasetSplitName.train))
    assert sum(nb_samples_class_eval_values) == len(mod.get_dataset_split(DatasetSplitName.eval))
    assert len(nb_samples_class.plots.overall.data) > 0
    assert nb_samples_class.plots.overall.layout

    # Test Class Imbalance
    class_imbalance_warnings = general_warnings.warnings[0]
    perc_values = [x.data[0].value for x in class_imbalance_warnings.comparisons]
    # All percentage values should be higher than -100.
    assert (np.array(perc_values) >= -100).all()
    assert len(class_imbalance_warnings.plots.overall.data) > 0
    assert class_imbalance_warnings.plots.overall.layout

    # Test Class representation
    class_repr = general_warnings.warnings[1]
    class_repr_delta_values = [x.data[0].value for x in class_repr.comparisons]
    assert (np.array(class_repr_delta_values) <= 1).all() and (
        np.array(class_repr_delta_values) >= -1
    ).all()
    assert len(class_repr.plots.overall.data) > 0
    assert class_repr.plots.overall.layout

    # Token length portion
    tokens = syntactic_warnings.warnings[0]
    assert len(tokens.comparisons) == num_classes
    assert tokens.columns == ["mean", "std"]
    assert len(tokens.plots.overall.data) > 0
    assert tokens.plots.overall.layout
    assert all([len(p.data) > 0 for cls_name, p in tokens.plots.per_class.items()])
    assert all([p.layout for p in tokens.plots.per_class.values()])


def add_rejection_class(mod, monkeypatch):
    # Adding a rejection class
    eval_dm: DatasetSplitManager = mod.get_dataset_split_manager(DatasetSplitName.eval)
    train_dm: DatasetSplitManager = mod.get_dataset_split_manager(DatasetSplitName.train)
    eval_dm._base_dataset_split.features["label"].names.append("NO_INTENT")  # Should be 2
    train_dm._base_dataset_split.features["label"].names.append("NO_INTENT")  # Should be 2
    eval_dm._base_dataset_split = eval_dm._base_dataset_split.map(
        lambda u, i: {"label": 2 if i % 10 == 0 else u["label"]}, with_indices=True
    )
    dms = {
        DatasetSplitName.eval: eval_dm,
        DatasetSplitName.train: train_dm,
    }
    # Modifying the config reset the ArtifactManager, which we do not want.
    monkeypatch.setattr(mod, "get_dataset_split_manager", lambda s: dms[s])
    mod.config.rejection_class = "NO_INTENT"


def remove_one_cls(mod):
    # Remove class 0 from eval set
    eval_ds: DatasetSplitManager = mod.get_dataset_split_manager(DatasetSplitName.eval)
    augmented = deepcopy(eval_ds._base_dataset_split.filter(lambda u: u["label"] != 0))
    mod.get_dataset_split_manager(DatasetSplitName.eval)._base_dataset_split = augmented


def test_with_dataset_and_indices(simple_text_config):
    with pytest.raises(ValueError):
        DatasetWarningsModule(
            dataset_split_name=DatasetSplitName.eval,
            config=simple_text_config,
        )

    with pytest.raises(ValueError):
        DatasetWarningsModule(
            dataset_split_name=DatasetSplitName.all,
            config=simple_text_config,
            mod_options=ModuleOptions(indices=[1, 2]),
        )
