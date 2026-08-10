<script setup>
/**
 * 收藏夹 —— 视频与图片两个标签页。
 *
 * 数据源是 /api/favorites/（每行内嵌一个视频或图片），
 * 任何地方改了收藏/删了文件都会让 ops.revision 变化，这里随之重拉。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import Icon from '../components/Icon.vue'
import ImageViewer from '../components/ImageViewer.vue'
import MediaGrid from '../components/MediaGrid.vue'
import { errMsg, fetchFavorites, recordHistory } from '../api/api.js'
import { useOpsStore } from '../stores/ops.js'
import { useSettingsStore } from '../stores/settings.js'
import { useUiStore } from '../stores/ui.js'
import { copyText, fmtCount } from '../utils.js'

const router = useRouter()
const ops = useOpsStore()
const ui = useUiStore()
const settings = useSettingsStore()

const tab = ref('video')
const items = ref([])
const loading = ref(false)
const error = ref('')
const viewerIndex = ref(-1)

const TABS = [
  { key: 'video', label: '视频', icon: 'video' },
  { key: 'photo', label: '图片', icon: 'image' },
]

const isVideo = computed(() => tab.value === 'video')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchFavorites({ content_type: tab.value, page_size: 100 })
    const rows = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
    // 内嵌对象可能为空（记录被清理但收藏行还在），过滤掉避免渲染空卡片
    items.value = rows
      .map((row) => row.video || row.photo)
      .filter(Boolean)
      .map((m) => ({ ...m, is_favorited: true }))
  } catch (e) {
    error.value = errMsg(e, '收藏夹加载失败')
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(tab, () => {
  viewerIndex.value = -1
  load()
})
watch(() => ops.revision, load)
onMounted(load)

function open(item) {
  if (isVideo.value) {
    router.push(`/play/${item.id}`)
    return
  }
  const idx = items.value.findIndex((p) => p.id === item.id)
  if (idx !== -1) viewerIndex.value = idx
}

function markSeen(photo) {
  recordHistory('photo', photo.id, 'view').catch(() => {})
}

async function fav(item) {
  try {
    await ops.toggleFav(tab.value, item)
    // 取消收藏后本行就不该留在收藏夹里
    items.value = items.value.filter((i) => i.id !== item.id)
    if (viewerIndex.value >= items.value.length) viewerIndex.value = -1
    ui.ok('已取消收藏')
  } catch (e) {
    ui.fail(errMsg(e, '操作失败'))
  }
}

async function action(key, item) {
  if (key === 'copy') {
    const done = await copyText(item.absolute_path)
    done ? ui.ok('路径已复制') : ui.fail('复制失败，请手动选择路径')
    return
  }
  ops.start(key, tab.value, item)
}
</script>

<template>
  <div class="mv-page">
    <div class="mv-page__head">
      <h1 class="mv-page__title">收藏夹</h1>
      <span class="mv-page__meta">共 {{ fmtCount(items.length) }} 项</span>
    </div>

    <div class="mv-toolbar">
      <div class="mv-pillbar mv-toolbar__grow">
        <button
          v-for="t in TABS"
          :key="t.key"
          class="mv-pill mv-pill--soft"
          :class="{ 'is-active': tab === t.key }"
          type="button"
          @click="tab = t.key"
        >
          <Icon :name="t.icon" :size="14" /> {{ t.label }}
        </button>
      </div>
      <button class="mv-btn mv-btn--ghost mv-btn--sm" type="button" @click="load">
        <Icon name="refresh" :size="14" :class="{ 'mv-spin': loading }" /> 刷新
      </button>
    </div>

    <div v-if="error" class="mv-alert mv-alert--danger" style="margin-bottom: 16px">
      <Icon name="warn" :size="15" />
      <span>{{ error }}</span>
    </div>

    <MediaGrid
      :items="items"
      :kind="tab"
      :loading="loading"
      :grid-class="settings.gridClass"
      :show-filename="settings.appearance.show_filename"
      empty-title="收藏夹是空的"
      :empty-desc="`在${isVideo ? '视频' : '图片'}页把鼠标移到卡片上，点右上角的星标即可收藏。`"
      @open="open"
      @fav="fav"
      @action="action"
    >
      <template #empty-actions>
        <router-link :to="isVideo ? '/videos' : '/images'" class="mv-btn mv-btn--ghost">
          去挑几个
        </router-link>
      </template>
    </MediaGrid>

    <ImageViewer
      v-if="!isVideo && viewerIndex >= 0 && items[viewerIndex]"
      :items="items"
      :index="viewerIndex"
      @update:index="viewerIndex = $event"
      @close="viewerIndex = -1"
      @seen="markSeen"
      @fav="fav"
    />
  </div>
</template>
