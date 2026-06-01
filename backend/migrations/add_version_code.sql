-- 迁移：为 knowledge_base_version 添加 version_code 字段
-- 日期：2026-06-01
-- 说明：新增 version_code (BIGINT, 毫秒时间戳)，从 version_name 解析回填

-- Step 1: 添加 column（先允许 NULL）
ALTER TABLE knowledge_base_version
    ADD COLUMN IF NOT EXISTS version_code BIGINT;

-- Step 2: 从 version_name 解析回填已有数据
-- version_name 格式: vYYYYMMDD_HHMMSS (如 v20260422_103000)
UPDATE knowledge_base_version
SET version_code = EXTRACT(EPOCH FROM TO_TIMESTAMP(
    SUBSTRING(version_name FROM 2), 'YYYYMMDD_HH24MISS'
)) * 1000
WHERE version_code IS NULL;

-- Step 3: 回填后加 NOT NULL 和 UNIQUE 约束
ALTER TABLE knowledge_base_version
    ALTER COLUMN version_code SET NOT NULL;

ALTER TABLE knowledge_base_version
    ADD CONSTRAINT uq_kb_version_version_code UNIQUE (version_code);
