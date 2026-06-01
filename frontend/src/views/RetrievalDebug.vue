<template>
  <div style="display: flex; flex-direction: column; height: calc(100vh - 140px);">
    <!-- 顶部输入栏 -->
    <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-shrink: 0;">
      <el-input
        v-model="query"
        placeholder="输入检索问题或关键词..."
        clearable
        style="flex: 1;"
        @keyup.enter="handleSearch"
      />
      <el-select
        v-model="versionId"
        placeholder="选择知识库版本"
        style="width: 240px;"
      >
        <el-option
          v-for="v in versions"
          :key="v.id"
          :label="`${v.version_name}${v.is_built ? '' : ' (构建失败)'}`"
          :value="v.id"
          :disabled="!v.is_built"
        />
      </el-select>
      <span style="white-space: nowrap; font-size: 13px; color: #606266;">返回条数</span>
      <el-input-number
        v-model="topN"
        :min="1"
        :max="50"
        style="width: 120px;"
        placeholder="20"
      />
      <el-button type="primary" @click="handleSearch" :loading="searching">
        <el-icon><Search /></el-icon>
        查询
      </el-button>
    </div>

    <!-- 多 Tab 结果区 -->
    <el-tabs v-model="activeTab" style="flex: 1; display: flex; flex-direction: column;">
      <el-tab-pane label="ES 检索结果" name="es">
        <result-table :data="results.es_results" empty-text="暂无 ES 检索结果" />
      </el-tab-pane>
      <el-tab-pane label="Milvus 检索结果" name="milvus">
        <result-table :data="results.milvus_results" empty-text="暂无 Milvus 检索结果" />
      </el-tab-pane>
      <el-tab-pane label="Neo4j 检索结果" name="neo4j">
        <result-table :data="results.neo4j_results" empty-text="暂无 Neo4j 检索结果" />
      </el-tab-pane>
      <el-tab-pane label="合并后结果" name="merged">
        <result-table :data="results.merged_results" empty-text="暂无合并后结果" />
      </el-tab-pane>
      <el-tab-pane label="重排序后结果" name="reranked">
        <result-table :data="results.reranked_results" empty-text="暂无重排序后结果" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ResultTable from '../components/RetrievalDebugTable.vue'
import { debugSearch, getRetrievalVersions } from '../api.js'

const query = ref('')
const versionId = ref(null)
const versions = ref([])
const topN = ref(null)
const searching = ref(false)
const activeTab = ref('reranked')

const results = reactive({
  es_results: [],
  milvus_results: [],
  neo4j_results: [],
  merged_results: [],
  reranked_results: [],
})

onMounted(async () => {
  try {
    const data = await getRetrievalVersions()
    versions.value = data.versions || []
    if (versions.value.length > 0) {
      const built = versions.value.filter(v => v.is_built)
      if (built.length > 0) {
        const succeeded = built.find(v => v.status === 'succeeded')
        const enabled = built.find(v => v.status === 'enabled')
        versionId.value = succeeded ? succeeded.id : (enabled ? enabled.id : built[0].id)
      }
    }
  } catch (err) {
    ElMessage.error(`获取版本列表失败: ${err.message}`)
  }
})

async function handleSearch() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }
  if (!versionId.value) {
    ElMessage.warning('请选择知识库版本')
    return
  }

  searching.value = true
  try {
    const data = await debugSearch({ query: query.value.trim(), versionId: versionId.value, topN: topN.value })
    results.es_results = data.es_results || []
    results.milvus_results = data.milvus_results || []
    results.neo4j_results = data.neo4j_results || []
    results.merged_results = data.merged_results || []
    results.reranked_results = data.reranked_results || []
    ElMessage.success(`检索完成，共 ${results.reranked_results.length} 条结果`)
  } catch (err) {
    ElMessage.error(`检索失败: ${err.message}`)
  } finally {
    searching.value = false
  }
}


</script>
