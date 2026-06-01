<template>
  <div style="flex: 1; overflow: auto;">
    <el-table
      v-if="data.length > 0"
      :data="data"
      border
      stripe
      style="width: 100%;"
      max-height="100%"
    >
      <el-table-column type="index" label="#" width="50" />
      <el-table-column prop="chunk_text" label="分块文本" min-width="300" show-overflow-tooltip />
      <el-table-column prop="document_name" label="所属文档" width="180" show-overflow-tooltip />
      <el-table-column prop="page_number" label="所在页码" width="90" align="center" />
      <el-table-column prop="chapter_title" label="所在章节" width="150" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.chapter_title || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="score" label="相关性分数" width="120" align="center">
        <template #default="{ row }">
          {{ row.score != null ? row.score.toFixed(4) : '-' }}
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else :description="emptyText" style="margin-top: 60px;" />
  </div>
</template>

<script setup>
defineProps({
  data: { type: Array, default: () => [] },
  emptyText: { type: String, default: '暂无数据' },
})
</script>
