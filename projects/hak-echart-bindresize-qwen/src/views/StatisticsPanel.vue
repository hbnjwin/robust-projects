<template>
  <div class="statistics-panel">
    <el-row :gutter="20">
      <el-col :span="24">
        <PowerTrendChart />
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <FaultDistributionChart />
      </el-col>
      <el-col :span="12">
        <ReviewProgressChart />
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import PowerTrendChart from '@/components/PowerTrendChart.vue'
import FaultDistributionChart from '@/components/FaultDistributionChart.vue'
import ReviewProgressChart from '@/components/ReviewProgressChart.vue'
</script>

<style scoped>
.statistics-panel {
  padding: 20px;
}
</style>
