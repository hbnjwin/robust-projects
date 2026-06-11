<template>
  <div class="chat-export">
    <el-dropdown @command="handleExport">
      <el-button>
        导出对话 <el-icon><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="docx">导出为 DOCX</el-dropdown-item>
          <el-dropdown-item command="text">导出为纯文本</el-dropdown-item>
          <!-- BUG (feature gap): 缺少 Markdown 格式导出选项 -->
          <!-- 产品要求增加 Markdown 格式导出 -->
          <!-- <el-dropdown-item command="markdown">导出为 Markdown</el-dropdown-item> -->
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

const props = defineProps<{
  messages: ChatMessage[]
  conversationTitle: string
}>()

const handleExport = (format: string) => {
  switch (format) {
    case 'docx':
      exportAsDocx()
      break
    case 'text':
      exportAsText()
      break
    // BUG: 没有 markdown case
    // case 'markdown':
    //   exportAsMarkdown()
    //   break
  }
}

const exportAsDocx = () => {
  // 使用 docx 库生成 DOCX 文件
  console.log('导出 DOCX...')
}

const exportAsText = () => {
  let text = `对话: ${props.conversationTitle}\n\n`
  for (const msg of props.messages) {
    const role = msg.role === 'user' ? '用户' : 'AI'
    text += `[${role}] ${msg.timestamp}\n${msg.content}\n\n`
  }
  downloadFile(text, `${props.conversationTitle}.txt`, 'text/plain')
}

// BUG: 缺少 exportAsMarkdown 方法
// 需要实现：
// 1. 代码块保留语言标识（```js ... ```）
// 2. 列表、标题层级正确转换
// 3. 下载 .md 文件

const downloadFile = (content: string, filename: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>
