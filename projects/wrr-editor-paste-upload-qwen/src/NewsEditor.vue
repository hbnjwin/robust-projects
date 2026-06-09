<template>
  <div class="news-editor">
    <div style="border: 1px solid #ccc">
      <Toolbar :editor="editorRef" :defaultConfig="toolbarConfig" style="border-bottom: 1px solid #ccc" />
      <Editor
        v-model="valueHtml"
        :defaultConfig="editorConfig"
        style="height: 400px; overflow-y: hidden"
        @onCreated="handleCreated"
      />
    </div>
    <el-button type="primary" @click="handleSave" style="margin-top: 16px">保存</el-button>
  </div>
</template>

<script setup>
import { ref, shallowRef, onBeforeUnmount } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import axios from 'axios'

const emit = defineEmits(['save'])
const props = defineProps({ initialContent: { type: String, default: '' } })

const editorRef = shallowRef()
const valueHtml = ref(props.initialContent)

const toolbarConfig = {}
const editorConfig = {
  placeholder: '请输入新闻内容...',
  MENU_CONF: {
    uploadImage: {
      server: '/api/infra/file/upload',
      fieldName: 'file',
      maxFileSize: 10 * 1024 * 1024
    }
  }
}

const handleCreated = (editor) => {
  editorRef.value = editor
}

// BUG: 从浏览器或微信复制图片粘贴到编辑器中
// WangEditor 会直接插入 base64 格式的图片（data:image/png;base64,...）
// 编辑时能看到图片，因为浏览器可以渲染 base64 图片
// 但保存到数据库后重新打开，base64 图片数据太大可能被截断
// 或者后端拒绝存储超长的 HTML 内容
// 正确的做法是拦截粘贴事件，把 base64 图片先上传到文件服务器，替换为 URL

// BUG: WangEditor 的 customPaste 或 insertedNode 回调没有配置
// 应该在 editorConfig 中添加自定义粘贴处理：
// customPaste: (editor, event) => {
//   const items = event.clipboardData?.items
//   for (const item of items) {
//     if (item.type.startsWith('image/')) {
//       const file = item.getAsFile()
//       uploadAndInsert(editor, file)
//       event.preventDefault()
//     }
//   }
// }

const handleSave = () => {
  // BUG: 保存时 valueHtml 中可能包含大量 base64 图片数据
  // 导致 HTML 内容非常大，可能超出后端字段长度限制
  emit('save', valueHtml.value)
}

onBeforeUnmount(() => {
  const editor = editorRef.value
  if (editor) editor.destroy()
})
</script>
