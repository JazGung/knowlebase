# LLM 智能分块

## 决策背景

### 为什么结合 LLM 做分块

传统分块算法（按字符数截断、按句子滑动窗口、基于 Embedding 相似度）存在以下局限：

1. **语义边界不精确**：按固定字数或句子数切分容易破坏语义完整性
2. **指代消解需要额外步骤**：传统方法分块后需独立做指代消解，两次处理可能引入不一致
3. **HyDE 生成也需要独立调用**：向量库写入前需单独调用 LLM 生成假设问题
4. **图片处理孤立**：图片与文本分离，无法关联上下文

将分块、指代消解、HyDE 问题生成、图谱关系提取合并为一次 LLM 调用（每窗口一次），可以：
- 减少 API 调用次数
- 模型在理解上下文语境后同时输出，质量更高
- 指代消解结果可以直接基于分块的语义边界，更精准

### 选择 LangChain 而非直接调用 API

- `init_chat_model` 统一接口，后续切换 LLM 只需改配置
- `JsonOutputParser` 保证输出结构化，避免正则解析 JSON 的脆弱性

## 架构

```
解析 → 清洗 → [图片转描述] → [窗口滑动 + LLM 分块] → [还原图片占位符] → 存储/向量化
```

## 配置项

| 配置 | 规则 | 默认值 |
|------|------|--------|
| `CHUNK_MAX_CHARS` | 整数，非整数向下取整 | 800 |
| `CHUNK_MIN_CHARS` | (0,1) → max_chars 比例；>1 → 绝对值，向下取整 | 0.5（400 字） |
| `CHUNK_OVERLAP` | (0,1) → max_chars 倍数；>1 → 绝对值，向下取整 | 0.1（80 字） |
| `CHUNK_WINDOW` | (1,5) → max_chars 倍数；>5 → 绝对值，向下取整 | 1.5（1200 字） |

## 分块流程

### 1. 图片预处理（清洗后、分块前）

- 遍历 ParseResult 中的 `ParsedImage`
- 使用视觉模型生成描述文字
- 用 `[IMAGE_START:caption] 描述文字 [IMAGE_END]` 替换原图片位置
- 保留原始 ParsedImage 信息用于后续还原

### 2. 最小分块单位：三级标题

- H1/H2/H3 为独立分块单位，一个分块内不能包含多个同级标题
- H4 及以下不作为单独分块单位，多个可合并到同一分块
- 如果 section 文本 ≤ max_chars，不再分块，只做指代替换、假设提问、关系提取

### 3. 窗口滑动

**[窗口1]（首个窗口）**
- Context: 无
- Current Window: 前 window_size 字符，前溯到句子/图片/表格行边界

**[窗口2+]**
- Context:
  1. 重叠文本：上一 chunk `processed_text` 末尾 ≥ overlap 长度的完整句子/图片/表格行
  2. 上一分块提取的实体列表
- Current Window: 从上一窗口结束处起，window_size 字符，前溯到边界

**输出处理：**
- 丢弃最后一个 chunk（边界截断风险），最后一个窗口除外
- 每个 chunk 的 `processed_text` 在开头添加重叠部分，`original_text` 不加

### 4. LLM 分块调用（每窗口一次，Pipeline 4 步）

Prompt 指示模型按顺序执行：

1. **语义分块**：如果文本 > max_chars，按语义分成多个 sub-chunk（每块 ≥ min_chars 且 ≤ max_chars）
2. **指代替换**：结合 Context 做指代消解
3. **假设提问**：每块生成 2-5 个 HyDE 问题
4. **关系提取**：提取 `(source, relationship, target)` 三元组

### 5. 分块后还原

- `[IMAGE_START:caption]...[IMAGE_END]` → `[IMAGE: path=xxx|caption=xxx]`
- **original_text**：还原图片为 `[IMAGE: path=xxx|caption=xxx]` 占位符，前端可通过 path 获取 MinIO 预签名 URL 预览图片
- **processed_text**：在开头添加重叠部分，保留完整图片描述文字 + 指代消解，用于向量入库和检索

## 输出结构

### ChunkResult

| 字段 | 类型 | 说明 |
|------|------|------|
| original_text | str | 还原图片为 `[IMAGE: path=xxx\|caption=xxx]`，前端可预览图片 |
| processed_text | str | 含重叠前缀 + 完整图片描述 + 指代消解，向量入库 |
| hypothetical_questions | List[str] | 2-5 个假设问题（HyDE） |
| relations | List[Triplet] | 图关系三元组：(source, relationship, target) |
| page_range | Optional[str] | 页码范围，如 "1-3" |
| section_title | Optional[str] | 所属章节标题 |

### LLM 返回 → ChunkResult 映射

```json
{
  "original_text": "原始分块文本（不修改任何字符）",
  "processed_text": "指代消解后的分块文本",
  "questions": ["问题1", "问题2"],
  "triplets": [{"source": "A", "relationship": "关系", "target": "B"}]
}
```

映射为：
- `original_text` → 还原图片占位符为 `[IMAGE: path|caption]`
- `processed_text` → 添加重叠前缀
- `questions` → `hypothetical_questions`
- `triplets` → `relations`

### 图谱导入

- 节点去重由 Neo4j 层用 `MERGE` 处理，LLM 输出不关心去重
- 导入格式：nodes + relationships 分开，避免重复创建节点

### 图片前端展示

- 占位符格式：`[IMAGE: path=images/abc123.png|caption=公司Logo]`
- 后端接口：`/build/image/preview?path=xxx`，返回 MinIO 预签名 URL
- 前端渲染为 `<img>` 标签

## 文件

| 文件 | 职责 |
|------|------|
| `backend/src/knowlebase/parsers/image_storage.py` | 图片 MD5 去重 + MinIO 存储 |
| `backend/src/knowlebase/chunker/__init__.py` | 统一入口，暴露 `chunk_document` |
| `backend/src/knowlebase/chunker/models.py` | `ChunkResult` + `Triplet` 数据模型 |
| `backend/src/knowlebase/chunker/langchain_chunker.py` | 窗口滑动 + LLM Chain + 分块逻辑 |
| `backend/src/knowlebase/chunker/image_describer.py` | 图片描述生成 |
| `backend/src/knowlebase/core/config.py` | LLM 配置解析 + 回退逻辑 |
| `backend/src/knowlebase/admin/processing/service.py` | 流水线集成 |
| `backend/tests/test_chunking.py` | 单元测试（Mock Chain） |

## 测试

- TDD，使用 `AsyncMock` 模拟 Chain
- 覆盖：分块边界、指代消解、HyDE 生成、关系提取、窗口滑动、重叠处理、空章节跳过、图片不切断
