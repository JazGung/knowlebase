<template>
  <div>
    <!-- 工具栏 -->
    <div style="margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        创建重建版本
      </el-button>
      <el-button
        type="success"
        :disabled="selectedRows.length !== 1 || !canEnableSelected"
        @click="handleEnable"
      >
        <el-icon><Check /></el-icon>
        启用版本
      </el-button>
      <el-button
        type="warning"
        :disabled="selectedRows.length !== 1 || !canDisableSelected"
        @click="handleDisable"
      >
        <el-icon><Close /></el-icon>
        停用版本
      </el-button>
      <el-button
        type="danger"
        :disabled="selectedRows.length !== 1 || !canDeleteSelected"
        @click="handleDelete"
      >
        <el-icon><Delete /></el-icon>
        删除版本
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <div style="margin-bottom: 16px; display: flex; justify-content: flex-end;">
      <el-select v-model="statusFilter" placeholder="状态过滤" clearable style="width: 160px;" @change="loadVersions">
        <el-option label="全部" value="" />
        <el-option label="重建中" value="building" />
        <el-option label="已完成" value="succeeded" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已停用" value="disabled" />
        <el-option label="已失败" value="failed" />
      </el-select>
    </div>

    <!-- 版本表格 -->
    <el-table
      v-loading="tableLoading"
      :data="versions"
      border
      stripe
      style="width: 100%;"
      @selection-change="handleSelectionChange"
      @row-dblclick="handleRowDblClick"
    >
      <el-table-column type="selection" width="40" />
      <el-table-column prop="version_id" label="版本ID" min-width="200" show-overflow-tooltip sortable="custom" />
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'building'" type="warning" size="small">重建中</el-tag>
          <el-tag v-else-if="row.status === 'succeeded'" type="success" size="small">已完成</el-tag>
          <el-tag v-else-if="row.status === 'enabled'" type="primary" size="small">已启用</el-tag>
          <el-tag v-else-if="row.status === 'disabled'" type="info" size="small">已停用</el-tag>
          <el-tag v-else-if="row.status === 'failed'" type="danger" size="small">已失败</el-tag>
          <span v-else style="color: #909399;">{{ row.status }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="document_count" label="文档数" width="80" align="center" />
      <el-table-column prop="chunk_count" label="分块数" width="100" align="center" />
      <el-table-column prop="created_by" label="操作人" width="100" align="center">
        <template #default="{ row }">
          {{ row.created_by || '系统' }}
        </template>
      </el-table-column>
      <el-table-column prop="started_at" label="开始时间" width="170" align="center">
        <template #default="{ row }">
          {{ formatTime(row.started_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="completed_at" label="完成时间" width="170" align="center">
        <template #default="{ row }">
          {{ row.completed_at ? formatTime(row.completed_at) : '-' }}
        </template>
      </el-table-column>
    </el-table>

    <!-- 底部操作栏 -->
    <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
      <el-button size="small" @click="handleViewDetail(selectedRows[0]?.version_id)" :disabled="selectedRows.length !== 1">
        <el-icon><View /></el-icon>
        查看详情
      </el-button>
      <span v-if="selectedRows.length > 0" style="margin-left: auto; color: #909399; font-size: 12px;">
        已选中 {{ selectedRows.length }} 项
      </span>
    </div>

    <!-- 分页 -->
    <div style="margin-top: 16px; display: flex; justify-content: flex-end;">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadVersions"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 版本详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      title="版本详情"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-descriptions v-if="detailData" :column="2" border>
        <el-descriptions-item label="版本ID" :span="2">{{ detailData.version?.version_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            :type="detailData.version?.status === 'enabled' ? 'primary' : detailData.version?.status === 'succeeded' ? 'success' : detailData.version?.status === 'failed' ? 'danger' : detailData.version?.status === 'building' ? 'warning' : 'info'"
            size="small"
          >
            {{ formatStatus(detailData.version?.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="操作人">{{ detailData.version?.created_by || '系统' }}</el-descriptions-item>
        <el-descriptions-item label="文档数">{{ detailData.version?.document_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="分块数">{{ detailData.version?.chunk_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="开始时间" :span="2">{{ formatTime(detailData.version?.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间" :span="2">
          {{ detailData.version?.completed_at ? formatTime(detailData.version?.completed_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detailData.version?.error_message" label="错误信息" :span="2">
          <span style="color: #f56c6c;">{{ detailData.version.error_message }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatTime(detailData.version?.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间" :span="2">{{ formatTime(detailData.version?.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Check, Close, Delete, View } from '@element-plus/icons-vue'
import {
  getVersionList,
  getVersionDetail,
  createVersion,
  enableVersion,
  disableVersion,
} from '../api.js'

// 版本列表
const versions = ref([])
const tableLoading = ref(false)
const selectedRows = ref([])
const statusFilter = ref('')

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// 详情对话框
const detailVisible = ref(false)
const detailData = ref(null)

onMounted(() => {
  loadVersions()
})

// 加载版本列表
async function loadVersions() {
  tableLoading.value = true
  try {
    const result = await getVersionList({
      page: pagination.page,
      page_size: pagination.pageSize,
      status: statusFilter.value || undefined,
    })
    versions.value = result.versions || []
    pagination.total = result.total || 0
  } catch (err) {
    ElMessage.error(`加载版本列表失败: ${err.message}`)
  } finally {
    tableLoading.value = false
  }
}

function handleSizeChange() {
  pagination.page = 1
  loadVersions()
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

// 按钮可用性计算
const canEnableSelected = computed(() => {
  if (selectedRows.value.length !== 1) return false
  const row = selectedRows.value[0]
  return row.status === 'succeeded' || row.status === 'disabled'
})

const canDisableSelected = computed(() => {
  if (selectedRows.value.length !== 1) return false
  const row = selectedRows.value[0]
  return row.status !== 'enabled' && (row.status === 'succeeded' || row.status === 'disabled')
})

const canDeleteSelected = computed(() => {
  if (selectedRows.value.length !== 1) return false
  return selectedRows.value[0].status !== 'enabled'
})

// 创建重建版本
async function handleCreate() {
  try {
    await ElMessageBox.confirm('确定要创建新的知识库重建版本吗？', '确认操作', { type: 'info' })
    const result = await createVersion({})
    ElMessage.success(`版本创建成功: ${result.data?.version_id}`)
    loadVersions()
  } catch (err) {
    if (err?.name === 'Cancel') return
    ElMessage.error(`版本创建失败: ${err.message}`)
  }
}

// 启用版本
async function handleEnable() {
  const row = selectedRows.value[0]
  if (!row) return

  try {
    await ElMessageBox.confirm(
      `确定要启用版本「${row.version_id}」吗？当前启用的版本将自动停用。`,
      '确认操作',
      { type: 'success' }
    )
    await enableVersion(row.version_id)
    ElMessage.success('版本已启用')
    loadVersions()
  } catch (err) {
    if (err?.name === 'Cancel') return
    ElMessage.error(`启用失败: ${err.message}`)
  }
}

// 停用版本
async function handleDisable() {
  const row = selectedRows.value[0]
  if (!row) return

  try {
    await ElMessageBox.confirm(`确定要停用版本「${row.version_id}」吗？`, '确认操作', { type: 'warning' })
    await disableVersion(row.version_id)
    ElMessage.success('版本已停用')
    loadVersions()
  } catch (err) {
    if (err?.name === 'Cancel') return
    ElMessage.error(`停用失败: ${err.message}`)
  }
}

// 删除版本
async function handleDelete() {
  const row = selectedRows.value[0]
  if (!row) return

  try {
    await ElMessageBox.confirm(
      `确定要删除版本「${row.version_id}」吗？此操作不可恢复。`,
      '确认删除',
      { type: 'error' }
    )
    // TODO: 后端 delete 接口待实现
    ElMessage.warning('删除功能待后端接口实现')
  } catch (err) {
    if (err?.name === 'Cancel') return
    ElMessage.error(`删除失败: ${err.message}`)
  }
}

// 查看详情
async function handleViewDetail(versionId) {
  if (!versionId) return
  try {
    detailData.value = await getVersionDetail(versionId)
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(`加载版本详情失败: ${err.message}`)
  }
}

function handleRowDblClick(row) {
  handleViewDetail(row.version_id)
}

// 工具函数
function formatStatus(status) {
  const map = {
    building: '重建中',
    succeeded: '已完成',
    enabled: '已启用',
    disabled: '已停用',
    failed: '已失败',
  }
  return map[status] || status
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  try {
    const d = new Date(timeStr)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return timeStr
  }
}
</script>
