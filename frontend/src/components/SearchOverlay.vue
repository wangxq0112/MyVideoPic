<script setup>
/**
 * 搜索浮层 —— 顶栏放大镜（或 Ctrl+K）唤起。
 *
 * 键盘优先：↑↓ 选中、Enter 打开、Esc 关闭，无需碰鼠标。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import Icon from './Icon.vue'
import Modal from './Modal.vue'
import { errMsg, searchMedia } from '../api/api.js'
import { useUiStore } from '../stores/ui.js'
import { debounce, fmtDuration, fmtSize, photoCoverUrl, videoCoverUrl } from '../utils.js'

const emit = defineEmits(['photo'])

const router = useRouter()
const ui = useUiStore()

const box = ref(null)
const q = ref('')
const scope = ref('all')
const loading = ref(false)
const error = ref('')
const results = ref([])
const cursor = ref(0)

const SCOPES = [
  { key: 'all', label: '全部' },
  { key: 'video', label: '视频' },
  { key: 'photo', label: '图片' },
]

const hasQuery = computed(() => q.value.trim().length > 0)

async function run() {
  const keyword = q.value.trim()
  if (!keyword) {
    results.value = []
    error.value = ''
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await searchMedia(keyword, scope.value)
    const videos = (res.data.videos || []).map((v) => ({ ...v, kind: 'video' }))
    const photos = (res.data.photos || []).map((p) => ({ ...p, kind: 'photo' }))
    results.value = [...videos, ...photos]
    cursor.value = 0
  } catch (e) {
    error.value = errMsg(e, '搜索失败')
    results.value = []
  } finally {
    loading.value = false
  }
}

const runDebounced = debounce(run, 260)

watch(q, () => runDebounced())
watch(scope, () => run())

function coverOf(item) {
  if (!item.has_cover) return ''
  return item.kind === 'video' ? videoCoverUrl(item.id) : photoCoverUrl(item.id)
}

function metaOf(item) {
  const parts = [item.kind === 'video' ? '视频' : '图片']
  if (item.library_name) parts.push(item.library_name)
  if (item.kind === 'video' && item.duration) parts.push(fmtDuration(item.duration))
  if (item.file_size) parts.push(fmtSize(item.file_size))
  return parts.join(' · ')
}

function open(item) {
  ui.closeOverlays()
  if (item.kind === 'video') {
    router.push(`/play/${item.id}`)
  } else {
    // 图片没有独立路由，交给图片页的查看器处理
    emit('photo', item)
  }
}

function onKey(e) {
  if (!results.value.length) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    cursor.value = (cursor.value + 1) % results.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    cursor.value = (cursor.value - 1 + results.value.length) % results.value.length
  } else if (e.key === 'Enter') {
    e.preventDefault()
    open(results.value[cursor.value])
  }
}

onMounted(async () => {
  await nextTick()
  box.value?.focus()
})

onBeforeUnmount(() => runDebounced.cancel())
</script>

<template>
  <Modal wide flush @close="ui.closeOverlays()">
    <template #default>
      <div class="mv-searchbox">
        <Icon name="search" :size="18" class="mv-dim" />
        <input
          ref="box"
          v-model="q"
          type="search"
          placeholder="搜索视频与图片名称…"
          autocomplete="off"
          spellcheck="false"
          @keydown="onKey"
        />
        <Icon v-if="loading" name="spinner" :size="16" class="mv-spin mv-dim" />
        <button class="mv-icon-btn" type="button" aria-label="关闭" @click="ui.closeOverlays()">
          <Icon name="x" :size="17" />
        </button>
      </div>

      <div class="mv-pillbar" style="padding: 10px 14px">
        <button
          v-for="s in SCOPES"
          :key="s.key"
          class="mv-pill mv-pill--soft"
          :class="{ 'is-active': scope === s.key }"
          type="button"
          @click="scope = s.key"
        >
          {{ s.label }}
        </button>
        <div class="mv-grow" />
        <span v-if="hasQuery && !loading" class="mv-dim">{{ results.length }} 条结果</span>
      </div>

      <div v-if="error" style="padding: 0 14px 14px">
        <div class="mv-alert mv-alert--danger">
          <Icon name="warn" :size="15" />
          <span>{{ error }}</span>
        </div>
      </div>

      <div v-else-if="!hasQuery" class="mv-center-pad">
        输入关键词开始搜索，支持名称与原始文件名
      </div>

      <div v-else-if="!results.length && !loading" class="mv-center-pad">
        没有匹配的结果
      </div>

      <div v-else style="padding-bottom: 8px">
        <button
          v-for="(item, i) in results"
          :key="item.kind + item.id"
          class="mv-result"
          :class="{ 'is-cursor': i === cursor }"
          type="button"
          @mouseenter="cursor = i"
          @click="open(item)"
        >
          <div class="mv-result__thumb">
            <img v-if="coverOf(item)" :src="coverOf(item)" :alt="item.name" loading="lazy" />
          </div>
          <div class="mv-result__text">
            <div class="mv-result__name">{{ item.name }}</div>
            <div class="mv-result__meta">{{ metaOf(item) }}</div>
          </div>
          <Icon v-if="item.is_favorited" name="star" :size="14" style="color: var(--warn)" />
        </button>
      </div>
    </template>
  </Modal>
</template>
