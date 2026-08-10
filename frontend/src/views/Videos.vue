<script setup>
/**
 * 视频页 —— 分类胶囊 + 网格 + 无限滚动。
 */
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

import Icon from '../components/Icon.vue'
import MediaGrid from '../components/MediaGrid.vue'
import MediaToolbar from '../components/MediaToolbar.vue'
import { errMsg } from '../api/api.js'
import { useLibrariesStore } from '../stores/libraries.js'
import { useOpsStore } from '../stores/ops.js'
import { useSettingsStore } from '../stores/settings.js'
import { useUiStore } from '../stores/ui.js'
import { useVideosStore } from '../stores/videos.js'
import { copyText, fmtCount } from '../utils.js'

const router = useRouter()
const videos = useVideosStore()
const libs = useLibrariesStore()
const ops = useOpsStore()
const ui = useUiStore()
const settings = useSettingsStore()

const ORDERINGS = [
  { key: 'recent', label: '最近添加' },
  { key: 'name', label: '名称 A→Z' },
  { key: 'name_desc', label: '名称 Z→A' },
  { key: 'size', label: '体积最大' },
  { key: 'duration', label: '时长最长' },
  { key: 'year', label: '年份最新' },
  { key: 'oldest', label: '最早添加' },
]

const empty = computed(() => (libs.videoLibs.length
  ? { title: '没有符合条件的视频', desc: '试试切换分类，或到设置页重新扫描媒体库。' }
  : { title: '还没有视频库', desc: '到设置页添加一个视频文件夹，然后手动扫描即可。' }))

onMounted(() => videos.load())

// 别处（收藏页、搜索浮层）改动过收藏或删过文件时，标记为待刷新
watch(() => ops.revision, () => videos.invalidate())

function open(video) {
  router.push(`/play/${video.id}`)
}

async function fav(video) {
  try {
    const on = await ops.toggleFav('video', video)
    ui.ok(on ? '已加入收藏' : '已取消收藏')
  } catch (e) {
    ui.fail(errMsg(e, '收藏失败'))
  }
}

async function action(key, video) {
  if (key === 'copy') {
    const done = await copyText(video.absolute_path)
    done ? ui.ok('路径已复制') : ui.fail('复制失败，请手动选择路径')
    return
  }
  ops.start(key, 'video', video)
}
</script>

<template>
  <div class="mv-page">
    <div class="mv-page__head">
      <h1 class="mv-page__title">视频</h1>
      <span class="mv-page__meta">
        共 {{ fmtCount(videos.total) }} 个
        <template v-if="videos.isFiltered">（已筛选）</template>
      </span>
    </div>

    <MediaToolbar
      :filters="videos.filters"
      :categories="libs.videoCategories"
      :libraries="libs.videoLibs"
      :orderings="ORDERINGS"
      @change="videos.applyFilters($event)"
    />

    <div v-if="videos.error" class="mv-alert mv-alert--danger" style="margin-bottom: 16px">
      <Icon name="warn" :size="15" />
      <span class="mv-grow">{{ videos.error }}</span>
      <button class="mv-btn mv-btn--ghost mv-btn--sm" type="button" @click="videos.load(true)">
        重试
      </button>
    </div>

    <MediaGrid
      :items="videos.list"
      kind="video"
      :loading="videos.loading"
      :loading-more="videos.loadingMore"
      :has-more="videos.hasMore"
      :grid-class="settings.gridClass"
      :show-filename="settings.appearance.show_filename"
      :empty-title="empty.title"
      :empty-desc="empty.desc"
      @open="open"
      @fav="fav"
      @action="action"
      @more="videos.loadMore()"
    >
      <template #empty-actions>
        <router-link v-if="!libs.videoLibs.length" to="/settings" class="mv-btn mv-btn--primary">
          <Icon name="plus" :size="15" /> 添加视频库
        </router-link>
        <button
          v-else-if="videos.isFiltered"
          class="mv-btn mv-btn--ghost"
          type="button"
          @click="videos.applyFilters({ category: 'all', library: '', favorited: false, q: '' })"
        >
          清除筛选
        </button>
      </template>
    </MediaGrid>
  </div>
</template>
