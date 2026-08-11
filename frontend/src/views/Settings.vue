<script setup>
/**
 * 设置页 —— 左侧栏 + 右内容，六个分区（对齐概念图）。
 *
 * 媒体库、扫描、偏好、维护都在这里；偏好开关即时落库，
 * 不设"保存"按钮，避免改了不生效的困惑。
 */
import { computed, onMounted, reactive, ref } from 'vue'

import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
import ScanPanel from '../components/ScanPanel.vue'
import {
  cleanupOrphans, clearThumbnailCache, errMsg, fetchStats, pickAndScanLibrary,
} from '../api/api.js'
import { useLibrariesStore } from '../stores/libraries.js'
import { usePhotosStore } from '../stores/photos.js'
import { useSettingsStore } from '../stores/settings.js'
import { useUiStore } from '../stores/ui.js'
import { useVideosStore } from '../stores/videos.js'
import { copyText, fmtCount, fmtDurationLong, fmtSize } from '../utils.js'

const libs = useLibrariesStore()
const settings = useSettingsStore()
const ui = useUiStore()
const videos = useVideosStore()
const photos = usePhotosStore()

const SECTIONS = [
  { key: 'libraries', label: '媒体库管理', icon: 'folder' },
  { key: 'scan', label: '扫描与更新', icon: 'refresh' },
  { key: 'playback', label: '播放设置', icon: 'play' },
  { key: 'appearance', label: '外观设置', icon: 'grid' },
  { key: 'storage', label: '存储与维护', icon: 'db' },
  { key: 'about', label: '关于', icon: 'info' },
]

const DENSITIES = [
  { key: 'compact', label: '紧凑' },
  { key: 'comfortable', label: '标准' },
  { key: 'spacious', label: '宽松' },
]

const section = ref('libraries')
const stats = ref(null)
const busy = ref('')
const selectingLibrary = ref(false)

// 新增/编辑媒体库
const form = reactive({
  open: false, id: '', name: '', folder_path: '',
  library_type: 'video', category: '', enabled: true, error: '', saving: false,
})

const editing = computed(() => !!form.id)

function openForm(lib = null) {
  Object.assign(form, {
    open: true,
    id: lib?.id || '',
    name: lib?.name || '',
    folder_path: lib?.folder_path || '',
    library_type: lib?.library_type || 'video',
    category: lib?.category || '',
    enabled: lib ? lib.enabled : true,
    error: '',
    saving: false,
  })
}

async function addLibraryFromSystemPicker() {
  if (selectingLibrary.value) return
  selectingLibrary.value = true
  try {
    const res = await pickAndScanLibrary()
    if (res.data?.cancelled) return
    await libs.load(true)
    invalidateLists()
    const names = (res.data?.libraries || []).map((lib) => lib.name).join('、')
    section.value = 'scan'
    if (res.data?.scan?.already_running) {
      ui.ok(`${names} 已添加；当前扫描任务结束后可再次扫描`)
    } else {
      ui.ok(`${names} 已添加，正在自动扫描`)
    }
  } catch (e) {
    ui.fail(errMsg(e, '添加媒体库失败'))
  } finally {
    selectingLibrary.value = false
  }
}

async function submitForm() {
  const payload = {
    name: form.name.trim(),
    folder_path: form.folder_path.trim(),
    library_type: form.library_type,
    category: form.category.trim(),
    enabled: form.enabled,
  }
  if (!payload.name || !payload.folder_path) {
    form.error = '请填写名称与文件夹路径'
    return
  }
  form.saving = true
  form.error = ''
  try {
    editing.value ? await libs.update(form.id, payload) : await libs.create(payload)
    form.open = false
    invalidateLists()
    ui.ok(editing.value ? '媒体库已更新' : '媒体库已添加，接下来手动扫描一次')
  } catch (e) {
    form.error = errMsg(e, '保存失败')
  } finally {
    form.saving = false
  }
}

async function toggleEnabled(lib) {
  try {
    await libs.update(lib.id, { enabled: !lib.enabled })
    invalidateLists()
  } catch (e) {
    ui.fail(errMsg(e, '操作失败'))
  }
}

// 删除媒体库的两种方式：keepItems=true 只解绑，false 连带清理编目与封面
const confirmDel = reactive({ open: false, lib: null, keep: false, busy: false })

async function doDelete() {
  confirmDel.busy = true
  try {
    await libs.remove(confirmDel.lib.id, confirmDel.keep)
    confirmDel.open = false
    invalidateLists()
    ui.ok('媒体库已移除（磁盘上的文件未改动）')
  } catch (e) {
    ui.fail(errMsg(e, '移除失败'))
  } finally {
    confirmDel.busy = false
  }
}

function invalidateLists() {
  videos.invalidate()
  photos.invalidate()
}

async function loadStats() {
  try {
    stats.value = (await fetchStats()).data
  } catch {
    stats.value = null
  }
}

async function setPref(group, key, value) {
  try {
    await settings.set(group, key, value)
  } catch (e) {
    ui.fail(errMsg(e, '设置保存失败'))
  }
}

async function runMaintenance(kind) {
  busy.value = kind
  try {
    const res = kind === 'cache' ? await clearThumbnailCache() : await cleanupOrphans()
    ui.ok(res.data?.message || '完成')
    invalidateLists()
    await loadStats()
  } catch (e) {
    ui.fail(errMsg(e, '操作失败'))
  } finally {
    busy.value = ''
  }
}

async function copyAppData() {
  const done = await copyText(stats.value?.app_data_dir)
  done ? ui.ok('缓存目录已复制') : ui.fail('复制失败')
}

onMounted(() => {
  libs.load(true)
  settings.load(true)
  loadStats()
})
</script>

<template>
  <div class="mv-page">
    <div class="mv-page__head">
      <h1 class="mv-page__title">设置</h1>
      <span class="mv-page__meta">全部数据保存在本机，不联网</span>
    </div>

    <div class="mv-split">
      <nav class="mv-sidenav">
        <button
          v-for="s in SECTIONS"
          :key="s.key"
          class="mv-sidenav__item"
          :class="{ 'is-active': section === s.key }"
          type="button"
          @click="section = s.key"
        >
          <Icon :name="s.icon" :size="16" />
          {{ s.label }}
        </button>
      </nav>

      <div>
        <section v-if="section === 'libraries'" class="mv-panel">
          <div class="mv-panel__head">
            <div class="mv-grow">
              <div class="mv-panel__title">媒体库</div>
              <div class="mv-panel__desc">
                挂载本地文件夹。原文件只读，不会在其中生成任何隐藏文件。
              </div>
            </div>
            <button
              class="mv-btn mv-btn--primary mv-btn--sm"
              type="button"
              :disabled="selectingLibrary"
              @click="addLibraryFromSystemPicker"
            >
              <Icon :name="selectingLibrary ? 'spinner' : 'folderOpen'" :size="14" :class="{ 'mv-spin': selectingLibrary }" />
              选择媒体文件夹
            </button>
          </div>

          <div v-if="libs.loading && !libs.list.length" class="mv-center-pad">
            <Icon name="spinner" :size="18" class="mv-spin" />
          </div>

          <div v-else-if="!libs.list.length" class="mv-empty mv-empty--sm">
            <div class="mv-empty__icon"><Icon name="folderOpen" :size="22" /></div>
            <div class="mv-empty__title">还没有媒体库</div>
            <p class="mv-empty__desc">选择一个文件夹，应用会识别视频和图片并立即开始扫描。</p>
            <div class="mv-empty__actions">
              <button
                class="mv-btn mv-btn--primary"
                type="button"
                :disabled="selectingLibrary"
                @click="addLibraryFromSystemPicker"
              >
                <Icon :name="selectingLibrary ? 'spinner' : 'folderOpen'" :size="15" :class="{ 'mv-spin': selectingLibrary }" />
                选择媒体文件夹
              </button>
            </div>
          </div>

          <div v-else class="mv-panel__body--flush">
            <div v-for="lib in libs.list" :key="lib.id" class="mv-lib">
              <div
                class="mv-lib__icon"
                :class="[
                  lib.library_type === 'photo' ? 'mv-lib__icon--photo' : '',
                  lib.enabled ? '' : 'mv-lib__icon--off',
                ]"
              >
                <Icon :name="lib.library_type === 'photo' ? 'image' : 'video'" :size="18" />
              </div>
              <div class="mv-lib__text">
                <div class="mv-lib__name">
                  {{ lib.name }}
                  <span v-if="lib.category" class="mv-tag mv-tag--brand">{{ lib.category }}</span>
                  <span v-if="!lib.enabled" class="mv-tag">已停用</span>
                  <span v-if="!lib.path_exists" class="mv-tag mv-tag--danger">路径离线</span>
                </div>
                <div class="mv-lib__path" :title="lib.folder_path">{{ lib.folder_path }}</div>
              </div>
              <div class="mv-lib__actions">
                <span class="mv-dim mv-nums">{{ fmtCount(lib.item_count) }} 项</span>
                <button
                  class="mv-switch"
                  :class="{ 'is-on': lib.enabled }"
                  type="button"
                  :title="lib.enabled ? '停用（扫描时跳过）' : '启用'"
                  :aria-label="lib.enabled ? '停用' : '启用'"
                  @click="toggleEnabled(lib)"
                />
                <button class="mv-icon-btn" type="button" title="编辑" @click="openForm(lib)">
                  <Icon name="pencil" :size="16" />
                </button>
                <button
                  class="mv-icon-btn"
                  type="button"
                  title="移除媒体库"
                  @click="Object.assign(confirmDel, { open: true, lib, keep: false })"
                >
                  <Icon name="trash" :size="16" />
                </button>
              </div>
            </div>
          </div>
        </section>
        <template v-else-if="section === 'scan'">
          <section class="mv-panel">
            <div class="mv-panel__head">
              <div>
                <div class="mv-panel__title">扫描与更新</div>
                <div class="mv-panel__desc">
                  纯手动触发，没有任何后台定时任务。增量扫描只处理有变化的文件。
                </div>
              </div>
            </div>
            <div class="mv-panel__body">
              <ScanPanel />
            </div>
          </section>

          <section class="mv-panel">
            <div class="mv-panel__head">
              <div class="mv-panel__title">扫描选项</div>
            </div>
            <div class="mv-panel__body">
              <div class="mv-row">
                <div class="mv-row__text">
                  <div class="mv-row__title">生成视频封面</div>
                  <div class="mv-row__desc">
                    用 ffmpeg 截取 10% 处的画面存到 .app_data/。关闭后扫描明显更快，
                    卡片显示占位图标。
                  </div>
                </div>
                <button
                  class="mv-switch mv-row__ctl"
                  :class="{ 'is-on': settings.scan.generate_video_thumbnails }"
                  type="button"
                  aria-label="生成视频封面"
                  @click="setPref('scan', 'generate_video_thumbnails', !settings.scan.generate_video_thumbnails)"
                />
              </div>
              <div class="mv-row">
                <div class="mv-row__text">
                  <div class="mv-row__title">跳过隐藏文件与文件夹</div>
                  <div class="mv-row__desc">忽略以 . 开头的条目，避免把缓存目录当成媒体入库。</div>
                </div>
                <button
                  class="mv-switch mv-row__ctl"
                  :class="{ 'is-on': settings.scan.skip_hidden }"
                  type="button"
                  aria-label="跳过隐藏文件"
                  @click="setPref('scan', 'skip_hidden', !settings.scan.skip_hidden)"
                />
              </div>
            </div>
          </section>
        </template>
        <section v-else-if="section === 'playback'" class="mv-panel">
          <div class="mv-panel__head">
            <div class="mv-panel__title">播放设置</div>
          </div>
          <div class="mv-panel__body">
            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">打开后自动播放</div>
                <div class="mv-row__desc">部分浏览器会拦截非静音的自动播放。</div>
              </div>
              <button
                class="mv-switch mv-row__ctl"
                :class="{ 'is-on': settings.playback.autoplay }"
                type="button"
                aria-label="自动播放"
                @click="setPref('playback', 'autoplay', !settings.playback.autoplay)"
              />
            </div>

            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">记住播放位置</div>
                <div class="mv-row__desc">下次打开同一视频时从上次的位置继续。</div>
              </div>
              <button
                class="mv-switch mv-row__ctl"
                :class="{ 'is-on': settings.playback.remember_position }"
                type="button"
                aria-label="记住播放位置"
                @click="setPref('playback', 'remember_position', !settings.playback.remember_position)"
              />
            </div>

            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">默认音量</div>
                <div class="mv-row__desc">{{ settings.playback.default_volume }}%</div>
              </div>
              <div class="mv-row__ctl">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  :value="settings.playback.default_volume"
                  aria-label="默认音量"
                  @change="setPref('playback', 'default_volume', Number($event.target.value))"
                />
              </div>
            </div>

            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">快进/快退步长</div>
                <div class="mv-row__desc">播放页按 ←/→ 时跳转的秒数。</div>
              </div>
              <select
                class="mv-select mv-row__ctl"
                :value="settings.playback.seek_step"
                aria-label="快进步长"
                @change="setPref('playback', 'seek_step', Number($event.target.value))"
              >
                <option v-for="s in [5, 10, 15, 30]" :key="s" :value="s">{{ s }} 秒</option>
              </select>
            </div>

          </div>
        </section>
        <section v-else-if="section === 'appearance'" class="mv-panel">
          <div class="mv-panel__head">
            <div class="mv-panel__title">外观设置</div>
          </div>
          <div class="mv-panel__body">
            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">网格密度</div>
                <div class="mv-row__desc">决定卡片大小与每行数量。</div>
              </div>
              <div class="mv-row__ctl mv-row-flex">
                <button
                  v-for="d in DENSITIES"
                  :key="d.key"
                  class="mv-pill mv-pill--soft"
                  :class="{ 'is-active': settings.appearance.grid_density === d.key }"
                  type="button"
                  @click="setPref('appearance', 'grid_density', d.key)"
                >
                  {{ d.label }}
                </button>
              </div>
            </div>

            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">卡片显示原始文件名</div>
                <div class="mv-row__desc">在名称下方额外显示磁盘上的真实文件名。</div>
              </div>
              <button
                class="mv-switch mv-row__ctl"
                :class="{ 'is-on': settings.appearance.show_filename }"
                type="button"
                aria-label="显示原始文件名"
                @click="setPref('appearance', 'show_filename', !settings.appearance.show_filename)"
              />
            </div>
          </div>
        </section>
        <template v-else-if="section === 'storage'">
          <section class="mv-panel">
            <div class="mv-panel__head">
              <div class="mv-grow">
                <div class="mv-panel__title">媒体统计</div>
              </div>
              <button class="mv-btn mv-btn--ghost mv-btn--sm" type="button" @click="loadStats">
                <Icon name="refresh" :size="14" /> 刷新
              </button>
            </div>
            <div class="mv-panel__body">
              <div v-if="!stats" class="mv-center-pad">
                <Icon name="spinner" :size="18" class="mv-spin" />
              </div>
              <div v-else class="mv-stats">
                <div class="mv-stat">
                  <div class="mv-stat__label"><Icon name="video" :size="13" /> 视频</div>
                  <div class="mv-stat__value">{{ fmtCount(stats.video_count) }}</div>
                  <div class="mv-stat__hint">{{ fmtSize(stats.video_size) }}</div>
                </div>
                <div class="mv-stat">
                  <div class="mv-stat__label"><Icon name="image" :size="13" /> 图片</div>
                  <div class="mv-stat__value">{{ fmtCount(stats.photo_count) }}</div>
                  <div class="mv-stat__hint">{{ fmtSize(stats.photo_size) }}</div>
                </div>
                <div class="mv-stat">
                  <div class="mv-stat__label"><Icon name="clock" :size="13" /> 总时长</div>
                  <div class="mv-stat__value">{{ fmtDurationLong(stats.total_duration) }}</div>
                </div>
                <div class="mv-stat">
                  <div class="mv-stat__label"><Icon name="star" :size="13" /> 收藏</div>
                  <div class="mv-stat__value">{{ fmtCount(stats.favorite_count) }}</div>
                  <div class="mv-stat__hint">{{ fmtCount(stats.history_count) }} 条历史</div>
                </div>
                <div class="mv-stat">
                  <div class="mv-stat__label"><Icon name="image" :size="13" /> 缩略图缓存</div>
                  <div class="mv-stat__value">{{ fmtSize(stats.cache_size) }}</div>
                  <div class="mv-stat__hint">{{ fmtCount(stats.cache_files) }} 个文件</div>
                </div>
                <div class="mv-stat">
                  <div class="mv-stat__label"><Icon name="db" :size="13" /> 数据库</div>
                  <div class="mv-stat__value">{{ fmtSize(stats.db_size) }}</div>
                  <div class="mv-stat__hint">SQLite 单文件</div>
                </div>
              </div>

              <div v-if="stats && !stats.ffmpeg" class="mv-alert mv-alert--warn" style="margin-top: 16px">
                <Icon name="warn" :size="15" />
                <span>
                  未检测到 ffmpeg / ffprobe。视频仍可入库，但没有封面、时长与编码信息，
                  也无法判断浏览器兼容性。把 ffmpeg 加入 PATH 后重新扫描即可补全。
                </span>
              </div>
            </div>
          </section>

          <section class="mv-panel">
            <div class="mv-panel__head">
              <div>
                <div class="mv-panel__title">维护</div>
                <div class="mv-panel__desc">以下操作只影响缓存与编目记录，绝不删除原始媒体文件。</div>
              </div>
            </div>
            <div class="mv-panel__body">
              <div class="mv-row">
                <div class="mv-row__text">
                  <div class="mv-row__title">清空缩略图缓存</div>
                  <div class="mv-row__desc">删除 .app_data/ 内的封面，下次扫描会重新生成。</div>
                </div>
                <button
                  class="mv-btn mv-btn--ghost mv-row__ctl"
                  type="button"
                  :disabled="busy === 'cache'"
                  @click="runMaintenance('cache')"
                >
                  <Icon name="broom" :size="15" :class="{ 'mv-spin': busy === 'cache' }" /> 清空
                </button>
              </div>
              <div class="mv-row">
                <div class="mv-row__text">
                  <div class="mv-row__title">清理失效记录</div>
                  <div class="mv-row__desc">
                    移除物理文件已不存在的编目项。磁盘未连接时请勿执行，
                    否则会误清离线盘上的记录。
                  </div>
                </div>
                <button
                  class="mv-btn mv-btn--ghost mv-row__ctl"
                  type="button"
                  :disabled="busy === 'orphans'"
                  @click="runMaintenance('orphans')"
                >
                  <Icon name="shield" :size="15" :class="{ 'mv-spin': busy === 'orphans' }" /> 清理
                </button>
              </div>
              <div class="mv-row">
                <div class="mv-row__text">
                  <div class="mv-row__title">缓存目录</div>
                  <div class="mv-row__desc mv-mono">{{ stats?.app_data_dir || '—' }}</div>
                </div>
                <button class="mv-btn mv-btn--ghost mv-row__ctl" type="button" @click="copyAppData">
                  <Icon name="copy" :size="15" /> 复制路径
                </button>
              </div>
            </div>
          </section>
        </template>
        <section v-else-if="section === 'about'" class="mv-panel">
          <div class="mv-panel__head">
            <div class="mv-panel__title">关于 MyVideoPic</div>
          </div>
          <div class="mv-panel__body">
            <div class="mv-alert mv-alert--ok">
              <Icon name="shield" :size="15" />
              <span>
                完全离线运行：不请求任何外部接口，不上传任何数据，
                媒体文件始终留在原处。
              </span>
            </div>

            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">零侵入</div>
                <div class="mv-row__desc">
                  只读访问媒体文件夹，不在其中写入任何文件；缩略图统一放在
                  <b class="mv-mono">.app_data/</b>，并以数据库 UUID 命名，
                  所以重命名或移动文件都不会导致封面丢失。
                </div>
              </div>
            </div>
            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">纯手动更新</div>
                <div class="mv-row__desc">
                  没有任何后台定时扫描。文件有变化时，到「扫描与更新」点一次即可。
                </div>
              </div>
            </div>
            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">真实文件操作</div>
                <div class="mv-row__desc">
                  卡片上的重命名 / 移动 / 删除都会作用于磁盘上的真实文件，
                  删除不进回收站，请谨慎确认。
                </div>
              </div>
            </div>
            <div class="mv-row">
              <div class="mv-row__text">
                <div class="mv-row__title">技术栈</div>
                <div class="mv-row__desc">
                  Django + DRF + SQLite / Vue 3 + Vite ·
                  视频走 HTTP 206 分段传输，拖动进度条即时响应。
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- 新增 / 编辑媒体库 -->
    <Modal
      v-if="form.open"
      :title="editing ? '编辑媒体库' : '添加媒体库'"
      @close="form.open = false"
    >
      <div class="mv-formgrid">
        <label class="mv-field">
          <span class="mv-field__label">文件夹路径</span>
          <div class="mv-row-flex">
            <input
              v-model="form.folder_path"
              class="mv-input mv-grow"
              type="text"
              placeholder="D:\Movies"
              spellcheck="false"
            />
          </div>
          <span class="mv-field__hint">必须是本机的绝对路径；文件夹内容只读，不会被修改。</span>
        </label>

        <label class="mv-field">
          <span class="mv-field__label">名称</span>
          <input v-model="form.name" class="mv-input" type="text" placeholder="例如：电影" />
        </label>

        <div class="mv-field">
          <span class="mv-field__label">类型</span>
          <div class="mv-row-flex">
            <button
              class="mv-pill mv-pill--soft"
              :class="{ 'is-active': form.library_type === 'video' }"
              type="button"
              :disabled="editing"
              @click="form.library_type = 'video'"
            >
              <Icon name="video" :size="14" /> 视频库
            </button>
            <button
              class="mv-pill mv-pill--soft"
              :class="{ 'is-active': form.library_type === 'photo' }"
              type="button"
              :disabled="editing"
              @click="form.library_type = 'photo'"
            >
              <Icon name="image" :size="14" /> 图片库
            </button>
          </div>
          <span v-if="editing" class="mv-field__hint">
            类型创建后不可更改（已入库的条目分属不同表）。
          </span>
        </div>

        <label class="mv-field">
          <span class="mv-field__label">分类（可选）</span>
          <input
            v-model="form.category"
            class="mv-input"
            type="text"
            placeholder="例如：电影 / 剧集 / 旅行"
          />
          <span class="mv-field__hint">分类会成为列表页顶部的筛选胶囊。</span>
        </label>

        <div v-if="form.error" class="mv-alert mv-alert--danger">
          <Icon name="warn" :size="15" />
          <span>{{ form.error }}</span>
        </div>
      </div>

      <template #foot>
        <button class="mv-btn mv-btn--ghost" type="button" @click="form.open = false">取消</button>
        <button
          class="mv-btn mv-btn--primary"
          type="button"
          :disabled="form.saving"
          @click="submitForm"
        >
          <Icon v-if="form.saving" name="spinner" :size="15" class="mv-spin" />
          {{ editing ? '保存' : '添加' }}
        </button>
      </template>
    </Modal>

    <!-- 移除媒体库 -->
    <Modal v-if="confirmDel.open" title="移除媒体库" @close="confirmDel.open = false">
      <div class="mv-col" style="gap: 14px">
        <div class="mv-alert mv-alert--info">
          <Icon name="info" :size="15" />
          <span>只移除应用内的挂载配置，<b>磁盘上的文件不会有任何变化</b>。</span>
        </div>
        <div>
          <div class="mv-row__title">{{ confirmDel.lib?.name }}</div>
          <div class="mv-mono mv-dim" style="margin-top: 4px">{{ confirmDel.lib?.folder_path }}</div>
        </div>
        <div class="mv-row">
          <div class="mv-row__text">
            <div class="mv-row__title">保留编目记录</div>
            <div class="mv-row__desc">
              开启则只解绑，条目与封面保留；关闭则同时清理该库的编目与缩略图。
            </div>
          </div>
          <button
            class="mv-switch mv-row__ctl"
            :class="{ 'is-on': confirmDel.keep }"
            type="button"
            aria-label="保留编目记录"
            @click="confirmDel.keep = !confirmDel.keep"
          />
        </div>
      </div>

      <template #foot>
        <button class="mv-btn mv-btn--ghost" type="button" @click="confirmDel.open = false">
          取消
        </button>
        <button
          class="mv-btn mv-btn--danger"
          type="button"
          :disabled="confirmDel.busy"
          @click="doDelete"
        >
          <Icon v-if="confirmDel.busy" name="spinner" :size="15" class="mv-spin" />
          确认移除
        </button>
      </template>
    </Modal>
  </div>
</template>
