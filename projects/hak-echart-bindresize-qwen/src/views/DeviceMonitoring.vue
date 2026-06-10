<template>
  <div class="device-monitoring">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>设备监控</span>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8" v-for="device in devices" :key="device.id">
          <el-card shadow="hover" class="device-card">
            <div class="device-info">
              <h4>{{ device.name }}</h4>
              <p>状态：<el-tag :type="device.status === '运行中' ? 'success' : 'danger'">{{ device.status }}</el-tag></p>
              <p>功率：{{ device.power }} kW</p>
              <p>转速：{{ device.speed }} rpm</p>
              <p>温度：{{ device.temperature }}°C</p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const devices = ref([
  { id: 1, name: '风机 #1', status: '运行中', power: 1500, speed: 12, temperature: 45 },
  { id: 2, name: '风机 #2', status: '运行中', power: 1480, speed: 11, temperature: 43 },
  { id: 3, name: '风机 #3', status: '停机', power: 0, speed: 0, temperature: 25 },
  { id: 4, name: '风机 #4', status: '运行中', power: 1520, speed: 13, temperature: 47 },
  { id: 5, name: '风机 #5', status: '运行中', power: 1490, speed: 12, temperature: 44 },
  { id: 6, name: '风机 #6', status: '维护中', power: 0, speed: 0, temperature: 30 }
])
</script>

<style scoped>
.device-monitoring {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.device-card {
  margin-bottom: 20px;
}

.device-info h4 {
  margin: 0 0 12px 0;
  color: #303133;
}

.device-info p {
  margin: 8px 0;
  color: #606266;
  font-size: 14px;
}
</style>
