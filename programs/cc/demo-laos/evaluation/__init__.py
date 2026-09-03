"""效果验证体系（Phase 7 + 治理）。

- transfer.py：Pre/Post + 四层迁移验证（任务 #23）
- retention.py：个性化保持模型 + 干预效果评价（任务 #24）
- experiments.py：四类核心实验（任务 #28）
- baseline.py：五基线（任务 #2 的运行时实现）
"""
from .transfer import PrePostDesign, TransferLevel, TransferValidator
from .retention import RetentionModel, InterventionEffect
