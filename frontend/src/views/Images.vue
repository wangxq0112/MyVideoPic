<script setup>
/**
 * 图片页 —— 方图网格 + 全屏查看器。
 *
 * 查看器直接在当前列表里翻页（←/→），因此传整份 list 而不是单张。
 */
import { computed, onMounted, ref, watch } from 'vue'

import Icon from '../components/Icon.vue'
import ImageViewer from '../components/ImageViewer.vue'
import MediaGrid from '../components/MediaGrid.vue'
import MediaPagination from '../components/MediaPagination.vue'
import MediaToolbar from '../components/MediaToolbar.vue'
import { errMsg, recordHistory } from '../api/api.js'
import { useLibrariesStore } from '../stores/libraries.js'
import { useOpsStore } from '../stores/ops.js'
import { usePhotosStore } from '../stores/photos.js'
import { useSettingsStore } from '../stores/settings.js'
import { useUiStore } from '../stores/ui.js'
import { copyText, fmtCount } from '../utils.js'

const photos = usePhotosStore()
const libs = useLibrariesStore()
const ops = useOpsStore()
const ui = useUiStore()
const settings = useSettingsStore()

const viewerIndex = ref(-1)

const ORDERINGS = [
  { key: 'recent', label: '最近添加' },
  { key: 'name', label: '名称 A→Z' },
  { key: 'name_desc', label: '名称 Z→A' },
  { key: 'size', label: '体积最大' },
  { key: 'taken', label: '拍摄时间' },
  { key: 'oldest', label: '最早添加' },
]

const empty = computed(() => (libs.photoLibs.length
  ? { title: '没有符合条件的图片', desc: '试试切换分类，或到设置页重新扫描相册。' }
  : { title: '还没有图片库', desc: '到设置页添加一个图片文件夹，然后手动扫描即可。' }))

onMounted(() => photos.load())

watch(() => ops.revision, () => photos.invalidate())

function open(photo) {
  const idx = photos.list.findIndex((p) => p.id === photo.id)
  if (idx !== -1) viewerIndex.value = idx
}

function markSeen(photo) {
  recordHistory('photo', photo.id, 'view').catch(() => {})
}

async function fav(photo) {
  try {
    const on = await ops.toggleFav('photo', photo)
    ui.ok(on ? '已加入收藏' : '已取消收藏')
  } catch (e) {
    ui.fail(errMsg(e, '收藏失败'))
  }
}

async function action(key, photo) {
  if (key === 'copy') {
    const done = await copyText(photo.absolute_path)
    done ? ui.ok('路径已复制') : ui.fail('复制失败，请手动选择路径')
    return
  }
  ops.start(key, 'photo', photo)
}
</script>

<template>
  <div class="mv-page">
    <div class="mv-page__head">
      <h1 class="mv-page__title">图片</h1>
      <span class="mv-page__meta">
        共 {{ fmtCount(photos.total) }} 张
        <template v-if="photos.isFiltered">（已筛选）</template>
      </span>
    </div>

    <MediaToolbar
      :filters="photos.filters"
      :categories="libs.photoCategories"
      :libraries="libs.photoLibs"
      :orderings="ORDERINGS"
      @change="photos.applyFilters($event)"
    />

    <div v-if="photos.error" class="mv-alert mv-alert--danger" style="margin-bottom: 16px">
      <Icon name="warn" :size="15" />
      <span class="mv-grow">{{ photos.error }}</span>
      <button class="mv-btn mv-btn--ghost mv-btn--sm" type="button" @click="photos.load(true)">
        重试
      </button>
    </div>

    <MediaGrid
      :items="photos.list"
      kind="photo"
      :loading="photos.loading"
      :grid-class="settings.gridClass"
      :show-filename="settings.appearance.show_filename"
      :empty-title="empty.title"
      :empty-desc="empty.desc"
      @open="open"
      @fav="fav"
      @action="action"
    >
      <template #empty-actions>
        <router-link v-if="!libs.photoLibs.length" to="/settings" class="mv-btn mv-btn--primary">
          <Icon name="plus" :size="15" /> 添加图片库
        </router-link>
        <button
          v-else-if="photos.isFiltered"
          class="mv-btn mv-btn--ghost"
          type="button"
          @click="photos.applyFilters({ category: 'all', library: '', favorited: false, q: '' })"
        >
          清除筛选
        </button>
      </template>
    </MediaGrid>

    <MediaPagination
      :current-page="photos.currentPage"
      :total-pages="photos.totalPages"
      :total="photos.total"
      :loading="photos.loading"
      @page="photos.goToPage($event)"
    />

    <ImageViewer
      v-if="viewerIndex >= 0 && photos.list[viewerIndex]"
      :items="photos.list"
      :index="viewerIndex"
      @update:index="viewerIndex = $event"
      @close="viewerIndex = -1"
      @seen="markSeen"
      @fav="fav"
    />
  </div>
</template>
