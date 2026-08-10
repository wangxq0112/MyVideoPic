<script setup>
/**
 * 文件夹选择器 —— 浏览器的 file input 拿不到真实目录路径，
 * 因此由后端 /api/browse/ 逐层列目录（只返回目录名与媒体计数，不读内容）。
 */
import { computed, onMounted, ref } from 'vue'

import Icon from './Icon.vue'
import Modal from './Modal.vue'
import { browseDirectory, errMsg } from '../api/api.js'
import { fmtSize } from '../utils.js'

const props = defineProps({
  // 'video' | 'photo' —— 只影响"此处有 N 个文件"的提示措辞
  kind: { type: String, default: 'video' },
})
const emit = defineEmits(['pick', 'close'])

const loading = ref(false)
const error = ref('')
const current = ref('')
const parent = ref(null)
const drives = ref([])
const dirs = ref([])
const counts = ref({ video: 0, photo: 0 })
const manual = ref('')

const here = computed(() =>
  props.kind === 'video' ? counts.value.video : counts.value.photo)

async function go(path) {
  loading.value = true
  error.value = ''
  try {
    const res = await browseDirectory(path || '')
    current.value = res.data.current || ''
    parent.value = res.data.parent ?? null
    drives.value = res.data.drives || []
    dirs.value = res.data.directories || []
    counts.value = {
      video: res.data.video_files_here || 0,
      photo: res.data.photo_files_here || 0,
    }
  } catch (e) {
    error.value = errMsg(e, '无法读取该目录')
  } finally {
    loading.value = false
  }
}

function confirmManual() {
  const p = manual.value.trim().replace(/^"|"$/g, '')
  if (p) emit('pick', p)
}

onMounted(() => go(''))
</script>

<template>
  <Modal title="选择文件夹" flush @close="emit('close')">
    <div class="mv-crumb">
      <button
        class="mv-icon-btn"
        type="button"
        :disabled="!current"
        title="上一级"
        aria-label="上一级"
        @click="go(parent || '')"
      >
        <Icon name="chevronUp" :size="16" />
      </button>
      <span class="mv-grow">{{ current || '此电脑' }}</span>
      <Icon v-if="loading" name="spinner" :size="15" class="mv-spin" />
    </div>

    <div v-if="error" style="padding: 14px">
      <div class="mv-alert mv-alert--danger">
        <Icon name="warn" :size="15" />
        <span>{{ error }}</span>
      </div>
    </div>

    <div class="mv-dirlist">
      <button
        v-for="d in drives"
        :key="d.path"
        class="mv-dir"
        type="button"
        @click="go(d.path)"
      >
        <Icon name="db" :size="17" />
        <span class="mv-dir__name">{{ d.name }}</span>
        <span v-if="d.free" class="mv-dir__hint">剩余 {{ fmtSize(d.free) }}</span>
      </button>

      <button
        v-for="d in dirs"
        :key="d.path"
        class="mv-dir"
        type="button"
        @click="go(d.path)"
      >
        <Icon name="folder" :size="17" />
        <span class="mv-dir__name">{{ d.name }}</span>
        <Icon name="chevronRight" :size="14" class="mv-dim" />
      </button>

      <div v-if="!loading && current && !dirs.length" class="mv-center-pad">
        此文件夹内没有子文件夹
      </div>
    </div>

    <template #foot>
      <div class="mv-grow" style="min-width: 0">
        <input
          v-model="manual"
          class="mv-input"
          type="text"
          placeholder="或直接粘贴路径，如 D:\Movies"
          @keydown.enter.prevent="confirmManual"
        />
      </div>
      <button
        v-if="manual.trim()"
        class="mv-btn mv-btn--ghost"
        type="button"
        @click="confirmManual"
      >
        使用此路径
      </button>
      <button
        class="mv-btn mv-btn--primary"
        type="button"
        :disabled="!current"
        @click="emit('pick', current)"
      >
        <Icon name="check" :size="15" />
        选择当前文件夹<template v-if="here">（{{ here }} 个文件）</template>
      </button>
    </template>
  </Modal>
</template>
