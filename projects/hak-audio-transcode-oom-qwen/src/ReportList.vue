<template>
  <div class="report-list-wrapper">
    <!-- 筛选条件区域 -->
    <div class="filter-bar">
      <el-select
        v-model="filterStatus"
        placeholder="审核状态"
        clearable
        @change="handleFilterChange"
      >
        <el-option label="全部" value="" />
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
      </el-select>

      <el-input
        v-model="searchKeyword"
        placeholder="搜索报告标题"
        clearable
        @input="handleFilterChange"
      />
    </div>

    <!--
      修复核心 1：使用 DynamicScroller + DynamicScrollerItem 替代 RecycleScroller
      ─────────────────────────────────────────────────────────
      RecycleScroller 要求所有行等高（通过 itemSize 固定），当报告行因标题换行、
      标签数量不同而高度不一致时，快速滚动会出现行间白缝、内容错位。
      DynamicScroller 会在运行时逐行测量实际高度并缓存，彻底解决不等高问题。

      修复核心 2：通过 :key="scrollerKey" 强制重建 scroller
      ──────────────────────────────────────
      DynamicScroller 内部会缓存每个 item 的测量高度。筛选条件变化后，
      数据源被替换为新列表，但缓存中仍然保留旧数据的高度信息，
      导致新数据项使用了旧的缓存高度 → 出现上一轮筛选结果的"残影"。
      每次筛选变化时递增 scrollerKey，让 Vue 销毁旧 scroller 实例并重建，
      从而清空全部高度缓存。

      修复核心 3：筛选变化时重置滚动位置到顶部
      ──────────────────────────────────────
      切换筛选条件后，列表数据量可能大幅缩减（如从上千条变到几十条），
      如果不重置 scrollTop，用户会看到空白区域。
    -->
    <DynamicScroller
      :key="scrollerKey"
      ref="scrollerRef"
      class="report-scroller"
      :items="filteredReports"
      :min-item-size="72"
      key-field="id"
      :buffer="400"
    >
      <template #default="{ item, index, active }">
        <DynamicScrollerItem
          :item="item"
          :active="active"
          :data-index="index"
          :size-dependencies="[
            item.title,
            item.status,
            item.tags,
            item.reviewers,
            item.createdAt,
          ]"
        >
          <ReportItem :report="item" />
        </DynamicScrollerItem>
      </template>
    </DynamicScroller>

    <!-- 空状态提示 -->
    <div v-if="filteredReports.length === 0" class="empty-state">
      暂无匹配的报告记录
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import ReportItem from './ReportItem.vue'

interface Report {
  id: string | number
  title: string
  status: 'pending' | 'approved' | 'rejected'
  tags: string[]
  reviewers: { name: string; avatar: string }[]
  createdAt: string
  summary: string
}

const props = defineProps<{
  reports: Report[]
}>()

// ─── 筛选状态 ───
const filterStatus = ref('')
const searchKeyword = ref('')

// ─── scroller 重建控制 ───
const scrollerRef = ref<InstanceType<typeof DynamicScroller> | null>(null)
const scrollerKey = ref(0)

// ─── 筛选后的数据 ───
const filteredReports = computed(() => {
  let result = props.reports

  if (filterStatus.value) {
    result = result.filter((r) => r.status === filterStatus.value)
  }

  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    result = result.filter((r) => r.title.toLowerCase().includes(kw))
  }

  return result
})

/**
 * 筛选条件变化时的统一处理：
 * 1. 递增 scrollerKey → 触发 :key 变化 → Vue 销毁旧 DynamicScroller 并重建
 *    → 旧实例内部的高度缓存 (v-measure) 随之清除，新数据项全部重新测量
 * 2. 等待 nextTick 后重置滚动位置到顶部
 */
const handleFilterChange = () => {
  // 递增 key 强制重建 scroller，清空高度缓存
  scrollerKey.value++

  nextTick(() => {
    // 新 scroller 实例挂载后，滚动位置归零
    if (scrollerRef.value?.$el) {
      scrollerRef.value.$el.scrollTop = 0
    }
  })
}

// 监听筛选数据变化（比如外部 props.reports 被替换时），也做同样的缓存清理
watch(
  () => props.reports,
  () => {
    scrollerKey.value++
    nextTick(() => {
      if (scrollerRef.value?.$el) {
        scrollerRef.value.$el.scrollTop = 0
      }
    })
  },
)
</script>

<style scoped>
.report-list-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.filter-bar {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.filter-bar .el-select {
  width: 140px;
}

.filter-bar .el-input {
  flex: 1;
}

.report-scroller {
  flex: 1;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
  font-size: 14px;
}
</style>
