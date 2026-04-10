<template>
  <el-dialog
    v-model="visible"
    title="上传文档"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-upload
      ref="uploadRef"
      v-model:file-list="fileList"
      drag
      multiple
      accept=".pdf,.docx,.doc"
      :auto-upload="false"
      :on-change="handleFileChange"
      :before-upload="beforeUpload"
      :limit="50"
    >
      <el-icon class="el-icon--upload" :size="48"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽文件到此处，或 <em>点击选择文件</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持 PDF、Word（.docx/.doc）格式，单文件最大 100MB，最多 50 个文件
        </div>
      </template>
    </el-upload>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="primary"
        :disabled="selectedFiles.length === 0"
        @click="handleConfirm"
      >
        确认上传 ({{ selectedFiles.length }})
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const MAX_FILE_SIZE = 100 * 1024 * 1024 // 100MB
const emit = defineEmits(['confirm', 'close'])

const visible = ref(false)
const fileList = ref([])
const selectedFiles = ref([])

function open() {
  visible.value = true
  fileList.value = []
  selectedFiles.value = []
}

function handleClose() {
  visible.value = false
  fileList.value = []
  selectedFiles.value = []
  emit('close')
}

function beforeUpload(rawFile) {
  if (rawFile.size > MAX_FILE_SIZE) {
    ElMessage.error(`文件 "${rawFile.name}" 超过 100MB 限制`)
    return false
  }
  const ext = rawFile.name.split('.').pop().toLowerCase()
  if (!['pdf', 'docx', 'doc'].includes(ext)) {
    ElMessage.error(`文件 "${rawFile.name}" 格式不支持`)
    return false
  }
  return true
}

function handleFileChange(uploadFile, uploadFiles) {
  // 从 uploadFiles 中提取原生 File 对象
  selectedFiles.value = uploadFiles
    .filter((f) => f.status !== 'fail')
    .map((f) => f.raw)
    .filter(Boolean)
}

function handleConfirm() {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  visible.value = false
  emit('confirm', [...selectedFiles.value])
}

defineExpose({ open })
</script>

<style scoped>
.el-upload__tip {
  color: #909399;
  font-size: 12px;
  margin-top: 8px;
}
</style>
