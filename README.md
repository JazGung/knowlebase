# 知识库构建/检索系统

这是一个知识库构建和检索系统，分为前端和后端两部分。

## 项目结构

```
knowlebase/
├── frontend/          # Vue3 前端
├── backend/           # Python 后端
├── .gitignore         # Git 忽略文件
└── README.md          # 项目说明
```

## 技术栈

### 前端
- Vue 3
- 现代化的 UI 框架（待定）
- 构建工具：Vite / Webpack

### 后端
- **Web框架**: FastAPI（异步支持，高性能）
- **编程语言**: Python 3.10+

### 中间件架构
采用多数据库分离架构，各司其职：

| 组件 | 用途 | 说明 |
|------|------|------|
| **PostgreSQL** | 关系数据库 | 存储用户信息、文档元数据、系统配置等结构化数据，保证事务一致性 |
| **ElasticSearch** | 全文检索引擎 | 关键词搜索、文档内容索引、中文分词（IK Analyzer） |
| **Milvus** | 向量数据库 | 语义搜索、向量相似性检索，存储文档嵌入向量 |
| **Neo4j** | 图数据库 | 知识图谱构建、实体关系存储、图算法分析 |
| **Redis** | 缓存（可选） | 热点数据缓存、会话存储（未来扩展） |
| **消息队列**（可选） | 异步任务 | 文档解析、向量化等耗时任务异步处理 |

### 为什么需要关系数据库？
尽管有ElasticSearch（全文检索）、Milvus（向量搜索）、Neo4j（图查询），但仍需要关系数据库的原因：
1. **事务一致性**: 用户管理、权限控制需要ACID事务保证
2. **结构化数据**: 文档元数据、系统配置等结构化数据更适合关系模型
3. **复杂查询**: 关联查询、聚合统计在关系数据库中更高效
4. **数据完整性**: 外键约束、数据类型校验确保数据质量
5. **运维成熟度**: 关系数据库的备份、监控、运维工具更成熟

## 功能规划

### 核心功能
1. 知识文档上传与管理
2. 文档内容解析与向量化
3. 语义搜索与检索
4. 知识图谱构建
5. 用户权限管理

### 扩展功能
- 多格式文档支持（PDF、DOCX、TXT、Markdown等）
- API 接口
- 批量导入/导出
- 统计分析

## 中间件架构详细说明

### 数据流向设计
```
用户请求 → FastAPI后端 → 根据查询类型路由到相应数据库
                    ├─→ PostgreSQL（元数据查询、用户管理）
                    ├─→ ElasticSearch（关键词全文检索）
                    ├─→ Milvus（语义向量搜索）
                    └─→ Neo4j（知识图谱查询）
```

### 各组件职责
1. **PostgreSQL (关系数据库)**
   - 用户认证和权限管理
   - 文档元数据存储（标题、文件名、大小、状态等）
   - 系统配置管理
   - 搜索历史记录
   - 事务性操作保证数据一致性

2. **ElasticSearch (全文检索引擎)**
   - 文档内容存储和索引
   - 中文分词（IK Analyzer）
   - 关键词搜索、模糊匹配、布尔查询
   - 搜索结果相关性评分
   - 支持高亮显示、分面搜索

3. **Milvus (向量数据库)**
   - 存储文档分块的嵌入向量（512维）
   - 语义相似度搜索
   - 支持混合查询（向量+标量过滤）
   - 近似最近邻搜索（ANN）
   - 支持多种索引类型（IVF_FLAT、HNSW等）
   
   **架构依赖**:
   - **etcd**: 元数据存储（集合schema、索引配置、节点注册等）
   - **Minio**: 对象存储（实际向量数据文件存储）
   - **说明**: Milvus采用存算分离架构，etcd存储元数据，Minio存储向量数据，计算节点无状态，便于扩展

4. **Neo4j (图数据库)**
   - 实体识别和关系抽取
   - 知识图谱构建和存储
   - 图遍历查询（Cypher语言）
   - 社区发现、中心性分析等图算法
   - 可视化知识图谱

### 数据同步机制
- **文档上传**: 内容存ElasticSearch，向量存Milvus，元数据存PostgreSQL，关系存Neo4j
- **数据一致性**: 通过事务和补偿机制保证
- **增量更新**: 支持文档更新和删除的同步

## Docker Compose 部署

### 快速开始
```bash
# 克隆项目
git clone <repository-url>
cd knowlebase

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

### 服务端口映射
| 服务 | 容器端口 | 主机端口 | 说明 |
|------|----------|----------|------|
| PostgreSQL | 5432 | 5432 | 关系数据库 |
| ElasticSearch | 9200, 9300 | 9200, 9300 | 全文检索引擎 |
| Milvus | 19530, 9091 | 19530, 9091 | 向量数据库 |
| etcd | 2379 | 2379 | Milvus元数据存储 |
| Minio | 9000, 9090 | 9000, 9090 | Milvus对象存储（S3兼容） |
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

## 开发环境搭建

### 前端开发
```bash
cd frontend
# 安装依赖、启动开发服务器等
```

### 后端开发
```bash
cd backend
# 创建虚拟环境、安装依赖、启动服务器等
```

## 部署

### 生产环境建议
1. **数据库分离**: 各数据库独立部署，配置集群
2. **安全加固**: 启用ElasticSearch安全特性，配置防火墙规则
3. **监控告警**: 配置Prometheus + Grafana监控
4. **备份策略**: 定期备份数据库，测试恢复流程
5. **性能优化**: 根据负载调整资源配置和索引策略

### 云原生部署
- **Kubernetes**: 使用Helm charts部署各组件
- **对象存储**: 使用S3兼容存储替代Minio
- **服务网格**: 使用Istio进行流量管理
- **CI/CD**: 自动化构建和部署流水线

## 许可证

待定

## 贡献

欢迎提交 Issue 和 Pull Request。