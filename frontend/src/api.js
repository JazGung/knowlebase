/**
 * 后端 API 调用封装
 * 所有请求通过 Vite 代理转发到后端
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

/**
 * 通用请求处理
 * 后端统一返回 HTTP 200，通过 body.code 判断业务成功/失败
 */
async function request(url, options = {}) {
  const res = await fetch(BASE_URL + url, {
    ...options,
    headers: {
      ...options.headers,
    },
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const error = new Error(data.detail?.message || data.message || `HTTP ${res.status}`)
    error.status = res.status
    error.detail = data.detail
    throw error
  }

  const data = await res.json()

  // 检查业务错误码（后端统一返回 HTTP 200，业务错误通过 code 区分）
  if (data.code !== 0) {
    const error = new Error(data.message || `业务错误 code=${data.code}`)
    error.code = data.code
    error.detail = data.detail
    throw error
  }

  return data
}

// ==================== 文档检查 ====================

/**
 * POST /build/document/check - 批量重复检查
 * @param {Array<{filename: string, hash: string}>} files
 */
export async function checkDuplicates(files) {
  const res = await request('/build/document/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files }),
  })
  return res.data || { duplicate_files: [] }
}

// ==================== 文件上传 ====================

/**
 * POST /build/document/upload - 单文件上传
 * @param {File} file - 文件对象
 * @param {string} hash - MD5 hex 字符串
 * @param {Object} metadata - 可选元数据 {title, description, category, tags}
 */
export async function uploadFile(file, hash, metadata = {}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('hash', hash)
  if (metadata.title) formData.append('title', metadata.title)
  if (metadata.description) formData.append('description', metadata.description)
  if (metadata.category) formData.append('category', metadata.category)
  if (metadata.tags) formData.append('tags', metadata.tags)

  const res = await request('/build/document/upload', {
    method: 'POST',
    body: formData,
  })
  return res.data
}

// ==================== 文档管理 ====================

/**
 * GET /build/document/list - 文档列表
 * @param {Object} params - 查询参数 {page, page_size, status, enabled, search, sort_by, order}
 */
export async function getDocumentList(params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  }
  const url = `/build/document/list?${query.toString()}`
  const res = await request(url)
  return res.data || { documents: [], pagination: { total: 0, page: 1, page_size: 20, total_pages: 0 } }
}

/**
 * GET /build/document/detail - 文档详情
 * @param {string} documentId
 */
export async function getDocumentDetail(documentId) {
  const res = await request(`/build/document/detail?document_id=${encodeURIComponent(documentId)}`)
  return res.data
}

/**
 * PUT /build/document/enable - 启用文档
 * @param {string} documentId
 */
export async function enableDocument(documentId) {
  return request('/build/document/enable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId }),
  })
}

/**
 * PUT /build/document/disable - 停用文档
 * @param {string} documentId
 */
export async function disableDocument(documentId) {
  return request('/build/document/disable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId }),
  })
}

/**
 * POST /build/document/reprocess - 重新处理文档
 * @param {string} documentId
 * @param {boolean} forceReprocess
 */
export async function reprocessDocument(documentId, forceReprocess = false) {
  return request('/build/document/reprocess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, force_reprocess: forceReprocess }),
  })
}

// ==================== 知识库版本管理 ====================

/**
 * GET /build/version/list - 版本列表
 * @param {Object} params - {page, page_size, status}
 */
export async function getVersionList(params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  }
  const url = `/build/version/list?${query.toString()}`
  const res = await request(url)
  return res.data || { versions: [], total: 0, page: 1, page_size: 20 }
}

/**
 * GET /build/version/detail - 版本详情
 * @param {string} versionId
 */
export async function getVersionDetail(versionId) {
  const res = await request(`/build/version/detail?version_id=${encodeURIComponent(versionId)}`)
  return res.data
}

/**
 * POST /build/version/create - 创建重建版本
 * @param {Object} data - {created_by?: string}
 */
export async function createVersion(data = {}) {
  return request('/build/version/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

/**
 * PUT /build/version/enable - 启用版本
 * @param {string} versionId
 */
export async function enableVersion(versionId) {
  return request('/build/version/enable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version_id: versionId }),
  })
}

/**
 * PUT /build/version/disable - 停用版本
 * @param {string} versionId
 */
export async function disableVersion(versionId) {
  return request('/build/version/disable', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version_id: versionId }),
  })
}
