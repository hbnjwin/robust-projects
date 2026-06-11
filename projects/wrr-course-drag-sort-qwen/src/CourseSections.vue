<template>
  <div class="course-sections">
    <draggable
      v-model="sections"
      handle=".drag-handle"
      item-key="id"
      animation="200"
      ghost-class="drag-ghost"
      @end="onSectionDragEnd"
    >
      <template #item="{ element: section }">
        <el-card class="section-card">
          <template #header>
            <div class="section-header">
              <el-icon class="drag-handle"><Rank /></el-icon>
              <span class="section-title">{{ section.title }}</span>
              <div class="section-actions">
                <el-button size="small" @click="moveUp(section.id)" :disabled="section.sort === 0">
                  上移
                </el-button>
                <el-button size="small" @click="moveDown(section.id)" :disabled="section.sort === sections.length - 1">
                  下移
                </el-button>
              </div>
            </div>
          </template>
          <draggable
            v-model="section.resources"
            :group="{ name: 'resources' }"
            handle=".resource-drag-handle"
            item-key="id"
            animation="200"
            ghost-class="drag-ghost"
            class="resource-list"
            @end="onResourceDragEnd"
          >
            <template #item="{ element: res }">
              <div class="resource-item">
                <el-icon class="resource-drag-handle"><Rank /></el-icon>
                <el-icon><Document /></el-icon>
                <span class="resource-name">{{ res.name }}</span>
              </div>
            </template>
          </draggable>
        </el-card>
      </template>
    </draggable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Rank, Document } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'

interface Resource {
  id: number
  name: string
  type: string
  sort: number
}

interface Section {
  id: number
  title: string
  sort: number
  resources: Resource[]
}

const props = defineProps<{ courseId: number }>()
const sections = ref<Section[]>([])

const loadSections = async () => {
  const { data } = await axios.get(`/api/edu/course/sections?courseId=${props.courseId}`)
  sections.value = data.data
}

const moveUp = async (sectionId: number) => {
  const idx = sections.value.findIndex(s => s.id === sectionId)
  if (idx <= 0) return
  const temp = sections.value[idx]
  sections.value[idx] = sections.value[idx - 1]
  sections.value[idx - 1] = temp
  reindexSections()
  await saveSectionSort()
}

const moveDown = async (sectionId: number) => {
  const idx = sections.value.findIndex(s => s.id === sectionId)
  if (idx >= sections.value.length - 1) return
  const temp = sections.value[idx]
  sections.value[idx] = sections.value[idx + 1]
  sections.value[idx + 1] = temp
  reindexSections()
  await saveSectionSort()
}

const reindexSections = () => {
  sections.value.forEach((s, i) => {
    s.sort = i
  })
}

const reindexResources = (section: Section) => {
  section.resources.forEach((r, i) => {
    r.sort = i
  })
}

const onSectionDragEnd = async () => {
  reindexSections()
  await saveSectionSort()
}

const onResourceDragEnd = async () => {
  sections.value.forEach(s => reindexResources(s))
  await saveResourceSort()
}

const saveSectionSort = async () => {
  try {
    const sortData = sections.value.map((s, i) => ({ id: s.id, sort: i }))
    await axios.post('/api/edu/course/sections/sort', sortData)
    ElMessage.success('章节排序已保存')
  } catch {
    ElMessage.error('保存失败，请重试')
  }
}

const saveResourceSort = async () => {
  try {
    const sortData = sections.value.flatMap(s =>
      s.resources.map((r, i) => ({ id: r.id, sectionId: s.id, sort: i }))
    )
    await axios.post('/api/edu/course/resources/sort', sortData)
    ElMessage.success('资源排序已保存')
  } catch {
    ElMessage.error('保存失败，请重试')
  }
}

onMounted(loadSections)
</script>

<style scoped>
.course-sections {
  padding: 16px;
}

.section-card {
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title {
  flex: 1;
}

.section-actions {
  display: flex;
  gap: 4px;
}

.drag-handle,
.resource-drag-handle {
  cursor: grab;
  color: #909399;
  font-size: 16px;
}

.drag-handle:active,
.resource-drag-handle:active {
  cursor: grabbing;
}

.resource-list {
  min-height: 40px;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f0f0;
}

.resource-item:last-child {
  border-bottom: none;
}

.resource-name {
  flex: 1;
}

.drag-ghost {
  opacity: 0.5;
  background: #e8f4ff;
}
</style>
