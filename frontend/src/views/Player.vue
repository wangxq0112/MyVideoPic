<script setup>
/**
 * 播放页。
 *
 * 三个要点：
 *   1. 视频流走 /api/stream/video/<uuid>/ —— 支持 206 Range，拖进度才有效，
 *      同时 URL 里不出现磁盘路径。
 *   2. 编码不被浏览器支持时不硬播，直接给"复制路径 / 系统默认播放器"两条出路。
 *   3. 播放进度每 5 秒上报一次，离开页面时再补一次，下次进来可续播。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import Icon from '../components/Icon.vue'
import {
  errMsg, fetchVideo, openVideoWithDefaultPlayer, recordHistory, saveProgress,
} from '../api/api.js'
import { useOpsStore } from '../stores/ops.js'
import { useSettingsStore } from '../stores/settings.js'
import { useUiStore } from '../stores/ui.js'
import { useVideosStore } from '../stores/videos.js'
import {
  browserPlayableVideoMime, copyText, fmtDate, fmtDuration, fmtSize,
  parentDir, videoStreamUrl,
} from '../utils.js'

const route = useRoute()
const router = useRouter()
const videos = useVideosStore()
const ops = useOpsStore()
const ui = useUiStore()
const settings = useSettingsStore()

const el = ref(null)
const video = ref(null)
const loading = ref(true)
const error = ref('')
const resumed = ref(0)
const playbackFailed = ref(false)

let timer = null
let lastSent = 0

const id = computed(() => route.params.id)
const src = computed(() => (video.value ? videoStreamUrl(video.value.id) : ''))
const playableMime = computed(() => browserPlayableVideoMime(video.value))
const playable = computed(() => !!playableMime.value && !playbackFailed.value)
const missing = computed(() => video.value?.file_exists === false)

const meta = computed(() => {
  const v = video.value
  if (!v) return []
  const parts = []
  if (v.duration) parts.push(fmtDuration(v.duration))
  if (v.width && v.height) parts.push(`${v.width} × ${v.height}`)
  if (v.file_size) parts.push(fmtSize(v.file_size))
  if (v.video_codec) parts.push(`${v.video_codec}${v.audio_codec ? ' / ' + v.audio_codec : ''}`)
  if (v.library_name) parts.push(v.library_name)
  if (v.created_at) parts.push(`入库 ${fmtDate(v.created_at)}`)
  return parts
})

async function load() {
  // 从网格点进来时列表里已有这条数据，先渲染出来避免白屏一闪
  const cached = videos.findById(id.value)
  if (cached) video.value = cached
  loading.value = !cached
  error.value = ''
  playbackFailed.value = false
  try {
    const res = await fetchVideo(id.value)
    video.value = res.data
    recordHistory('video', id.value, 'play').catch(() => {})
  } catch (e) {
    error.value = errMsg(e, '视频信息加载失败')
    video.value = null
  } finally {
    loading.value = false
  }
}

/** 上报进度；已看到结尾就归零，避免下次一进来就跳到片尾 */
function report(force = false) {
  const node = el.value
  if (!node || !video.value) return
  const pos = node.currentTime || 0
  const dur = node.duration || video.value.duration || 0
  if (!force && Math.abs(pos - lastSent) < 3) return
  lastSent = pos
  const finished = dur > 0 && pos / dur > 0.98
  saveProgress(video.value.id, finished ? 0 : Math.floor(pos)).catch(() => {})
}

function onLoaded() {
  const node = el.value
  if (!node) return
  node.volume = Math.min(Math.max(settings.playback.default_volume / 100, 0), 1)

  const pos = video.value?.play_position || 0
  const dur = node.duration || video.value?.duration || 0
  // 只在"看过一段但还没看完"时续播
  if (settings.playback.remember_position && pos > 5 && (!dur || pos < dur - 10)) {
    node.currentTime = pos
    resumed.value = pos
  }
  if (settings.playback.autoplay) node.play().catch(() => {})
}

/** ←/→ 按设置里的步长跳转，空格播放/暂停 */
function onKey(e) {
  const node = el.value
  if (!node || !playable.value) return
  const tag = e.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable) return

  const step = settings.playback.seek_step || 10
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    node.currentTime = Math.max(node.currentTime - step, 0)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    node.currentTime = node.currentTime + step
  } else if (e.key === ' ') {
    e.preventDefault()
    node.paused ? node.play().catch(() => {}) : node.pause()
  }
}

async function copyPath() {
  const done = await copyText(video.value?.absolute_path)
  done ? ui.ok('路径已复制，可粘贴到本地播放器') : ui.fail('复制失败，请手动选择路径')
}

async function copyFolder() {
  const done = await copyText(parentDir(video.value?.absolute_path))
  done ? ui.ok('文件夹路径已复制') : ui.fail('复制失败')
}

/** canPlayType 通过后仍可能因具体文件损坏、编码级别等原因失败。 */
function onPlaybackError() {
  playbackFailed.value = true
}

async function openWithDefaultPlayer() {
  if (!video.value) return
  try {
    await openVideoWithDefaultPlayer(video.value.id)
    ui.ok('已交给系统默认播放器打开')
  } catch (e) {
    ui.fail(errMsg(e, '无法调用系统默认播放器'))
  }
}

async function fav() {
  try {
    const on = await ops.toggleFav('video', video.value)
    video.value = { ...video.value, is_favorited: on }
    ui.ok(on ? '已加入收藏' : '已取消收藏')
  } catch (e) {
    ui.fail(errMsg(e, '收藏失败'))
  }
}

async function rename() {
  ops.start('rename', 'video', video.value)
}

/** 本视频被删掉了就退出播放页，否则（重命名/移动后）重新取一次信息 */
watch(() => ops.removedId, (id) => {
  if (id && id === video.value?.id) router.replace('/videos')
})

watch(() => ops.revision, () => {
  if (video.value && ops.removedId !== video.value.id) load()
})

watch(id, load)

onMounted(() => {
  load()
  document.addEventListener('keydown', onKey)
  timer = setInterval(() => report(), 5000)
})

onBeforeUnmount(() => {
  report(true)
  document.removeEventListener('keydown', onKey)
  clearInterval(timer)
})
</script>

<template>
  <div class="mv-player">
    <div class="mv-row-flex" style="margin-bottom: 14px">
      <button class="mv-btn mv-btn--ghost mv-btn--sm" type="button" @click="router.back()">
        <Icon name="chevronLeft" :size="14" /> 返回
      </button>
      <router-link to="/videos" class="mv-btn mv-btn--ghost mv-btn--sm">视频列表</router-link>
    </div>

    <div v-if="loading" class="mv-player__stage">
      <Icon name="spinner" :size="26" class="mv-spin mv-dim" />
    </div>

    <div v-else-if="error" class="mv-player__stage">
      <div class="mv-fallback">
        <div>
          <div class="mv-empty__icon" style="margin-inline: auto">
            <Icon name="warn" :size="24" />
          </div>
          <div class="mv-empty__title">{{ error }}</div>
          <div class="mv-empty__actions">
            <button class="mv-btn mv-btn--ghost" type="button" @click="load">重试</button>
          </div>
        </div>
      </div>
    </div>

    <template v-else-if="video">
      <div class="mv-player__stage">
        <!-- 文件不在了：先提示，不要让 <video> 反复请求 404 -->
        <div v-if="missing" class="mv-fallback">
          <div>
            <div class="mv-empty__icon" style="margin-inline: auto">
              <Icon name="warn" :size="24" />
            </div>
            <div class="mv-empty__title">文件不存在</div>
            <p class="mv-empty__desc">
              可能已被移动、删除，或所在磁盘未连接。<br />
              重新扫描后编目会自动更新。
            </p>
            <div class="mv-empty__actions">
              <button class="mv-btn mv-btn--ghost" type="button" @click="copyPath">
                <Icon name="copy" :size="15" /> 复制原路径
              </button>
            </div>
          </div>
        </div>

        <!-- 当前浏览器无法播放：交给 Windows 的默认文件关联处理 -->
        <div v-else-if="!playable" class="mv-fallback">
          <div>
            <div class="mv-empty__icon" style="margin-inline: auto">
              <Icon name="film" :size="24" />
            </div>
            <div class="mv-empty__title">当前浏览器无法直接播放此视频</div>
            <p class="mv-empty__desc">
              {{ video.container_format || '该封装' }} /
              {{ video.video_codec || '未知编码' }} 在当前浏览器中不可用。<br />
              可直接用系统默认播放器打开，或复制路径手动处理。
            </p>
            <div class="mv-empty__actions">
              <button
                class="mv-btn mv-btn--primary"
                type="button"
                @click="openWithDefaultPlayer"
              >
                <Icon name="external" :size="15" /> 用系统默认播放器打开
              </button>
              <button class="mv-btn mv-btn--ghost" type="button" @click="copyPath">
                <Icon name="copy" :size="15" /> 复制文件路径
              </button>
            </div>
          </div>
        </div>

        <video
          v-else
          ref="el"
          controls
          preload="metadata"
          playsinline
          @loadedmetadata="onLoaded"
          @timeupdate="report()"
          @pause="report(true)"
          @ended="report(true)"
          @error="onPlaybackError"
        >
          <source :src="src" :type="playableMime" @error="onPlaybackError" />
        </video>
      </div>

      <h1 class="mv-player__title">{{ video.name }}</h1>

      <div class="mv-player__meta">
        <template v-for="(m, i) in meta" :key="m + i">
          <span v-if="i">·</span>
          <span>{{ m }}</span>
        </template>
        <span v-if="!playable" class="mv-tag mv-tag--warn">需外部播放</span>
      </div>

      <div v-if="resumed" class="mv-alert mv-alert--info" style="margin-top: 14px">
        <Icon name="info" :size="15" />
        <span>已从上次的 {{ fmtDuration(resumed) }} 继续播放。</span>
      </div>

      <div class="mv-player__actions">
        <button class="mv-btn mv-btn--ghost" type="button" @click="fav">
          <Icon name="star" :size="15" :style="video.is_favorited ? 'color: var(--warn)' : ''" />
          {{ video.is_favorited ? '取消收藏' : '加入收藏' }}
        </button>
        <button class="mv-btn mv-btn--ghost" type="button" @click="rename">
          <Icon name="pencil" :size="15" /> 重命名
        </button>
        <button class="mv-btn mv-btn--ghost" type="button" @click="copyPath">
          <Icon name="copy" :size="15" /> 复制文件路径
        </button>
        <button class="mv-btn mv-btn--ghost" type="button" @click="copyFolder">
          <Icon name="folder" :size="15" /> 复制所在文件夹
        </button>
        <button
          v-if="playable && !missing"
          class="mv-btn mv-btn--ghost"
          type="button"
          @click="openWithDefaultPlayer"
        >
          <Icon name="external" :size="15" /> 用系统默认播放器打开
        </button>
      </div>

      <div class="mv-hr" />
      <div class="mv-mono mv-dim" style="word-break: break-all">{{ video.absolute_path }}</div>
      <p class="mv-dim" style="margin-top: 10px; font-size: 12px">
        快捷键：空格 播放/暂停，←/→ 快退/快进 {{ settings.playback.seek_step }} 秒。
      </p>
    </template>
  </div>
</template>
