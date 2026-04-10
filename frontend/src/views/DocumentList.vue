<template>
  <div>
    <!-- 上传对话框 -->
    <UploadDialog ref="uploadDialogRef" @confirm="handleUploadConfirm" />

    <!-- 上传结果视图 -->
    <UploadResults
      v-if="viewMode === 'uploading'"
      :files="uploadFiles"
      @back="handleUploadBack"
      @view-document="handleViewDocument"
    />

    <!-- 文档列表视图 -->
    <template v-else>
      <!-- 工具栏 -->
      <div style="margin-bottom: 16px; display: flex; gap: 8px; align-items: center;">
        <el-button type="primary" @click="handleUpload">
          <el-icon><upload-filled /></el-icon>
          上传文档
        </el-button>
        <el-button
          :disabled="selectedRows.length === 0"
          @click="handleBatchEnable(true)"
        >
          <el-icon><check /></el-icon>
          启用
        </el-button>
        <el-button
          :disabled="selectedRows.length === 0"
          @click="handleBatchEnable(false)"
        >
          <el-icon><close /></el-icon>
          停用
        </el-button>
        <el-button
          :disabled="selectedRows.length !== 1"
          @click="handleReprocess"
        >
          <el-icon><refresh-right /></el-icon>
          重新处理
        </el-button>

        <!-- 搜索 -->
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文件名、标题..."
          clearable
          style="width: 240px; margin-left: auto;"
          @clear="loadDocuments"
          @keyup.enter="loadDocuments"
        >
          <template #append>
            <el-button @click="loadDocuments">
              <el-icon><search /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>

      <!-- 文档表格 -->
      <el-table
        v-loading="tableLoading"
        :data="documents"
        border
        stripe
        style="width: 100%;"
        @selection-change="handleSelectionChange"
        @row-dblclick="handleRowDblClick"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column prop="original_filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.title || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="处理状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'success'" type="success" size="small">成功</el-tag>
            <el-tag v-else-if="row.status === 'processing'" type="warning" size="small">处理中</el-tag>
            <el-tag v-else-if="row.status === 'pending'" size="small">待处理</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger" size="small">失败</el-tag>
            <el-tag v-else-if="row.status === 'deleted'" type="info" size="small">已删除</el-tag>
            <span v-else style="color: #909399;">{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.enabled" type="success" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="100" align="right">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" align="center">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleViewDetail(row.id)">
              详情
            </el-button>
            <el-button
              v-if="row.enabled"
              type="warning"
              link
              size="small"
              @click="handleToggleEnable(row, false)"
            >
              停用
            </el-button>
            <el-button
              v-else
              type="success"
              link
              size="small"
              @click="handleToggleEnable(row, true)"
            >
              启用
            </el-button>
            <el-button type="info" link size="small" @click="handleReprocessSingle(row.id)">
              重新处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end;">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="loadDocuments"
          @size-change="handleSizeChange"
        />
      </div>
    </template>

    <!-- 文档详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      title="文档详情"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-descriptions v-if="detailData" :column="2" border>
        <el-descriptions-item label="文档ID">{{ detailData.document?.id }}</el-descriptions-item>
        <el-descriptions-item label="原始文件名">{{ detailData.document?.original_filename }}</el-descriptions-item>
        <el-descriptions-item label="标题">{{ detailData.document?.title || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分类">{{ detailData.document?.category || '-' }}</el-descriptions-item>
        <el-descriptions-item label="文件大小">{{ formatFileSize(detailData.document?.file_size) }}</el-descriptions-item>
        <el-descriptions-item label="文件哈希">{{ detailData.document?.file_hash }}</el-descriptions-item>
        <el-descriptions-item label="处理状态">
          <el-tag v-if="detailData.document?.status === 'success'" type="success">成功</el-tag>
          <el-tag v-else-if="detailData.document?.status === 'processing'" type="warning">处理中</el-tag>
          <el-tag v-else-if="detailData.document?.status === 'failed'" type="danger">失败</el-tag>
          <el-tag v-else>{{ detailData.document?.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="是否启用">
          <el-tag v-if="detailData.document?.enabled" type="success">是</el-tag>
          <el-tag v-else type="info">否</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="标签" :span="2">
          <el-tag
            v-for="tag in (detailData.document?.tags || [])"
            :key="tag"
            size="small"
            style="margin-right: 4px;"
          >
            {{ tag }}
          </el-tag>
          <span v-if="!detailData.document?.tags?.length" style="color: #909399;">-</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatTime(detailData.document?.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间" :span="2">{{ formatTime(detailData.document?.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <!-- 处理历史 -->
      <div v-if="detailData?.processing_history?.length" style="margin-top: 16px;">
        <h4>处理历史</h4>
        <el-timeline>
          <el-timeline-item
            v-for="proc in detailData.processing_history"
            :key="proc.processing_id"
            :timestamp="formatTime(proc.started_at)"
            :type="proc.status === 'success' ? 'success' : proc.status === 'failed' ? 'danger' : 'warning'"
          >
            <div>
              第 {{ proc.processing_number }} 次处理 -
              <el-tag :type="proc.status === 'success' ? 'success' : proc.status === 'failed' ? 'danger' : 'warning'" size="small">
                {{ proc.status }}
              </el-tag>
              <span style="margin-left: 8px; color: #909399;">进度: {{ proc.progress }}%</span>
            </div>
            <div v-if="proc.error_message" style="color: #f56c6c; margin-top: 4px;">
              错误: {{ proc.error_message }}
            </div>
            <div v-if="proc.result" style="margin-top: 4px; color: #606266; font-size: 12px;">
              分块数: {{ proc.result.chunks_count || 0 }} |
              向量数: {{ proc.result.vector_count || 0 }} |
              实体数: {{ proc.result.entities_count || 0 }}
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Check, Close, RefreshRight, Search } from '@element-plus/icons-vue'
import UploadResults from '../components/UploadResults.vue'
import UploadDialog from '../components/UploadDialog.vue'
import {
  getDocumentList,
  getDocumentDetail,
  enableDocument,
  disableDocument,
  reprocessDocument,
} from '../api.js'

// 视图模式
const viewMode = ref('list')
const uploadFiles = ref([])

// 文档列表
const documents = ref([])
const tableLoading = ref(false)
const selectedRows = ref([])
const searchKeyword = ref('')

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// 详情对话框
const detailVisible = ref(false)
const detailData = ref(null)

// 上传对话框（使用 ref 控制）
const uploadDialogRef = ref(null)

onMounted(() => {
  loadDocuments()
})

// 加载文档列表
async function loadDocuments() {
  tableLoading.value = true
  try {
    const result = await getDocumentList({
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchKeyword.value || undefined,
    })
    documents.value = result.documents || []
    pagination.total = result.pagination?.total || 0
  } catch (err) {
    ElMessage.error(`加载文档列表失败: ${err.message}`)
  } finally {
    tableLoading.value = false
  }
}

function handleSizeChange() {
  pagination.page = 1
  loadDocuments()
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

// 上传
function handleUpload() {
  uploadDialogRef.value?.open()
}

function handleUploadConfirm(files) {
  uploadFiles.value = files
  viewMode.value = 'uploading'
}

function handleUploadBack() {
  viewMode.value = 'list'
  uploadFiles.value = []
  loadDocuments()
}

// 启用/停用
async function handleToggleEnable(row, enable) {
  try {
    if (enable) {
      await enableDocument(row.id)
      ElMessage.success('文档已启用')
    } else {
      await disableDocument(row.id)
      ElMessage.success('文档已停用')
    }
    loadDocuments()
  } catch (err) {
    ElMessage.error(`操作失败: ${err.message}`)
  }
}

async function handleBatchEnable(enable) {
  try {
    await ElMessageBox.confirm(
      `确定要${enable ? '启用' : '停用'}选中的 ${selectedRows.value.length} 个文档吗？`,
      '确认操作',
      { type: 'warning' }
    )
    for (const row of selectedRows.value) {
      if (enable) {
        await enableDocument(row.id)
      } else {
        await disableDocument(row.id)
      }
    }
    ElMessage.success(`已${enable ? '启用' : '停用'} ${selectedRows.value.length} 个文档`)
    loadDocuments()
  } catch {
    // 取消
  }
}

// 重新处理
async function handleReprocessSingle(documentId) {
  try {
    await ElMessageBox.confirm('确定要重新处理该文档吗？', '确认操作', { type: 'warning' })
    const result = await reprocessDocument(documentId, false)
    ElMessage.success(`已发起重新处理，任务ID: ${result.data?.processing_id || '未知'}`)
    loadDocuments()
  } catch {
    // 取消
  }
}

async function handleReprocess() {
  if (selectedRows.value.length !== 1) return
  await handleReprocessSingle(selectedRows.value[0].id)
}

// 查看详情
async function handleViewDetail(documentId) {
  try {
    detailData.value = await getDocumentDetail(documentId)
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(`加载文档详情失败: ${err.message}`)
  }
}

function handleViewDocument(documentId) {
  handleViewDetail(documentId)
}

function handleRowDblClick(row) {
  handleViewDetail(row.id)
}

// 工具函数
function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
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

// 暴露方法供父组件调用
defineExpose({ handleUploadConfirm, uploadDialogRef })
</script>
