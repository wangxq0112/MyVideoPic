<script setup>
/**
 * 应用外壳 —— 顶栏 + 路由内容 + 四个全局浮层。
 *
 * 搜索与历史是覆盖层而非路由页面（概念图如此），因此由 ui store
 * 控制显示；重命名/移动/删除对话框与吐司也只在这里挂载一份。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import HistoryDrawer from './components/HistoryDrawer.vue'
import Icon from './components/Icon.vue'
import ImageViewer from './components/ImageViewer.vue'
import MediaDialogs from './components/MediaDialogs.vue'
import SearchOverlay from './components/SearchOverlay.vue'
import Toasts from './components/Toasts.vue'
import {
  errMsg, getScanProgress, pickAndScanLibrary, recordHistory, triggerScan,
} from './api/api.js'
import { useLibrariesStore } from './stores/libraries.js'
import { useOpsStore } from './stores/ops.js'
import { usePhotosStore } from './stores/photos.js'
import { useSettingsStore } from './stores/settings.js'
import { useUiStore } from './stores/ui.js'
import { useVideosStore } from './stores/videos.js'

const route = useRoute()
const ui = useUiStore()
const ops = useOpsStore()
const libs = useLibrariesStore()
const videos = useVideosStore()
const photos = usePhotosStore()
const settings = useSettingsStore()
const selectingLibrary = ref(false)

const NAV = [
  { to: '/videos', label: '视频', icon: 'video' },
  { to: '/images', label: '图片', icon: 'image' },
  { to: '/favorites', label: '收藏夹', icon: 'star' },
]

// 从搜索/历史里点开的单张图片 —— 就地看图，不必先跳到图片页
const quickPhoto = ref(null)

function openPhoto(photo) {
  if (!photo) return
  quickPhoto.value = photo
  recordHistory('photo', photo.id, 'view').catch(() => {})
}

async function toggleFav(photo) {
  try {
    const on = await ops.toggleFav('photo', photo)
    quickPhoto.value = { ...quickPhoto.value, is_favorited: on }
    ui.ok(on ? '已加入收藏' : '已取消收藏')
  } catch (e) {
    ui.fail(errMsg(e, '收藏失败'))
  }
}

function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    ui.openSearch()
  }
}

async function addLibraryFromSystemPicker() {
  if (selectingLibrary.value) return
  selectingLibrary.value = true
  try {
    const res = await pickAndScanLibrary()
    if (res.data?.cancelled) return

    await libs.load(true)
    videos.invalidate()
    photos.invalidate()
    if (route.path.startsWith('/videos')) await videos.load(true)
    if (route.path.startsWith('/images')) await photos.load(true)

    const names = (res.data?.libraries || []).map((lib) => lib.name).join('、')
    const taskId = res.data?.scan?.task_id
    if (taskId) refreshAfterScan(taskId, !!res.data?.scan?.already_running)
    ui.ok(res.data?.scan?.already_running
      ? `${names || '媒体库'} 已添加，等待当前扫描完成后会自动扫描`
      : `${names || '媒体库'} 已添加，正在自动扫描`)
  } catch (e) {
    ui.fail(errMsg(e, '添加媒体库失败'))
  } finally {
    selectingLibrary.value = false
  }
}

async function refreshAfterScan(taskId, startQueuedScan = false) {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    try {
      const status = (await getScanProgress(taskId)).data
      if (!['completed', 'failed', 'cancelled'].includes(status?.status)) continue
      if (startQueuedScan) {
        const queued = await triggerScan()
        if (queued.data?.task_id) {
          refreshAfterScan(queued.data.task_id)
          return
        }
      }
      await libs.load(true)
      videos.invalidate()
      photos.invalidate()
      if (route.path.startsWith('/videos')) await videos.load(true)
      if (route.path.startsWith('/images')) await photos.load(true)
      return
    } catch {
      return
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKey)
  libs.load()
  settings.load()
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="mv-app">
    <header class="mv-topbar">
      <div class="mv-topbar__inner">
        <router-link to="/videos" class="mv-brand">
          <span class="mv-brand__mark"><Icon name="play" :size="13" /></span>
          MyVideoPic
        </router-link>

        <nav class="mv-nav">
          <router-link
            v-for="item in NAV"
            :key="item.to"
            :to="item.to"
            class="mv-pill"
            :class="{ 'is-active': route.path.startsWith(item.to) }"
          >
            <Icon :name="item.icon" :size="15" />
            {{ item.label }}
          </router-link>
        </nav>

        <div class="mv-topbar__spacer" />

        <div class="mv-topbar__tools">
          <button
            class="mv-icon-btn"
            type="button"
            :disabled="selectingLibrary"
            title="添加媒体文件夹"
            aria-label="添加媒体文件夹"
            @click="addLibraryFromSystemPicker"
          >
            <Icon v-if="selectingLibrary" name="spinner" :size="18" class="mv-spin" />
            <Icon v-else name="plus" :size="18" />
          </button>
          <button
            class="mv-icon-btn"
            :class="{ 'is-active': ui.searchOpen }"
            type="button"
            title="搜索 (Ctrl+K)"
            aria-label="搜索"
            @click="ui.openSearch()"
          >
            <Icon name="search" :size="18" />
          </button>
          <button
            class="mv-icon-btn"
            :class="{ 'is-active': ui.historyOpen }"
            type="button"
            title="历史记录"
            aria-label="历史记录"
            @click="ui.openHistory()"
          >
            <Icon name="clock" :size="18" />
          </button>
          <router-link
            to="/settings"
            class="mv-icon-btn"
            :class="{ 'is-active': route.path.startsWith('/settings') }"
            title="设置"
            aria-label="设置"
          >
            <Icon name="settings" :size="18" />
          </router-link>
        </div>
      </div>
    </header>

    <main>
      <router-view />
    </main>

    <SearchOverlay v-if="ui.searchOpen" @photo="openPhoto" />
    <HistoryDrawer v-if="ui.historyOpen" @photo="openPhoto" />

    <ImageViewer
      v-if="quickPhoto"
      :items="[quickPhoto]"
      :index="0"
      @close="quickPhoto = null"
      @fav="toggleFav"
    />

    <MediaDialogs v-if="ops.open" />
    <Toasts />
  </div>
</template>
