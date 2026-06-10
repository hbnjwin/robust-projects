<template>
  <div class="report-editor">
    <div class="editor-header">
      <span class="report-title">{{ reportTitle }}</span>
      <span class="save-status">{{ saveStatus }}</span>
    </div>
    <div ref="toolbarRef" class="editor-toolbar"></div>
    <div ref="editorRef" class="editor-container"></div>
  </div>
</template>

<script>
import '@wangeditor/editor/dist/css/style.css'

import { ref, shallowRef, watch, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { createEditor, createToolbar } from '@wangeditor/editor'

export default {
  name: 'ReportEditor',
  props: {
    reportId: {
      type: [String, Number],
      required: true,
    },
    reportTitle: {
      type: String,
      default: '',
    },
    initialContent: {
      type: String,
      default: '',
    },
    uploadUrl: {
      type: String,
      default: '/api/reports/upload-image',
    },
  },
  emits: ['change', 'save'],
  setup(props, { emit }) {
    const toolbarRef = ref(null)
    const editorRef = ref(null)
    const editorInstance = shallowRef(null)
    const toolbarInstance = shallowRef(null)
    const saveStatus = ref('')

    // --------------------------------------------------------
    // 修复点2: paste事件监听器 —— 保存handler引用以便清理
    // --------------------------------------------------------
    let pasteHandler = null

    function bindPasteUpload(editor) {
      // 先移除旧的监听器（防御性编程）
      unbindPasteUpload()

      pasteHandler = (e) => {
        const items = e.clipboardData && e.clipboardData.items
        if (!items || !items.length) return

        for (let i = 0; i < items.length; i++) {
          const item = items[i]
          if (item.type.indexOf('image/') === -1) continue

          e.preventDefault()
          const file = item.getAsFile()
          if (!file) continue

          // 检查编辑器实例是否仍然存在且未被销毁
          if (!editor || editor.isDestroyed) return

          uploadImage(file, editor)
          break
        }
      }

      document.addEventListener('paste', pasteHandler)
    }

    function unbindPasteUpload() {
      if (pasteHandler) {
        document.removeEventListener('paste', pasteHandler)
        pasteHandler = null
      }
    }

    function uploadImage(file, editor) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('reportId', props.reportId)

      fetch(props.uploadUrl, {
        method: 'POST',
        body: formData,
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.errno === 0 && data.data && data.data.url) {
            // 插入前再次确认编辑器实例有效
            if (editor && !editor.isDestroyed) {
              editor.dangerouslyInsertHtml(`<img src="${data.data.url}" alt="${data.data.alt || ''}" />`)
            }
          }
        })
        .catch((err) => {
          console.error('[ReportEditor] 粘贴图片上传失败:', err)
        })
    }

    // --------------------------------------------------------
    // 编辑器创建与销毁
    // --------------------------------------------------------
    function initEditor() {
      if (!editorRef.value) return

      const editorConfig = {
        placeholder: '请输入审核意见...',
        onChange(editor) {
          emit('change', editor.getHtml())
        },
        MENU_CONF: {
          uploadImage: {
            server: props.uploadUrl,
            fieldName: 'file',
            maxFileSize: 5 * 1024 * 1024,
            allowedFileTypes: ['image/*'],
            meta: { reportId: props.reportId },
          },
        },
      }

      const editor = createEditor({
        selector: editorRef.value,
        html: props.initialContent,
        config: editorConfig,
      })

      const toolbar = createToolbar({
        editor,
        selector: toolbarRef.value,
        config: {},
      })

      editorInstance.value = editor
      toolbarInstance.value = toolbar

      // 绑定粘贴图片上传监听
      bindPasteUpload(editor)
    }

    // --------------------------------------------------------
    // 修复点1: 正确销毁editor实例，清理所有资源
    // --------------------------------------------------------
    function destroyEditor() {
      // 先解绑paste事件监听
      unbindPasteUpload()

      // 销毁toolbar实例
      if (toolbarInstance.value) {
        // wangEditor toolbar没有destroy方法，置空即可
        toolbarInstance.value = null
      }

      // 销毁editor实例
      if (editorInstance.value) {
        if (!editorInstance.value.isDestroyed) {
          editorInstance.value.destroy()
        }
        editorInstance.value = null
      }
    }

    // --------------------------------------------------------
    // keep-alive 生命周期处理
    // --------------------------------------------------------
    // 组件被激活时（从缓存恢复），初始化编辑器
    onActivated(() => {
      // 先销毁可能残留的旧实例，防止实例累积
      destroyEditor()
      initEditor()
    })

    // 组件被停用时（进入缓存），销毁编辑器释放内存
    onDeactivated(() => {
      destroyEditor()
    })

    // 组件真正卸载时的兜底清理
    onBeforeUnmount(() => {
      destroyEditor()
    })

    // 切换报告时，需要重建编辑器
    watch(
      () => props.reportId,
      () => {
        destroyEditor()
        initEditor()
      }
    )

    return {
      toolbarRef,
      editorRef,
      saveStatus,
    }
  },
}
</script>

<style scoped>
.report-editor {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}
.report-title {
  font-weight: 600;
  font-size: 14px;
}
.save-status {
  font-size: 12px;
  color: #999;
}
.editor-toolbar {
  border-bottom: 1px solid #e8e8e8;
}
.editor-container {
  height: 400px;
  overflow-y: auto;
}
</style>
