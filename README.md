# 知识库构建与检索系统

## 项目介绍
这是一个基于多数据库架构的知识库构建与检索系统，专为企业内部知识管理设计。系统支持文档上传、智能解析、内容分块、多语言向量化和混合搜索功能，帮助企业构建智能化知识管理体系。

## 功能模块
根据CLAUDE.md中的需求分析，系统主要包含以下功能模块：

### 构建模块
1. **文档上传模块**：支持单文件和批量上传PDF、Word文档（最大100MB），文件长期保存
2. **文档解析模块**：自动提取文档内容、图片、表格和元数据
3. **智能分块模块**：基于章节结构的智能分块，支持表格特殊处理和预处理流水线
4. **向量化模块**：支持中英文混合内容的向量嵌入生成
5. **异步处理模块**：任务队列管理，支持进度实时监控

### 检索模块（后续实现）
1. **关键词检索模块**：基于ElasticSearch的全文检索
2. **语义检索模块**：基于Milvus的向量相似性搜索
3. **图谱检索模块**：基于Neo4j的知识图谱查询
4. **混合检索模块**：多检索方式结果融合

## 中间件选型
系统采用多数据库分离架构，各中间件选型如下：

### 关系数据库：PostgreSQL 15
- **选型理由**：ACID事务支持，复杂关联查询，数据完整性保证
- **用途**：存储用户信息、文档元数据、系统配置、任务状态等结构化数据
- **连接方式**：asyncpg驱动，连接池管理

### 全文检索引擎：ElasticSearch 8.12.0
- **选型理由**：成熟的开源搜索引擎，支持中文分词（IK Analyzer），相关性评分
- **用途**：文档内容索引，关键词搜索，布尔查询，高亮显示
- **配置**：单节点模式，跨域支持，中文分词器预配置

### 向量数据库：Milvus 2.4.0
- **选型理由**：专业的向量数据库，支持近似最近邻搜索，混合查询
- **用途**：存储文档向量嵌入，语义相似性搜索
- **架构依赖**：
  - **etcd**：元数据存储（集合schema、索引配置）
  - **Minio**：对象存储（向量数据文件）

### 图数据库：Neo4j 5.15.0
- **选型理由**：领先的图数据库，Cypher查询语言，图算法支持
- **用途**：知识图谱存储，实体关系查询，图遍历分析
- **插件**：APOC图算法插件，Graph Data Science插件

### 任务队列：Redis + RQ
- **选型理由**：轻量级Python任务队列，简单易用，快速实现
- **用途**：异步文档处理任务管理，任务状态跟踪，进度监控

### 对象存储：Minio
- **选型理由**：S3兼容的开源对象存储，易于部署和维护
- **用途**：
  - 存储Milvus向量数据文件
  - 存储上传的原始文档文件（长期保存）
- **特点**：提供Web控制台，支持桶策略和访问管理

## 部署指南

### 快速开始
```bash
# 克隆项目
git clone <repository-url>
cd knowlebase

# 一键启动所有服务（使用主docker-compose.yml）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down

# 单独启动中间件（用于本地开发调试）
# docker-compose -f docker-compose-midware.yml up -d

# 单独启动应用程序（需要中间件已运行）
# docker-compose -f docker-compose-app.yml up -d
```

### 服务端口映射
| 服务 | 容器端口 | 主机端口 | 说明 |
|------|----------|----------|------|
| PostgreSQL | 5432 | 5432 | 关系数据库 |
| ElasticSearch | 9200, 9300 | 9200, 9300 | 全文检索引擎 |
| Milvus | 19530, 9091 | 19530, 9091 | 向量数据库 |
| etcd | 2379 | 2379 | Milvus元数据存储 |
| Minio | 9000, 9090 | 9000, 9090 | 对象存储（文档文件和向量数据） |
| Neo4j | 7474, 7687 | 7474, 7687 | 图数据库 |
| Backend API | 8000 | 8000 | FastAPI后端 |
| Frontend | 5173 | 5173 | Vue3前端（开发） |

### 环境变量配置
复制 `.env.example` 为 `.env` 并修改配置：
```bash
cp .env.example .env
```

主要配置项：
```env
# 数据库连接
POSTGRES_USER=knowlebase
POSTGRES_PASSWORD=knowlebase_password
POSTGRES_DB=knowlebase

# ElasticSearch
ELASTICSEARCH_HOST=elasticsearch
ELASTICSEARCH_PORT=9200

# Milvus
MILVUS_HOST=milvus
MILVUS_PORT=19530

# Neo4j
NEO4J_URL=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=knowlebase_password
```

### 数据持久化
所有数据库数据存储在Docker volumes中：
- `postgres_data`: PostgreSQL数据
- `elasticsearch_data`: ElasticSearch索引
- `milvus_data`: Milvus向量数据
- `etcd_data`: etcd元数据
- `minio_data`: Minio对象存储数据
- `neo4j_data`: Neo4j图数据

备份数据：
```bash
# 备份PostgreSQL
docker exec knowlebase-postgres pg_dump -U knowlebase knowlebase > backup.sql

# 备份ElasticSearch索引（使用snapshot API）
```

## 配置管理和环境切换

### 多环境配置支持
项目支持灵活的配置管理，适应不同开发场景：

#### 1. 容器化部署（默认）
- 使用根目录 `.env` 文件（由 `docker-compose.yml` 读取）
- 所有服务都在 Docker 容器中运行
- Python 应用通过 Docker 网络访问其他服务（服务名如 `postgres`, `elasticsearch` 等）

#### 2. 本地混合开发
- 使用 `backend/.env` 文件（指向 `localhost`）
- 只启动数据库容器，Python 应用在宿主机运行
- 适合快速开发和调试

#### 3. 配置优先级
Python 应用配置读取优先级（从高到低）：
1. `backend/.env` 文件（如果存在）
2. 系统环境变量
3. 默认值

### 本地开发快速开始

#### 步骤1：启动数据库服务
```bash
# 只启动数据库和中间件（不启动后端应用）
docker-compose up -d postgres elasticsearch milvus etcd minio neo4j
```

#### 步骤2：配置本地环境
```bash
# backend/.env 已预先配置为 localhost
# 如果需要修改，编辑 backend/.env
```

#### 步骤3：设置Python虚拟环境
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 步骤4：运行后端应用
```bash
# 在虚拟环境中运行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 步骤5：访问应用
- API: http://localhost:8000
- API文档: http://localhost:8000/docs
- ElasticSearch: http://localhost:9200
- Neo4j Browser: http://localhost:7474 (用户名: neo4j, 密码: knowlebase_password)
- Minio Console: http://localhost:9090 (用户名: minioadmin, 密码: minioadmin)

### 切换回容器化部署
```bash
# 停止本地Python应用（Ctrl+C）
# 启动完整的容器化服务
docker-compose up -d

# 查看运行状态
docker-compose ps
```

### 开发环境搭建
详细开发步骤请参考CLAUDE.md中的需求分析和设计决策章节，以及backend/目录下的具体实现。

### 生产环境部署建议
1. **数据库分离部署**: 各数据库独立部署，配置集群和高可用
2. **安全加固**: 启用ElasticSearch安全特性，配置TLS加密和访问控制
3. **监控告警**: 配置Prometheus + Grafana监控各组件状态
4. **备份策略**: 定期备份数据库，测试恢复流程
5. **性能优化**: 根据负载调整资源配置，优化索引策略

### 云原生部署（可选）
- **Kubernetes**: 使用Helm charts部署各组件
- **对象存储**: 使用S3兼容存储替代Minio
- **服务网格**: 使用Istio进行流量管理和安全策略
- **CI/CD**: 自动化构建和部署流水线

## 许可证
待定

## 贡献指南
欢迎提交Issue和Pull Request。详细开发规范请参考CLAUDE.md中的设计决策部分。