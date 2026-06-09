<template>
  <div class="course-sections">
    <el-card v-for="section in sections" :key="section.id" class="section-card">
      <template #header>
        <div class="section-header">
          <span>{{ section.title }}</span>
          <div class="section-actions">
            <!-- BUG (feature gap): 只有上移下移按钮，没有拖拽排序 -->
            <el-button size="small" @click="moveUp(section.id)" :disabled="section.sort === 0">
              上移
            </el-button>
            <el-button size="small" @click="moveDown(section.id)" :disabled="section.sort === sections.length - 1">
              下移
            </el-button>
          </div>
        </div>
      </template>
      <div class="resource-list">
        <div v-for="res in section.resources" :key="res.id" class="resource-item">
          <el-icon><Document /></el-icon>
          <span>{{ res.name }}</span>
          <!-- 资源也只能上移下移，不能拖拽到其他章节 -->
          <el-button size="small" text @click="moveResourceUp(section.id, res.id)">↑</el-button>
          <el-button size="small" text @click="moveResourceDown(section.id, res.id)">↓</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

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
  await saveSort()
}

const moveDown = async (sectionId: number) => {
  const idx = sections.value.findIndex(s => s.id === sectionId)
  if (idx >= sections.value.length - 1) return
  const temp = sections.value[idx]
  sections.value[idx] = sections.value[idx + 1]
  sections.value[idx + 1] = temp
  await saveSort()
}

const moveResourceUp = (sectionId: number, resourceId: number) => { /* 同理 */ }
const moveResourceDown = (sectionId: number, resourceId: number) => { /* 同理 */ }

const saveSort = async () => {
  const sortData = sections.value.map((s, i) => ({ id: s.id, sort: i }))
  await axios.post('/api/edu/course/sections/sort', sortData)
}

onMounted(loadSections)
</script>
