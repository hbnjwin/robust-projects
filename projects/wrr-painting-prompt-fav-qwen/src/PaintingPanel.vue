<template>
  <div class="painting-panel">
    <div class="prompt-input">
      <el-input
        v-model="prompt"
        type="textarea"
        :rows="4"
        placeholder="请输入绘画提示词..."
      />
      <div class="prompt-actions">
        <el-button type="primary" @click="generateImage" :loading="generating">
          生成
        </el-button>
        <!-- BUG (enhancement gap): 没有收藏按钮 -->
        <!-- <el-button @click="saveToFavorites">收藏提示词</el-button> -->
        <!-- <el-button @click="showFavorites = true">收藏夹</el-button> -->
        <!-- <el-button @click="showHistory = true">历史记录</el-button> -->
      </div>
    </div>

    <!-- BUG: 每次都要重新输入提示词，没有收藏和历史功能 -->
    <!-- 用户体验差：常用的提示词模板无法保存和复用 -->

    <div v-if="generatedImage" class="result">
      <img :src="generatedImage" alt="生成的图片" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const prompt = ref('')
const generating = ref(false)
const generatedImage = ref('')

// BUG: 缺少提示词收藏功能
// 需要实现：
// 1. 收藏当前提示词到 localStorage
// 2. 从收藏列表快速填入提示词
// 3. 查看和复用历史提示词
// interface PromptFavorite {
//   id: string
//   prompt: string
//   tags: string[]
//   createdAt: string
// }
// const favorites = ref<PromptFavorite[]>([])

const generateImage = async () => {
  if (!prompt.value.trim()) return
  generating.value = true
  try {
    const { data } = await axios.post('/api/ai/image/generate', {
      prompt: prompt.value
    })
    generatedImage.value = data.data.imageUrl

    // BUG: 生成成功后没有保存到历史记录
  } finally {
    generating.value = false
  }
}
</script>
