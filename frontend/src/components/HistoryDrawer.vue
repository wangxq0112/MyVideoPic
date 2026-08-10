<script setup>
/**
 * 历史抽屉 —— 概念图右侧面板，观看记录 / 浏览记录两个标签页。
 *
 * 观看记录带进度条（可"继续观看"），浏览记录只记录看过什么。
 * 历史只是本地记录，删除条目不会碰任何磁盘文件。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import Icon from './Icon.vue'
import { clearHistory, deleteHistoryEntry, errMsg, fetchHistory } from '../api/api.js'
import { useUiStore } from '../stores/ui.js'
import { fmtDuration, fmtRelative, photoCoverUrl, videoCoverUrl } from '../utils.js'

const emit = defineEmits(['photo'])

const router = useRouter()
const ui = useUiStore()

const tab = ref('play')          // 'play' | 'view'
const entries = ref([])
const loading = ref(false)
const error = ref('')
const clearing = ref(false)

const TABS = [
  { key: 'play', label: '观看记录' },
  { key: 'view', label: '浏览记录' },
]

const empty = computed(() => !loading.value && !entries.value.length)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchHistory({ action: tab.value, page_size: 100 })
    entries.value = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
  } catch (e) {
    error.value = errMsg(e, '历史记录加载失败')
    entries.value = []
  } finally {
    loading.value = false
  }
}

watch(tab, load)
onMounted(load)

const targetOf = (entry) => entry.video || entry.photo

function coverOf(entry) {
  const t = targetOf(entry)
  if (!t?.has_cover) return ''
  return entry.video ? videoCoverUrl(t.id) : photoCoverUrl(t.id)
}

function open(entry) {
  const t = targetOf(entry)
  if (!t) return
  ui.closeOverlays()
  if (entry.video) {
    router.push(`/play/${t.id}`)
  } else {
    emit('photo', t)
  }
}

async function removeOne(entry) {
  try {
    await deleteHistoryEntry(entry.id)
    entries.value = entries.value.filter((e) => e.id !== entry.id)
  } catch (e) {
    ui.fail(errMsg(e, '删除记录失败'))
  }
}

async function clearAll() {
  clearing.value = true
  try {
    const res = await clearHistory({ action: tab.value })
    entries.value = []
    ui.ok(`已清空 ${res.data?.deleted ?? 0} 条记录`)
  } catch (e) {
    ui.fail(errMsg(e, '清空失败'))
  } finally {
    clearing.value = false
  }
}

function metaOf(entry) {
  const parts = [fmtRelative(entry.last_seen_at || entry.created_at)]
  if (entry.action === 'play' && entry.position) {
    parts.push(`看到 ${fmtDuration(entry.position)}`)
  }
  if (entry.play_count > 1) parts.push(`${entry.play_count} 次`)
  return parts.filter(Boolean)
}
</script>

<template>
  <Teleport to="body">
    <div class="mv-scrim" @click="ui.closeOverlays()" />
    <aside class="mv-drawer" role="dialog" aria-modal="true" aria-label="历史记录">
      <div class="mv-drawer__head">
        <Icon name="clock" :size="18" class="mv-dim" />
        <div class="mv-drawer__title mv-grow">历史记录</div>
        <button class="mv-icon-btn" type="button" aria-label="关闭" @click="ui.closeOverlays()">
          <Icon name="x" :size="17" />
        </button>
      </div>

      <div class="mv-tabs">
        <button
          v-for="t in TABS"
          :key="t.key"
          class="mv-tab"
          :class="{ 'is-active': tab === t.key }"
          type="button"
          @click="tab = t.key"
        >
          {{ t.label }}
        </button>
      </div>

      <div class="mv-drawer__body">
        <div v-if="loading" class="mv-center-pad">
          <Icon name="spinner" :size="18" class="mv-spin" />
        </div>

        <div v-else-if="error" style="padding: 16px">
          <div class="mv-alert mv-alert--danger">
            <Icon name="warn" :size="15" />
            <span>{{ error }}</span>
          </div>
        </div>

        <div v-else-if="empty" class="mv-empty mv-empty--sm">
          <div class="mv-empty__icon"><Icon name="clock" :size="22" /></div>
          <div class="mv-empty__title">还没有记录</div>
          <p class="mv-empty__desc">
            {{ tab === 'play' ? '播放过的视频会出现在这里' : '看过的图片会出现在这里' }}
          </p>
        </div>

        <div v-else>
          <div v-for="entry in entries" :key="entry.id" class="mv-hist">
            <a
              class="mv-hist__thumb"
              href="#"
              :title="targetOf(entry)?.name"
              @click.prevent="open(entry)"
            >
              <img v-if="coverOf(entry)" :src="coverOf(entry)" :alt="targetOf(entry)?.name" loading="lazy" />
            </a>
            <div class="mv-hist__text">
              <a class="mv-hist__name" href="#" @click.prevent="open(entry)">
                {{ targetOf(entry)?.name || '（记录已失效）' }}
              </a>
              <div class="mv-hist__meta">
                <template v-for="(m, i) in metaOf(entry)" :key="m + i">
                  <span v-if="i">·</span>
                  <span>{{ m }}</span>
                </template>
              </div>
              <div v-if="entry.action === 'play' && entry.percent > 0" class="mv-hist__bar">
                <div class="mv-progress mv-progress--thin">
                  <div
                    class="mv-progress__bar"
                    :class="{ 'mv-progress__bar--ok': entry.percent >= 98 }"
                    :style="{ width: Math.min(entry.percent, 100) + '%' }"
                  />
                </div>
              </div>
            </div>
            <button
              class="mv-hist__del"
              type="button"
              title="删除这条记录"
              aria-label="删除这条记录"
              @click="removeOne(entry)"
            >
              <Icon name="x" :size="14" />
            </button>
          </div>
        </div>
      </div>

      <div class="mv-drawer__foot">
        <span class="mv-dim mv-grow">仅记录在本机，不含任何文件内容</span>
        <button
          class="mv-btn mv-btn--ghost mv-btn--sm"
          type="button"
          :disabled="clearing || !entries.length"
          @click="clearAll"
        >
          <Icon name="broom" :size="14" /> 清空历史记录
        </button>
      </div>
    </aside>
  </Teleport>
</template>
