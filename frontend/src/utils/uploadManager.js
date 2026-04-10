/**
 * 并发上传队列管理
 * 控制同时上传的文件数量，避免过多并发请求
 */
import { uploadFile } from '../api.js'

export class UploadManager {
  /**
   * @param {number} concurrency - 最大并发数，默认 3
   */
  constructor(concurrency = 3) {
    this.concurrency = concurrency
    this._abort = false
  }

  /**
   * 执行批量上传
   * @param {Array} items - 上传项数组，每个包含 { file, hash, status, result }
   * @param {Function} onStatusChange - 状态变化回调 (item) => void
   */
  async uploadAll(items, onStatusChange) {
    this._abort = false

    const pending = items.filter((item) => item.status === 'pending')
    const queue = [...pending]
    const active = new Set()

    return new Promise((resolve) => {
      const runNext = async () => {
        if (this._abort || queue.length === 0) {
          if (active.size === 0) resolve()
          return
        }

        const item = queue.shift()
        active.add(item)
        item.status = 'uploading'
        item.progress = 0
        if (onStatusChange) onStatusChange(item)

        try {
          const result = await uploadFile(item.file, item.hash, item.metadata || {})
          item.status = result.status === 'duplicate' ? 'duplicate' : 'success'
          item.result = result
        } catch (err) {
          item.status = 'error'
          item.error = err.message || '上传失败'
          if (err.detail) {
            item.errorDetail = err.detail
          }
        }

        active.delete(item)
        if (onStatusChange) onStatusChange(item)
        runNext()
      }

      // 启动并发任务
      for (let i = 0; i < Math.min(this.concurrency, pending.length); i++) {
        runNext()
      }

      // 如果没有待上传的文件，直接 resolve
      if (pending.length === 0) resolve()
    })
  }

  /**
   * 重试单个文件上传
   * @param {Object} item - 上传项
   * @param {Function} onStatusChange - 状态变化回调
   */
  async retry(item, onStatusChange) {
    item.status = 'uploading'
    item.progress = 0
    item.error = null
    item.errorDetail = null
    if (onStatusChange) onStatusChange(item)

    try {
      const result = await uploadFile(item.file, item.hash, item.metadata || {})
      item.status = result.status === 'duplicate' ? 'duplicate' : 'success'
      item.result = result
    } catch (err) {
      item.status = 'error'
      item.error = err.message || '上传失败'
      if (err.detail) {
        item.errorDetail = err.detail
      }
    }

    if (onStatusChange) onStatusChange(item)
  }

  /**
   * 中止上传
   */
  abort() {
    this._abort = true
  }
}
