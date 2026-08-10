<script setup>
/**
 * 懒加载封面 —— 进入视口才请求，失败则退回占位图标。
 *
 * 封面缺失有两种情况：从未生成（关了缩略图开关 / 没装 ffmpeg）
 * 与文件已失效；两者都用同一个占位图标，不弹错误干扰浏览。
 */
import { ref, watch } from 'vue'

import Icon from './Icon.vue'
import { useInView } from '../composables/useInView.js'

const props = defineProps({
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  icon: { type: String, default: 'film' },
})

const { el, visible } = useInView()
const failed = ref(false)

// 重命名后封面 URL 不变但内容可能变了，src 变化时重置失败标记
watch(() => props.src, () => { failed.value = false })
</script>

<template>
  <div ref="el" class="mv-cover-slot">
    <img
      v-if="src && visible && !failed"
      class="mv-card__img"
      :src="src"
      :alt="alt"
      loading="lazy"
      decoding="async"
      draggable="false"
      @error="failed = true"
    />
    <div v-else class="mv-card__ph">
      <Icon :name="icon" :size="26" />
    </div>
  </div>
</template>

<style scoped>
.mv-cover-slot { width: 100%; height: 100%; }
</style>
