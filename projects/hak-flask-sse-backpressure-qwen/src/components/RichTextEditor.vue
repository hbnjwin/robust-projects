<template>
  <div class="rich-text-editor">
    <!-- Toolbar container -->
    <div ref="toolbarRef" class="editor-toolbar"></div>
    <!-- Editor container -->
    <div ref="editorRef" class="editor-container" :style="{ height: editorHeight }"></div>
  </div>
</template>

<script setup>
/**
 * RichTextEditor.vue
 *
 * WangEditor wrapper for Vue 3 with proper lifecycle management.
 *
 * Fixes two critical memory leaks:
 *
 * 1. Editor instance leak under keep-alive:
 *    - On `activated`, destroy the previous editor instance before creating a new one.
 *    - On `deactivated` and `onBeforeUnmount`, destroy the editor to release DOM references.
 *
 * 2. Paste event listener leak:
 *    - Track all paste handlers bound to `document`.
 *    - Remove them on `deactivated` and `onBeforeUnmount` so stale editors don't fire uploads.
 */

import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { onActivated, onDeactivated } from 'vue'
import { createEditor, createToolbar } from '@wangeditor/editor'
import '@wangeditor/editor/dist/css/style.css'

// ─── Props & Emits ──────────────────────────────────────────────────────────

const props = defineProps({
  /** v-model HTML content */
  modelValue: {
    type: String,
    default: '',
  },
  /** Editor height (CSS value) */
  editorHeight: {
    type: String,
    default: '400px',
  },
  /** Image upload API endpoint */
  imageUploadUrl: {
    type: String,
    default: '/api/upload/image',
  },
  /** Extra headers for image upload requests */
  uploadHeaders: {
    type: Object,
    default: () => ({}),
  },
  /** Toolbar config override */
  toolbarConfig: {
    type: Object,
    default: () => ({}),
  },
  /** Editor config override */
  editorConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['update:modelValue', 'onCreated', 'onChange', 'onDestroyed'])

// ─── Refs ───────────────────────────────────────────────────────────────────

const toolbarRef = ref(null)
const editorRef = ref(null)

/** @type {import('@wangeditor/editor').IDomEditor | null} */
let editorInstance = null

/** @type {import('@wangeditor/editor').IDomToolbar | null} */
let toolbarInstance = null

/**
 * Accumulator for paste handlers we attach to `document`.
 * Each entry is { handler, options } so we can removeEventListener precisely.
 */
const boundPasteHandlers = []

// ─── Editor factory ─────────────────────────────────────────────────────────

/**
 * Destroy the current editor + toolbar instances and clean up all associated
 * event listeners.  Safe to call multiple times.
 */
function destroyEditor() {
  // 1. Remove every paste handler we registered on `document`.
  boundPasteHandlers.forEach(({ handler, options }) => {
    document.removeEventListener('paste', handler, options)
  })
  boundPasteHandlers.length = 0

  // 2. Destroy toolbar first (it references the editor).
  if (toolbarInstance) {
    try {
      toolbarInstance.destroy()
    } catch (e) {
      console.warn('[RichTextEditor] toolbar destroy error:', e)
    }
    toolbarInstance = null
  }

  // 3. Destroy editor.
  if (editorInstance) {
    try {
      editorInstance.destroy()
    } catch (e) {
      console.warn('[RichTextEditor] editor destroy error:', e)
    }
    editorInstance = null
  }
}

/**
 * Create a fresh editor + toolbar, attaching them to the DOM refs.
 * If a previous instance exists it is destroyed first to prevent leaks.
 */
function createEditorInstance() {
  // Guard: DOM must be ready.
  if (!toolbarRef.value || !editorRef.value) {
    return
  }

  // ── Destroy stale instance (keep-alive reactivation path) ────────────────
  destroyEditor()

  // ── Build editor config ───────────────────────────────────────────────────
  const defaultEditorConfig = {
    placeholder: '请输入内容…',
    autoFocus: false,
    scroll: true,
    readOnly: false,
    // WangEditor uses `onCreated` to hand us the editor ref.
    onCreated(editor) {
      editorInstance = editor

      // Bind the paste handler for image paste-upload.
      attachPasteHandler(editor)

      emit('onCreated', editor)
    },
    onChange(editor) {
      const html = editor.getHtml()
      emit('update:modelValue', html)
      emit('onChange', editor)
    },
    MENU_CONF: {
      uploadImage: {
        server: props.imageUploadUrl,
        fieldName: 'file',
        headers: props.uploadHeaders,
        // 5 MB limit
        maxFileSize: 5 * 1024 * 1024,
        allowedFileTypes: ['image/*'],
      },
    },
    ...props.editorConfig,
  }

  // ── Create editor ─────────────────────────────────────────────────────────
  const editor = createEditor({
    selector: editorRef.value,
    html: props.modelValue || '<p><br></p>',
    config: defaultEditorConfig,
  })

  // ── Create toolbar ────────────────────────────────────────────────────────
  toolbarInstance = createToolbar({
    editor,
    selector: toolbarRef.value,
    mode: 'default',
    config: {
      ...props.toolbarConfig,
    },
  })
}

// ─── Paste handler (image upload) ───────────────────────────────────────────

/**
 * Attach a `paste` listener to `document` for the given editor.
 * The handler is tracked so it can be removed on deactivate / unmount.
 *
 * @param {import('@wangeditor/editor').IDomEditor} editor
 */
function attachPasteHandler(editor) {
  const handler = (event) => {
    // Only act when this editor is focused — avoids firing in stale editors.
    if (!editor.selection) {
      return
    }

    const clipboardData = event.clipboardData
    if (!clipboardData || !clipboardData.items) {
      return
    }

    const items = Array.from(clipboardData.items)
    const imageItem = items.find(
      (item) => item.kind === 'file' && item.type.startsWith('image/'),
    )

    if (!imageItem) {
      return
    }

    event.preventDefault()

    const file = imageItem.getAsFile()
    if (!file) {
      return
    }

    // Use the editor's built-in upload API.
    uploadImageToEditor(editor, file)
  }

  // Register and track.
  document.addEventListener('paste', handler)
  boundPasteHandlers.push({ handler, options: undefined })
}

/**
 * Upload an image file and insert it into the editor at the cursor.
 *
 * @param {import('@wangeditor/editor').IDomEditor} editor
 * @param {File} file
 */
async function uploadImageToEditor(editor, file) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch(props.imageUploadUrl, {
      method: 'POST',
      headers: props.uploadHeaders,
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`)
    }

    const data = await response.json()

    // Insert image node at current selection.
    const imageNode = {
      type: 'image',
      src: data.url,
      href: '',
      alt: file.name || 'image',
      style: {},
      children: [{ text: '' }],
    }

    editor.insertNode(imageNode)
  } catch (err) {
    console.error('[RichTextEditor] paste image upload failed:', err)
  }
}

// ─── Watchers ───────────────────────────────────────────────────────────────

// Sync external modelValue changes into the editor (only when value truly differs).
watch(
  () => props.modelValue,
  (newVal) => {
    if (!editorInstance) return

    // Avoid infinite loop: only set HTML when it actually changed externally.
    const currentHtml = editorInstance.getHtml()
    if (newVal !== currentHtml) {
      editorInstance.setHtml(newVal)
    }
  },
)

// ─── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  // Wait one tick so the DOM containers are fully rendered.
  nextTick(() => {
    createEditorInstance()
  })
})

/**
 * keep-alive `activated`:
 *
 * The component is coming back into view.  The previous editor instance is
 * stale (its DOM container was detached while cached).  We destroy it and
 * create a fresh one so there is always exactly ONE live instance.
 *
 * This is the fix for leak #1: without destroyEditor() here, each activation
 * would create a new editor while the old one stays alive, accumulating in
 * memory.
 */
onActivated(() => {
  nextTick(() => {
    createEditorInstance()
  })
})

/**
 * keep-alive `deactivated`:
 *
 * The component is being cached (navigated away).  Destroy the editor so that:
 *   - The editor's internal DOM nodes are released.
 *   - Paste handlers are removed (fix for leak #2).
 *
 * Without this, the editor stays in memory for the entire keep-alive lifetime,
 * and its paste handler continues to fire.
 */
onDeactivated(() => {
  destroyEditor()
})

/**
 * Full unmount (component is permanently removed):
 * Final safety net — destroy everything.
 */
onBeforeUnmount(() => {
  destroyEditor()
  emit('onDestroyed')
})
</script>

<style scoped>
.rich-text-editor {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.editor-toolbar {
  border-bottom: 1px solid #e0e0e0;
  background-color: #fafafa;
}

.editor-container {
  overflow-y: auto;
}
</style>
