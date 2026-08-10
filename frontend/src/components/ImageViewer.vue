<script setup>
/**
 * 全屏看图 —— ←/→ 翻页、Esc 关闭、空格下一张。
 *
 * 直接取原图（/api/original/photo/<id>/）而不是缩略图，
 * 缩略图只有 480px 宽，全屏会明显发虚。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import Icon from './Icon.vue'
import { fmtSize, photoOriginalUrl } from '../utils.js'

const props = defineProps({
  items: { type: Array, required: true },
  index: { type: Number, default: 0 },
})
const emit = defineEmits(['close', 'update:index', 'fav', 'seen'])

const failed = ref(false)

const current = computed(() => props.items[props.index] || null)
const canPrev = computed(() => props.index > 0)
const canNext = computed(() => props.index < props.items.length - 1)

const src = computed(() => (current.value ? photoOriginalUrl(current.value.id) : ''))

const meta = computed(() => {
  const p = current.value
  if (!p) return ''
  const parts = []
  if (p.width && p.height) parts.push(`${p.width} × ${p.height}`)
  if (p.file_size) parts.push(fmtSize(p.file_size))
  if (p.library_name) parts.push(p.library_name)
  return parts.join(' · ')
})

function go(step) {
  const next = props.index + step
  if (next < 0 || next >= props.items.length) return
  emit('update:index', next)
}

function onKey(e) {
  if (e.key === 'Escape') emit('close')
  else if (e.key === 'ArrowLeft') go(-1)
  else if (e.key === 'ArrowRight' || e.key === ' ') {
    e.preventDefault()
    go(1)
  }
}

// 每次换图都记一条浏览记录，并重置加载失败标记
watch(current, (p) => {
  failed.value = false
  if (p) emit('seen', p)
}, { immediate: true })

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="mv-viewer" @click.self="emit('close')">
      <div class="mv-viewer__bar">
        <div class="mv-grow" style="min-width: 0">
          <div class="mv-viewer__name">{{ current?.name }}</div>
          <div class="mv-dim" style="font-size: 11.5px">
            {{ index + 1 }} / {{ items.length }} · {{ meta }}
          </div>
        </div>
        <button
          class="mv-icon-btn"
          type="button"
          :title="current?.is_favorited ? '取消收藏' : '加入收藏'"
          :style="current?.is_favorited ? 'color: var(--warn)' : ''"
          @click="emit('fav', current)"
        >
          <Icon name="star" :size="18" />
        </button>
        <button class="mv-icon-btn" type="button" aria-label="关闭" @click="emit('close')">
          <Icon name="x" :size="18" />
        </button>
      </div>

      <img
        v-if="src && !failed"
        class="mv-viewer__img"
        :src="src"
        :alt="current?.name"
        draggable="false"
        @error="failed = true"
      />
      <div v-else class="mv-empty">
        <div class="mv-empty__icon"><Icon name="warn" :size="24" /></div>
        <div class="mv-empty__title">图片无法显示</div>
        <p class="mv-empty__desc">文件可能已被移动、删除，或所在磁盘未连接。</p>
      </div>

      <button
        v-if="canPrev"
        class="mv-viewer__nav mv-viewer__nav--prev"
        type="button"
        aria-label="上一张"
        @click.stop="go(-1)"
      >
        <Icon name="chevronLeft" :size="20" />
      </button>
      <button
        v-if="canNext"
        class="mv-viewer__nav mv-viewer__nav--next"
        type="button"
        aria-label="下一张"
        @click.stop="go(1)"
      >
        <Icon name="chevronRight" :size="20" />
      </button>
    </div>
  </Teleport>
</template>
