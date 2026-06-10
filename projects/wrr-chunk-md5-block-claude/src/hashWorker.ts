import SparkMD5 from 'spark-md5'

const CHUNK_SIZE = 2 * 1024 * 1024 // 2MB per hash chunk

self.onmessage = async (e: MessageEvent<{ file: File }>) => {
  const { file } = e.data
  const spark = new SparkMD5.ArrayBuffer()
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE)

  try {
    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE
      const end = Math.min(start + CHUNK_SIZE, file.size)
      const blob = file.slice(start, end)
      const buffer = await blob.arrayBuffer()
      spark.append(buffer)
      self.postMessage({ type: 'progress', progress: Math.round(((i + 1) / totalChunks) * 100) })
    }

    const hash = spark.end()
    self.postMessage({ type: 'done', hash })
  } catch (err) {
    self.postMessage({ type: 'error', error: (err as Error).message })
  }
}
