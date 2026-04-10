<template>
  <div>
    <!-- 顶部操作栏 -->
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
      <div>
        <el-button @click="handleBack">
          <el-icon><arrow-left /></el-icon>
          返回文档列表
        </el-button>
      </div>
      <div v-if="isComplete" style="display: flex; gap: 8px; align-items: center;">
        <el-tag type="success" size="large">成功: {{ successCount }}</el-tag>
        <el-tag type="warning" size="large">重复: {{ duplicateCount }}</el-tag>
        <el-tag type="danger" size="large">失败: {{ errorCount }}</el-tag>
      </div>
    </div>

    <!-- 上传进度提示 -->
    <el-alert
      v-if="!isComplete"
      :title="currentStatusText"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px;"
    >
      <template #default>
        <el-progress
          :percentage="overallProgress"
          :stroke-width="8"
          style="margin-top: 8px;"
        />
      </template>
    </el-alert>

    <!-- 结果表格 -->
    <el-table :data="uploadItems" border stripe style="width: 100%;">
      <el-table-column prop="originalFilename" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column prop="hash" label="Hash" width="320" align="center">
        <template #default="{ row }">
          <span v-if="row.hash" style="font-family: monospace; font-size: 12px;">{{ row.hash }}</span>
          <span v-else style="color: #909399;">计算中...</span>
        </template>
      </el-table-column>
      <el-table-column label="上传结果" min-width="250">
        <template #default="{ row }">
          <!-- 本地重复 -->
          <div v-if="row.status === 'local_duplicate'" style="color: #909399;">
            <el-icon><info-filled /></el-icon>
            {{ row.resultText }}
          </div>

          <!-- 服务器重复 -->
          <div v-else-if="row.status === 'server_duplicate'" style="color: #e6a23c;">
            <el-icon><warning-filled /></el-icon>
            {{ row.resultText }}
            <el-link
              v-if="row.existingDocumentId"
              type="primary"
              size="small"
              style="margin-left: 8px;"
              @click="handleViewExisting(row.existingDocumentId)"
            >
              查看原文
            </el-link>
          </div>

          <!-- 上传中 -->
          <div v-else-if="row.status === 'uploading'">
            <el-progress :percentage="row.progress || 0" :stroke-width="6" />
          </div>

          <!-- 上传成功 -->
          <div v-else-if="row.status === 'success'" style="color: #67c23a;">
            <el-icon><circle-check-filled /></el-icon>
            上传成功
            <el-link
              v-if="row.result?.processing_id"
              type="primary"
              size="small"
              style="margin-left: 8px;"
            >
              查看进度
            </el-link>
          </div>

          <!-- 上传时检测到重复 -->
          <div v-else-if="row.status === 'duplicate'" style="color: #e6a23c;">
            <el-icon><warning-filled /></el-icon>
            文件已存在
          </div>

          <!-- 上传失败 -->
          <div v-else-if="row.status === 'error'" style="color: #f56c6c;">
            <el-icon><circle-close-filled /></el-icon>
            {{ row.error }}
            <el-button
              type="primary"
              link
              size="small"
              style="margin-left: 8px;"
              @click="handleRetry(row)"
            >
              重试
            </el-button>
          </div>

          <!-- 等待中 -->
          <div v-else style="color: #909399;">
            等待中...
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 完成后操作 -->
    <div v-if="isComplete" style="margin-top: 16px; text-align: center;">
      <el-button type="primary" @click="handleBack">返回文档列表</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, InfoFilled, WarningFilled, CircleCheckFilled, CircleCloseFilled
} from '@element-plus/icons-vue'
import { computeMD5 } from '../utils/md5.js'
import { UploadManager } from '../utils/uploadManager.js'
import { checkDuplicates } from '../api.js'

const props = defineProps({
  files: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['back', 'view-document'])

const uploadItems = ref([])
const isComplete = ref(false)
const uploadManager = new UploadManager(3)

// 统计
const successCount = computed(() => uploadItems.value.filter((i) => i.status === 'success' || i.status === 'duplicate').length)
const duplicateCount = computed(() => uploadItems.value.filter((i) => i.status === 'local_duplicate' || i.status === 'server_duplicate').length)
const errorCount = computed(() => uploadItems.value.filter((i) => i.status === 'error').length)

// 总体进度
const overallProgress = computed(() => {
  const total = uploadItems.value.length
  if (total === 0) return 0
  const done = uploadItems.value.filter((i) =>
    ['success', 'duplicate', 'local_duplicate', 'server_duplicate', 'error'].includes(i.status)
  ).length
  return Math.round((done / total) * 100)
})

// 当前状态文本
const currentStatusText = computed(() => {
  const total = uploadItems.value.length
  const done = uploadItems.value.filter((i) =>
    ['success', 'duplicate', 'local_duplicate', 'server_duplicate', 'error'].includes(i.status)
  ).length
  const uploading = uploadItems.value.filter((i) => i.status === 'uploading').length
  const computing = uploadItems.value.filter((i) => !i.hash && i.status === 'pending').length

  if (computing > 0) return `正在计算文件哈希: ${total - computing}/${total}`
  if (uploading > 0) return `正在上传: ${done}/${total} (并发 ${uploading})`
  if (done < total) return `处理中: ${done}/${total}`
  return '处理完成'
})

// 重试
function handleRetry(item) {
  uploadManager.retry(item, onStatusChange)
}

function onStatusChange(_item) {
  // 触发响应式更新
  uploadItems.value = [...uploadItems.value]
}

function handleBack() {
  emit('back')
}

function handleViewExisting(documentId) {
  emit('view-document', documentId)
}

// 主流程
onMounted(async () => {
  // 1. 初始化上传项
  // 按文件名排序
  const sorted = [...props.files].sort((a, b) => {
    const nameA = a.webkitRelativePath || a.name
    const nameB = b.webkitRelativePath || b.name
    return nameA.localeCompare(nameB)
  })

  uploadItems.value = sorted.map((file) => ({
    file,
    originalFilename: file.name,
    hash: null,
    status: 'pending',
    result: null,
    resultText: '',
    error: null,
    errorDetail: null,
    progress: 0,
    existingDocumentId: null,
    existingFilename: null,
    metadata: {},
  }))

  // 2. 计算 MD5
  for (let i = 0; i < uploadItems.value.length; i++) {
    const item = uploadItems.value[i]
    try {
      item.hash = await computeMD5(item.file, (percent) => {
        // MD5 计算进度可以通过 hash 列显示
      })
    } catch (err) {
      item.status = 'error'
      item.error = `MD5 计算失败: ${err.message}`
      uploadItems.value = [...uploadItems.value]
    }
    uploadItems.value = [...uploadItems.value]
  }

  // 3. 本地去重
  const hashMap = new Map()
  for (const item of uploadItems.value) {
    if (item.status === 'error') continue
    if (hashMap.has(item.hash)) {
      item.status = 'local_duplicate'
      item.resultText = `与 ${hashMap.get(item.hash)} 文件重复`
    } else {
      hashMap.set(item.hash, item.originalFilename)
    }
  }
  uploadItems.value = [...uploadItems.value]

  // 4. 服务器重复检查
  const toCheck = uploadItems.value
    .filter((i) => i.status === 'pending')
    .map((i) => ({ filename: i.originalFilename, hash: i.hash }))

  if (toCheck.length > 0) {
    try {
      const checkResult = await checkDuplicates(toCheck)
      const dupMap = new Map()
      for (const dup of checkResult.duplicate_files || []) {
        dupMap.set(dup.hash, dup)
      }

      for (const item of uploadItems.value) {
        if (item.status === 'pending' && dupMap.has(item.hash)) {
          const dup = dupMap.get(item.hash)
          item.status = 'server_duplicate'
          item.resultText = `与已上传文件 "${dup.existing_filename}" 重复`
          item.existingDocumentId = dup.existing_document_id
          item.existingFilename = dup.existing_filename
        }
      }
      uploadItems.value = [...uploadItems.value]
    } catch (err) {
      ElMessage.warning(`服务器重复检查失败: ${err.message}，继续上传`)
    }
  }

  // 5. 并发上传
  await uploadManager.uploadAll(uploadItems.value, onStatusChange)

  isComplete.value = true

  // 统计
  const success = uploadItems.value.filter((i) => i.status === 'success' || i.status === 'duplicate').length
  const failed = uploadItems.value.filter((i) => i.status === 'error').length
  if (failed === 0) {
    ElMessage.success(`上传完成，成功 ${success} 个文件`)
  } else {
    ElMessage.warning(`上传完成: 成功 ${success} 个，失败 ${failed} 个`)
  }
})
</script>
