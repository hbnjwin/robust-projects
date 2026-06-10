<template>
  <t-dialog v-model:visible="visible" header="任务详情" width="800px">
    <div class="stats-bar">
      <t-tag theme="success">通过: {{ stats.pass }}</t-tag>
      <t-tag theme="warning">警告: {{ stats.warn }}</t-tag>
      <t-tag theme="danger">失败: {{ stats.fail }}</t-tag>
    </div>
    <t-table :data="checkResults" :columns="columns">
      <template #opinion="{ row }">
        <div v-html="sanitizeHtml(row.opinion)"></div>
      </template>
      <template #status="{ row }">
        <t-tag v-if="row.status" :theme="getStatusTheme(row.status)">{{ row.status }}</t-tag>
      </template>
    </t-table>
  </t-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getTaskDetail } from '@/api/modules/ai-report-review'

const props = defineProps({ taskId: String })
const visible = ref(false)
const stats = ref({ pass: 0, warn: 0, fail: 0 })
const checkResults = ref([])
const columns = [
  { colKey: 'name', title: '检查项', cell: (h, { row }) => row.name ?? '' },
  { colKey: 'opinion', title: '审查意见', cell: 'opinion' },
  { colKey: 'status', title: '状态', cell: 'status' },
]

const getStatusTheme = (s) => ({ pass: 'success', warn: 'warning', fail: 'danger' }[s])

const DANGEROUS_TAGS = ['script', 'iframe', 'object', 'embed', 'form', 'link', 'meta', 'base', 'applet']
const EVENT_ATTR_RE = /^on/i
const JS_PROTO_RE = /^\s*javascript\s*:/i

const sanitizeHtml = (html) => {
  if (html == null) return ''
  const str = String(html)
  if (!str) return ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(str, 'text/html')
  const clean = (node) => {
    const children = [...node.childNodes]
    for (const child of children) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const tag = child.tagName.toLowerCase()
        if (DANGEROUS_TAGS.includes(tag)) {
          child.remove()
          continue
        }
        const attrs = [...child.attributes]
        for (const attr of attrs) {
          if (EVENT_ATTR_RE.test(attr.name)) {
            child.removeAttribute(attr.name)
          } else if ((attr.name === 'href' || attr.name === 'src') && JS_PROTO_RE.test(attr.value)) {
            child.removeAttribute(attr.name)
          }
        }
        clean(child)
      }
    }
  }
  clean(doc.body)
  return doc.body.innerHTML
}

watch(() => props.taskId, async (id) => {
  if (!id) return
  const res = await getTaskDetail(id)
  const items = res.items || []
  checkResults.value = items
  stats.value = {
    pass: items.filter(i => i.status === 'pass').length,
    warn: items.filter(i => i.status === 'warn').length,
    fail: items.filter(i => i.status === 'fail').length,
  }
})
</script>
