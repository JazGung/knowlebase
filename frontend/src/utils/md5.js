/**
 * 使用 spark-md5 分块计算文件 MD5
 * 避免大文件一次性加载到内存
 */
import SparkMD5 from 'spark-md5'

const CHUNK_SIZE = 2 * 1024 * 1024 // 2MB

/**
 * 计算文件 MD5 哈希值
 * @param {File} file - 文件对象
 * @param {Function} onProgress - 可选进度回调 (percent: 0-100)
 * @returns {Promise<string>} MD5 hex 字符串
 */
export function computeMD5(file, onProgress) {
  return new Promise((resolve, reject) => {
    const spark = new SparkMD5.ArrayBuffer()
    const fileReader = new FileReader()
    let currentChunk = 0
    const chunks = Math.ceil(file.size / CHUNK_SIZE)

    fileReader.onload = (e) => {
      spark.append(e.target.result)
      currentChunk++

      if (onProgress) {
        onProgress(Math.round((currentChunk / chunks) * 100))
      }

      if (currentChunk < chunks) {
        loadNext()
      } else {
        resolve(spark.end())
      }
    }

    fileReader.onerror = () => {
      reject(new Error('文件读取失败'))
    }

    function loadNext() {
      const start = currentChunk * CHUNK_SIZE
      const end = Math.min(start + CHUNK_SIZE, file.size)
      fileReader.readAsArrayBuffer(file.slice(start, end))
    }

    loadNext()
  })
}
