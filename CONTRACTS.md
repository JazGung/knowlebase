---
title: 跨领域契约
---

记录跨领域（一级模块）之间的约束与约定。

## 文档启用/停用与知识库数据联动

- **涉及领域**：业务资源域-文档管理、构建域、业务资源域-版本管理
- **主题**：`document_version_relation.stored` 与知识库数据 `enabled` 字段的职责分离

### stored 字段（仅由处理流水线管理）

- `stored=true`：文档数据已写入知识库，可供检索
- `stored=false`：文档数据不在知识库中（未处理、处理失败、或处理中已清理旧数据）
- **业务资源域不修改 stored**：启用/停用操作不改变 stored 值
- **stored 生命周期**：处理流水线入库阶段开始时设 false → 清理旧数据 → 写入新数据 → COMMIT 成功设 true；COMMIT 失败保持 false

### enabled 字段（由业务资源域管理）

- 启用时：设对应文档的所有知识库数据 `enabled=true`
- 停用时：设对应文档的所有知识库数据 `enabled=false`，不删除数据
- 重新处理时：新写入的数据 `enabled` 值继承当前文档的启用状态

### 知识库管理约束

- 检索/问答时，系统仅查询 `stored=true` 且 `enabled=true` 的数据
- 构建知识库版本时，系统仅处理 `stored=true` 的文档-版本关联记录

---

## 知识库数据 enabled 元数据字段

- **涉及领域**：业务资源域-文档管理、构建域、业务资源域-版本管理
- **主题**：所有知识库数据记录需携带 `enabled` 布尔字段，用于查询时过滤已停用文档的数据

### 数据范围

以下存储层的数据记录均需包含 `enabled` 字段：

| 存储层 | 数据实体 | enabled 含义 |
| :--- | :--- | :--- |
| PostgreSQL | `document_chunk` | 该分块是否参与检索 |
| Elasticsearch | 文档索引记录 | 该索引记录是否参与全文检索 |
| Milvus | 向量记录 | 该向量是否参与语义检索 |
| Neo4j | 关系边 | 该关系是否参与图谱查询 |

### 联动规则

- **文档启用**：设对应文档的所有 chunk/ES/Milvus/Neo4j 记录的 `enabled=true`
- **文档停用**：设对应文档的所有 chunk/ES/Milvus/Neo4j 记录的 `enabled=false`，不删除数据
- **检索/问答**：所有查询必须追加 `enabled=true` 过滤条件
- **文档重新处理**：新写入的数据 `enabled` 值继承当前文档的启用状态
