<template>
  <div class="table-pagination">
    <t-pagination
      :total="total"
      :current="current"
      :page-size="pageSize"
      :page-size-options="[10, 20, 50, 100]"
      show-sizer
      @current-change="onCurrentChange"
      @page-size-change="onPageSizeChange"
    />
  </div>
</template>

<script setup>
const props = defineProps({
  total: { type: Number, default: 0 },
  current: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})

const emit = defineEmits(['change'])

function onCurrentChange(page) {
  emit('change', { current: page, pageSize: props.pageSize })
}

function onPageSizeChange(size) {
  emit('change', { current: 1, pageSize: size })
}
</script>
