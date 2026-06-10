<template>
  <div class="rulebase">
    <div class="toolbar">
      <t-button @click="handleCreate">新建规则</t-button>
      <t-input v-model="keyword" placeholder="搜索规则" />
    </div>
    <t-table :data="tableData" :columns="columns" :loading="loading">
      <template #operation="{ row }">
        <t-button variant="text" @click="handleEdit(row)">编辑</t-button>
        <t-button variant="text" theme="danger" @click="handleDelete(row)">删除</t-button>
      </template>
    </t-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const keyword = ref('')
const tableData = ref([])
const loading = ref(false)
const columns = [
  { colKey: 'name', title: '规则名称' },
  { colKey: 'type', title: '类型' },
  { colKey: 'description', title: '描述' },
  { colKey: 'operation', title: '操作', cell: 'operation' },
]

const getTableList = () => { /* TODO: implement */ }
const handleCreate = () => {}
const handleEdit = (row) => {}
const handleDelete = (row) => {}

onMounted(getTableList)
</script>
