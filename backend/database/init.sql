-- 知识库系统数据库初始化脚本

-- 用户表（未来扩展）
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- 文档元数据表
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_size BIGINT,
    file_type VARCHAR(50),
    mime_type VARCHAR(100),

    -- 文档状态
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'processed', 'failed', 'deleted')),

    -- 处理信息
    chunk_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    embedding_model VARCHAR(50),

    -- 元数据
    source_type VARCHAR(50) CHECK (source_type IN ('upload', 'api', 'crawl', 'import')),
    language VARCHAR(10) DEFAULT 'zh',
    tags TEXT[],

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- 文档分块表（存储分块元数据，内容存储在ElasticSearch）
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    token_count INTEGER NOT NULL,

    -- 向量信息
    vector_id VARCHAR(100), -- Milvus中的向量ID
    embedding_model VARCHAR(50),

    -- 位置信息
    page_number INTEGER,
    section_title VARCHAR(500),
    start_position INTEGER,
    end_position INTEGER,

    -- 元数据
    metadata JSONB DEFAULT '{}'::jsonb,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    UNIQUE(document_id, chunk_index),
    CONSTRAINT check_chunk_index_positive CHECK (chunk_index >= 0)
);

-- 搜索历史表
CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    search_type VARCHAR(20) DEFAULT 'hybrid' CHECK (search_type IN ('keyword', 'semantic', 'hybrid', 'graph')),
    total_results INTEGER,
    processing_time_ms INTEGER,
    filters JSONB DEFAULT '{}'::jsonb,
    search_params JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(id)
);

-- 索引创建
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_tags ON documents USING GIN(tags);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_index ON document_chunks(chunk_index);
CREATE INDEX IF NOT EXISTS idx_document_chunks_vector_id ON document_chunks(vector_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata ON document_chunks USING GIN(metadata);

CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_search_history_created_at ON search_history(created_at);

-- 更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要更新时间的表添加触发器
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 插入默认配置
INSERT INTO system_config (key, value, description) VALUES
    ('embedding_model', '"BAAI/bge-small-zh-v1.5"', '默认向量嵌入模型'),
    ('chunk_size', '500', '文档分块大小（字符数）'),
    ('chunk_overlap', '50', '文档分块重叠大小'),
    ('search_weights', '{"keyword": 0.4, "semantic": 0.4, "graph": 0.2}', '混合搜索权重')
ON CONFLICT (key) DO NOTHING;

-- 创建默认管理员用户（密码：admin123，实际使用时应该修改）
INSERT INTO users (username, email, password_hash, is_superuser) VALUES
    ('admin', 'admin@knowlebase.local', '$2b$12$YourHashedPasswordHere', TRUE)
ON CONFLICT (username) DO NOTHING;