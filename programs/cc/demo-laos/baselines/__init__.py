"""Baseline A–E 对比框架。"""
from .core import (
    Baseline, BaselineA, BaselineB, BaselineC, BaselineD, BaselineE,
    ALL_BASELINES,
)
from .compare import run_baseline_comparison, comparison_table, BaselineRow
