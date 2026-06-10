<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import ReportItem from './ReportItem.vue'

interface Report {
  id: number
  title: string
  status: 'pending' | 'approved' | 'rejected'
  reviewer: string
  createdAt: string
}

const props = defineProps<{
  reports: Report[]
}>()

// ---- 筛选逻辑 ----
const filterOptions = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已审核' },
  { value: 'rejected', label: '已驳回' },
] as const

const activeFilter = ref<string>('all')

const filteredReports = computed(() => {
  if (activeFilter.value === 'all') {
    return props.reports
  }
  return props.reports.filter(r => r.status === activeFilter.value)
})

// ---- 虚拟滚动 ----
const scroller = ref<InstanceType<typeof DynamicScroller> | null>(null)

// 关键修复：筛选条件变化时重置虚拟滚动缓存和滚动位置
// 不重置会导致：
//   1. 旧的行高缓存应用到新数据上，行间出现间隙
//   2. 滚动偏移量对不上新列表长度，看到上次结果的残影
watch(activeFilter, async () => {
  await nextTick() // 等 filteredReports 计算完成、DOM 更新
  if (!scroller.value) return

  // 步骤1: 强制清除所有已缓存的行高测量值
  // forceUpdate() 会丢弃 ResizeObserver 积累的尺寸缓存，
  // 让 DynamicScroller 对新数据集中的每个 item 重新测量
  scroller.value.forceUpdate()

  // 步骤2: 将滚动位置重置到顶部
  // 避免停留在旧列表的某个偏移位置，导致新列表渲染错位
  scroller.value.scrollToItem(0)
})

// 当外部传入的 reports 数组整体替换时（如翻页、刷新），同样需要重置
watch(
  () => props.reports,
  async () => {
    await nextTick()
    if (!scroller.value) return
    scroller.value.forceUpdate()
    scroller.value.scrollToItem(0)
  },
)
</script>

<template>
  <div class="report-list-container">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <button
        v-for="opt in filterOptions"
        :key="opt.value"
        :class="['filter-btn', { active: activeFilter === opt.value }]"
        @click="activeFilter = opt.value"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- 虚拟滚动列表 -->
    <!--
      关键修复说明：
      - 使用 DynamicScroller 替代 RecycleScroller
        RecycleScroller 需要 item-size（固定行高），不适合行高不统一的场景
        DynamicScroller 通过 ResizeObserver 自动测量每行真实高度

      - min-item-size 设为单行报告的最小高度（标题单行 + meta行 + padding）
        这个值只影响首次渲染时的预估，不影响最终布局精度
        设得过大会导致初始渲染的行数偏少（滚动时补渲染），过小则初始多渲染几行（性能略差但更安全）

      - key-field="id" 确保列表项有稳定的唯一标识
        筛选后列表项顺序变化时，Vue 能正确复用/销毁 DOM 节点
    -->
    <DynamicScroller
      ref="scroller"
      :items="filteredReports"
      :min-item-size="64"
      key-field="id"
      class="scroller"
    >
      <template #default="{ item, index, active }">
        <!--
          DynamicScrollerItem 必须包裹每个列表行
          - :item 和 :active 是必传的，DynamicScrollerItem 依赖它们触发 ResizeObserver
          - :index 用于内部定位计算（如 buffer 区域判断）
          - 不传 active 会导致行高无法被正确追踪，快速滚动时出现间隙
        -->
        <DynamicScrollerItem
          :item="item"
          :active="active"
          :index="index"
          :data-index="index"
        >
          <ReportItem :report="item" />
        </DynamicScrollerItem>
      </template>
    </DynamicScroller>
  </div>
</template>

<style scoped>
.report-list-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.filter-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
  flex-shrink: 0;
}

.filter-btn {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  color: #606266;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.filter-btn:hover {
  color: #409eff;
  border-color: #c6e2ff;
}

.filter-btn.active {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.scroller {
  flex: 1;
  overflow-y: auto;
}
</style>
