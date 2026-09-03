"""治理层（横切）。

- qmatrix.py：Q 矩阵治理与误标检测（任务 #25，V2.2 §31.2）
- fairness.py：公平性 / DIF 检测 / subgroup 校准（任务 #26，V2.2 §35 风险7）
- privacy.py：去标识化 / 审计链 / 可删除权（任务 #27，V2.2 §35 风险8）
"""
from .qmatrix import QMatrixValidator, inter_rater_kappa
from .fairness import DIFDetector, SubgroupCalibration
from .privacy import PrivacyGuard
