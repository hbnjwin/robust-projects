<template>
  <div class="statistics-panel">
    <el-row :gutter="16">
      <!-- 发电量趋势图 -->
      <el-col :span="24">
        <el-card header="发电量趋势">
          <div ref="trendChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 故障分布饼图 -->
      <el-col :span="12">
        <el-card header="故障分布">
          <div ref="faultChartRef" class="chart-container" />
        </el-card>
      </el-col>

      <!-- 审核进度柱状图 -->
      <el-col :span="12">
        <el-card header="审核进度">
          <div ref="progressChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useECharts } from '@/composables/useECharts'

// ── 图表容器引用 ──

const trendChartRef = ref<HTMLElement | null>(null)
const faultChartRef = ref<HTMLElement | null>(null)
const progressChartRef = ref<HTMLElement | null>(null)

// ── 使用 useECharts 管理每个图表实例 ──
// 每个图表独立管理自己的resize绑定和生命周期

const { setOption: setTrendOption } = useECharts(trendChartRef)
const { setOption: setFaultOption } = useECharts(faultChartRef)
const { setOption: setProgressOption } = useECharts(progressChartRef)

// ── 初始化图表数据 ──

onMounted(() => {
  initTrendChart()
  initFaultChart()
  initProgressChart()
})

function initTrendChart(): void {
  setTrendOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月',
             '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: { type: 'value', name: '发电量 (MWh)' },
    series: [{
      name: '发电量',
      type: 'line',
      smooth: true,
      data: [820, 932, 901, 1034, 1290, 1330,
             1520, 1430, 1380, 1210, 1050, 890],
      areaStyle: { opacity: 0.3 }
    }]
  })
}

function initFaultChart(): void {
  setFaultOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      name: '故障类型',
      type: 'pie',
      radius: ['40%', '70%'],
      data: [
        { value: 35, name: '叶片故障' },
        { value: 25, name: '齿轮箱异常' },
        { value: 20, name: '发电机过热' },
        { value: 15, name: '偏航系统' },
        { value: 5, name: '其他' }
      ]
    }]
  })
}

function initProgressChart(): void {
  setProgressOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: ['风场A', '风场B', '风场C', '风场D', '风场E']
    },
    yAxis: { type: 'value', name: '审核数量', max: 100 },
    series: [
      {
        name: '已审核',
        type: 'bar',
        stack: 'total',
        data: [85, 72, 90, 65, 78],
        itemStyle: { color: '#67C23A' }
      },
      {
        name: '待审核',
        type: 'bar',
        stack: 'total',
        data: [15, 28, 10, 35, 22],
        itemStyle: { color: '#E6A23C' }
      }
    ]
  })
}
</script>

<style scoped>
.statistics-panel {
  padding: 16px;
}

.chart-container {
  width: 100%;
  height: 400px;
}
</style>
