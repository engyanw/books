"""核心实验验证体系（任务 #28）。"""
from .core import (
    MetricBundle, DiagnosticValidResult, EfficiencyResult,
    LearningGainResult, ExternalValidityResult, ExperimentReport,
    experiment_diagnostic_validity, experiment_assessment_efficiency,
    experiment_learning_gain, experiment_external_validity,
    run_all_experiments, auc, brier, f1,
)
