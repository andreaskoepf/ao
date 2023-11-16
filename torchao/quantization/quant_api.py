# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""
Quantization APIs

Generally these APIs can be applied directly to any model
with Linear modules to obtain quantized linear ops. The intended
usage involves applying torch.compile to the model afterwards
both because primitives were designed based on the fusions that
come along with it and because that is how we access the intended quantized
and mixed GEMM kernels
"""

import torch
from .dynamic_quant import (
    DynamicallyPerAxisQuantizedLinear,
)
from .subclass import (
    DynamicallyQuantizedLinearWeight,
)
from .weight_only import (
    WeightOnlyInt8QuantLinear,
)

__all__ = [
    "apply_weight_only_int8_quant",
    "apply_dynamic_quant",
    "change_linear_weights_to_dqtensors",
]


def _replace_with_custom_fn_if_matches_filter(
    model, replacement_fn, filter_fn, cur_fqn=""
) -> None:
    """
    For each `child` in `model`, replaces it with `replacement_fn(child)`
    if `filter_fn(child)` is `True`
    """
    name_to_child = dict(model.named_children())
    for name, child in name_to_child.items():
        if cur_fqn == "":
            new_fqn = name
        else:
            new_fqn = f"{cur_fqn}.{name}"
        if filter_fn(child, new_fqn):
            new_child = replacement_fn(child)
            setattr(model, name, new_child)
        else:
            _replace_with_custom_fn_if_matches_filter(
                child, replacement_fn, filter_fn, new_fqn
            )
def apply_weight_only_int8_quant(model):
    """
    Applies weight-only symmetric per-channel int8 quantization to all linear layers
    in the given model using module swaps.
    """
    _replace_with_custom_fn_if_matches_filter(
        model,
        WeightOnlyInt8QuantLinear.from_float,
        lambda mod, fqn: isinstance(mod, torch.nn.Linear),
    )
def apply_dynamic_quant(model):
    """
    Applies dynamic symmetric per-token activation and per-channel weight
    quantization to all linear layers in the given model using
    module swaps.
    """
    _replace_with_custom_fn_if_matches_filter(
        model,
        lambda mod: DynamicallyPerAxisQuantizedLinear.from_float(mod),
        lambda mod, fqn: isinstance(mod, torch.nn.Linear),
    )
def change_linear_weights_to_dqtensors(model):
    """
    Converts all linear weight tensors to the `DynamicallyQuantizedLinearWeight`
    Tensor subclass, effectively applying the same form of quantization
    as apply_dynamic_quant while not modifying the linear modules.
    """
    def insert_subclass(lin):
        lin.weight = torch.nn.Parameter(
            DynamicallyQuantizedLinearWeight.from_float(lin.weight), requires_grad=False
        )
        return lin
    _replace_with_custom_fn_if_matches_filter(
        model, insert_subclass, lambda mod, fqn: isinstance(mod, torch.nn.Linear)
    )