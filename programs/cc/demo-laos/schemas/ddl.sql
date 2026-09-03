-- DDL for Learning Assessment OS — 核心表（MVP）。
-- 对应 schemas/ontology.py / state.py / evidence.py / item.py。
-- 优先级：Q 矩阵治理 > 题目参数估计；学生状态独立于知识图谱与题库。

-- ============ LKG：知识图谱 ============

CREATE TABLE knowledge (
    id            TEXT PRIMARY KEY,          -- K-<DOMAIN>-<SUBTYPE>-<SEQ>
    label         TEXT NOT NULL,
    domain        TEXT NOT NULL,
    sub_type      TEXT NOT NULL,
    contexts      JSONB DEFAULT '[]',
    common_errors JSONB DEFAULT '[]',
    version       TEXT DEFAULT '1.0'
);

CREATE TABLE task_capability (
    id               TEXT PRIMARY KEY,       -- CA01..CA05
    label            TEXT NOT NULL,
    domain           TEXT NOT NULL,
    literacy_weights JSONB DEFAULT '{}'      -- 一任务多素养，权重待校准
);

CREATE TABLE core_literacy (
    id    TEXT PRIMARY KEY,                  -- L01..L04
    label TEXT NOT NULL,
    version TEXT DEFAULT 'STD_1.0'
);

CREATE TABLE relation (
    id      TEXT PRIMARY KEY,                -- R-<SEQ>
    src     TEXT NOT NULL,
    dst     TEXT NOT NULL,
    type    TEXT NOT NULL,                   -- prerequisite/support/similarity/contrast/composition/transfer
    weight  REAL DEFAULT 1.0,                -- 条件依赖/证据权重，待校准
    version TEXT DEFAULT '1.0'
);

-- 标准层映射（标准层与知识层解耦）
CREATE TABLE standard_mapping (
    standard_id         TEXT,
    literacy_id         TEXT,
    task_id             TEXT,
    cognitive_process   TEXT,
    knowledge_id        TEXT,
    evidence_requirement TEXT,
    standard_version    TEXT DEFAULT 'STD_1.0',
    PRIMARY KEY (standard_id, knowledge_id, cognitive_process)
);

-- ============ Item & Q-Matrix ============

CREATE TABLE item (
    id            TEXT NOT NULL,
    version       TEXT NOT NULL,
    source        TEXT,
    text          TEXT NOT NULL,
    question      TEXT NOT NULL,
    answer        TEXT,
    options       JSONB DEFAULT '[]',
    score_rule    JSONB DEFAULT '{}',
    knowledge_tags JSONB DEFAULT '[]',
    cognitive_tags JSONB DEFAULT '[]',
    capability_tags JSONB DEFAULT '[]',
    literacy_tags  JSONB DEFAULT '[]',
    diagnostic_targets JSONB DEFAULT '[]',
    misconception_targets JSONB DEFAULT '[]',
    transfer_target TEXT,
    exposure_count INT DEFAULT 0,
    leakage_risk  TEXT DEFAULT 'low',
    irt_applicable BOOLEAN DEFAULT TRUE,    -- V2.2 §13.2 适用边界
    item_type     TEXT DEFAULT 'objective',
    audit_status  TEXT DEFAULT 'draft',
    quality       JSONB DEFAULT '{}',
    PRIMARY KEY (id, version)
);

CREATE TABLE q_matrix (
    item_id      TEXT NOT NULL,
    item_version TEXT NOT NULL,
    knowledge    TEXT NOT NULL,
    cognitive    TEXT NOT NULL,
    weight       REAL DEFAULT 1.0,
    is_primary   BOOLEAN DEFAULT TRUE,
    confidence   REAL DEFAULT 1.0,           -- 主观题附置信度
    PRIMARY KEY (item_id, item_version, knowledge, cognitive),
    FOREIGN KEY (item_id, item_version) REFERENCES item(id, version)
);

CREATE TABLE annotation_record (
    item_id            TEXT NOT NULL,
    annotators         JSONB DEFAULT '[]',
    labels             JSONB DEFAULT '{}',
    kappa              REAL DEFAULT 0.0,      -- < 0.6 退回重标
    krippendorff_alpha REAL DEFAULT 0.0,
    expert_arbitration  BOOLEAN DEFAULT FALSE,
    passed             BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (item_id)
);

-- ============ Evidence ============

CREATE TABLE evidence (
    id              TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL,
    item_id         TEXT NOT NULL,
    item_version    TEXT NOT NULL,
    assessment_id   TEXT,
    response        TEXT,
    score           REAL,
    response_time   REAL,
    hint_used       BOOLEAN DEFAULT FALSE,
    attempt         INT DEFAULT 1,
    rubric_version  TEXT,
    model_version   TEXT,
    qmatrix_version TEXT,
    standard_version TEXT DEFAULT 'STD_1.0',
    timestamp       TIMESTAMP,
    source          TEXT,                     -- direct_answer/scored/probe/transfer/external_anchor/...
    evidence_level  TEXT,                     -- A/B/C/D/E
    exposure_penalty REAL DEFAULT 0.0,        -- 同题重复降权
    provenance      JSONB DEFAULT '{}'        -- linked_state, weight
);
CREATE INDEX idx_evidence_student ON evidence(student_id);
CREATE INDEX idx_evidence_item ON evidence(item_id);

-- ============ Student Cognitive State ============

CREATE TABLE student_cognitive_state (
    student_id      TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    node_version    TEXT NOT NULL,
    domain          TEXT NOT NULL,
    core            JSONB DEFAULT '{}',       -- mastery/application/transfer
    dynamic         JSONB DEFAULT '{}',       -- stability/forgetting_risk
    diagnostic      JSONB DEFAULT '{}',       -- error_distribution/misconception
    uncertainty     JSONB DEFAULT '{}',       -- posterior_variance/confidence/evidence_count/...
    fusion          JSONB DEFAULT '{}',       -- posterior_mean/var/effective_n/model_contributions
    status          TEXT DEFAULT 'cold_start', -- ok/insufficient_evidence/cold_start
    meta            JSONB DEFAULT '{}',       -- state/model/qmatrix/standard version
    updated_at      TIMESTAMP,
    PRIMARY KEY (student_id, node_id)
);

-- ============ 横向：版本与审计（V2.2 §32 模型治理）============

CREATE TABLE model_version (
    version     TEXT PRIMARY KEY,
    component   TEXT,                          -- cdm/irt/adaptive/...
    trained_at  TIMESTAMP,
    metrics     JSONB DEFAULT '{}',
    retired     BOOLEAN DEFAULT FALSE
);
