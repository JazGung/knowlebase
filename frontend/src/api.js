/**
 * 后端 API 调用封装
 * 业务资源域: /resource/*   构建域: /build/*
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function request(url, options = {}) {
  const res = await fetch(BASE_URL + url, {
    ...options,
    headers: { ...options.headers },
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const error = new Error(data.detail?.message || data.message || `HTTP ${res.status}`)
    error.status = res.status
    error.detail = data.detail
    throw error
  }

  const data = await res.json()

  if (data.code !== "000000") {
    const error = new Error(data.description || `业务错误 code=${data.code}`)
    error.code = data.code
    error.content = data.content
    throw error
  }

  return data
}

// ==================== 业务资源域 - 文档管理 ====================

/** POST /resource/document/check - 批量重复检查 */
export async function checkDuplicates(hashes) {
  const res = await request('/resource/document/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hashes }),
  })
  return res.content || { duplicates: [] }
}

/** POST /resource/document/upload - 单文件上传 */
export async function uploadFile(file, hash, metadata = {}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('hash', hash)
  if (metadata.title) formData.append('title', metadata.title)

  const res = await request('/resource/document/upload', {
    method: 'POST',
    body: formData,
  })
  return res.content
}

/** GET /resource/document/list - 文档列表 */
export async function getDocumentList(params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  }
  const res = await request(`/resource/document/list?${query.toString()}`)
  return res.content || { data: [], total: 0, page: 1, page_size: 20, total_pages: 0 }
}

/** GET /resource/document/detail - 文档详情 */
export async function getDocumentDetail(documentId) {
  const res = await request(`/resource/document/detail?document_id=${encodeURIComponent(documentId)}`)
  return res.content
}

/** PUT /resource/document/enable - 批量启用文档 */
export async function enableDocuments(documentIds) {
  return request('/resource/document/enable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds }),
  })
}

/** PUT /resource/document/disable - 批量停用文档 */
export async function disableDocuments(documentIds) {
  return request('/resource/document/disable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds }),
  })
}

/** POST /resource/document/process - 批量触发文档处理 */
export async function processDocuments(documentIds) {
  return request('/resource/document/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds }),
  })
}

// ==================== 业务资源域 - 版本管理 ====================

/** GET /resource/version/list - 版本列表 */
export async function getVersionList(params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  }
  const res = await request(`/resource/version/list?${query.toString()}`)
  return res.content || { data: [], total: 0, page: 1, page_size: 20 }
}

/** POST /resource/version/create - 创建版本 */
export async function createVersion(data = {}) {
  return request('/resource/version/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

/** POST /resource/version/build - 版本构建 */
export async function buildVersion(versionName) {
  return request('/resource/version/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version_name: versionName }),
  })
}

/** PUT /resource/version/enable - 启用版本 */
export async function enableVersion(versionName) {
  return request('/resource/version/enable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version_name: versionName }),
  })
}

// ==================== 业务资源域 - 关联查询 ====================

/** GET /resource/relation/list - 文档-版本关联查询 */
export async function getRelationList(params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  }
  const res = await request(`/resource/relation/list?${query.toString()}`)
  return res.content || { data: [], total: 0, page: 1, page_size: 20, total_pages: 0 }
}

// ==================== 构建域 ====================

/** GET /build/history/list - 处理记录查询 */
export async function getProcessingHistory(relationId, params = {}) {
  const query = new URLSearchParams({ relation_id: relationId })
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  }
  const res = await request(`/build/history/list?${query.toString()}`)
  return res.content || { data: [], total: 0, page: 1, page_size: 20, total_pages: 0 }
}

/** GET /build/stage/{processing_id}/{stage_name} - 阶段结果详情 */
export async function getStageResult(processingId, stageName) {
  const res = await request(`/build/stage/${encodeURIComponent(processingId)}/${encodeURIComponent(stageName)}`)
  return res.content
}

/** GET /build/detail - 处理详情视图 (relation_ids 或 processing_id) */
export async function getProcessingDetail({ relationIds, processingId } = {}) {
  const query = new URLSearchParams()
  if (relationIds) query.append('relation_ids', relationIds)
  if (processingId) query.append('processing_id', processingId)
  const res = await request(`/build/detail?${query.toString()}`)
  return res.content
}

/** GET /build/stream/{processing_id} - 处理进度 SSE 流 */
export function createProcessingStream(processingId) {
  return new EventSource(`${BASE_URL}/build/stream/${encodeURIComponent(processingId)}`)
}
