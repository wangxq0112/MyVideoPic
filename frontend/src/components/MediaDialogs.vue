<script setup>
/**
 * 重命名 / 移动 / 删除三个对话框 —— 在 App.vue 里只挂载一份。
 *
 * 三者都直接操作磁盘上的真实文件，所以：
 *   * 重命名只让用户改主名，扩展名由后端保留，避免误改成无法识别的格式
 *   * 移动的目标只能是同类型的已有媒体库，跨盘会转为后台复制并显示进度
 *   * 删除是不进回收站的永久删除，必须二次确认
 */
import { computed, nextTick, ref, watch } from 'vue'

import Icon from './Icon.vue'
import Modal from './Modal.vue'
import { useLibrariesStore } from '../stores/libraries.js'
import { useOpsStore } from '../stores/ops.js'
import { useUiStore } from '../stores/ui.js'
import { copyText, fmtEta, fmtSize } from '../utils.js'

const ops = useOpsStore()
const libs = useLibrariesStore()
const ui = useUiStore()

const nameInput = ref(null)
const draft = ref('')

const item = computed(() => ops.item)
const kindLabel = computed(() => (ops.kind === 'video' ? '视频' : '图片'))

/** 去掉扩展名 —— 后端只接收主名 */
const baseName = (filename) => (filename || '').replace(/\.[^./\\]+$/, '')

const ext = computed(() => {
  const m = /\.[^./\\]+$/.exec(item.value?.original_filename || '')
  return m ? m[0] : ''
})

/** 只列出同类型、且路径当前可访问的库（目标磁盘掉线时移动必然失败） */
const targets = computed(() => {
  const all = ops.kind === 'video' ? libs.videoLibs : libs.photoLibs
  return all.filter((l) => l.id !== item.value?.library_id)
})

// immediate 是必须的：本组件在 ops.mode 已被赋值之后才挂载，
// 不加就永远等不到那次变化，输入框会是空的。
watch(() => ops.mode, async (mode) => {
  if (mode !== 'rename') return
  draft.value = baseName(item.value?.original_filename) || item.value?.name || ''
  await nextTick()
  nameInput.value?.focus()
  nameInput.value?.select()
}, { immediate: true })

async function submitRename() {
  const next = draft.value.trim()
  if (!next || next === baseName(item.value?.original_filename)) {
    ops.close()
    return
  }
  try {
    await ops.rename(next)
    ui.ok('已重命名')
    ops.close()
  } catch { /* 错误已写入 ops.error，就地显示 */ }
}

async function submitMove(libraryId) {
  try {
    const res = await ops.move(libraryId)
    ui.ok(res?.status === 'completed' ? '跨盘移动完成' : '已移动')
    ops.close()
  } catch { /* 同上 */ }
}

async function submitDelete() {
  try {
    const res = await ops.remove()
    ui.ok(res?.warning || '已永久删除')
    ops.close()
  } catch { /* 同上 */ }
}

async function copyPath() {
  const done = await copyText(item.value?.absolute_path)
  done ? ui.ok('路径已复制') : ui.fail('复制失败，请手动选择路径')
}
</script>

<template>
  <!-- ── 重命名 ─────────────────────────────────────── -->
  <Modal
    v-if="ops.mode === 'rename'"
    title="重命名"
    :closable="!ops.busy"
    @close="ops.close()"
  >
    <div class="mv-formgrid">
      <label class="mv-field">
        <span class="mv-field__label">新名称</span>
        <input
          ref="nameInput"
          v-model="draft"
          class="mv-input"
          type="text"
          maxlength="200"
          placeholder="请输入新名称"
          @keydown.enter.prevent="submitRename"
        />
        <span class="mv-field__hint">
          扩展名 <b class="mv-mono">{{ ext || '（无）' }}</b> 会保持不变；
          磁盘上的文件会被真实重命名，封面不会丢失。
        </span>
      </label>

      <div v-if="ops.error" class="mv-alert mv-alert--danger">
        <Icon name="warn" :size="15" />
        <span>{{ ops.error }}</span>
      </div>
    </div>

    <template #foot>
      <button class="mv-btn mv-btn--ghost" type="button" :disabled="ops.busy" @click="ops.close()">
        取消
      </button>
      <button
        class="mv-btn mv-btn--primary"
        type="button"
        :disabled="ops.busy || !draft.trim()"
        @click="submitRename"
      >
        <Icon v-if="ops.busy" name="spinner" :size="15" class="mv-spin" />
        确定
      </button>
    </template>
  </Modal>

  <!-- ── 移动 ───────────────────────────────────────── -->
  <Modal
    v-else-if="ops.mode === 'move'"
    :title="`移动${kindLabel}到…`"
    :closable="!ops.busy"
    @close="ops.close()"
  >
    <div v-if="ops.moveTask" class="mv-col">
      <div class="mv-row-flex">
        <Icon name="spinner" :size="15" class="mv-spin" />
        <span class="mv-grow">正在跨盘复制，请勿关闭页面…</span>
        <b class="mv-nums">{{ (ops.moveTask.percent ?? 0).toFixed(1) }}%</b>
      </div>
      <div class="mv-progress">
        <div class="mv-progress__bar" :style="{ width: (ops.moveTask.percent ?? 0) + '%' }" />
      </div>
      <div class="mv-dim">
        {{ fmtSize(ops.moveTask.copied_bytes) }} / {{ fmtSize(ops.moveTask.total_bytes) }}
        · 剩余 {{ fmtEta(ops.moveTask.eta_seconds) }}
      </div>
      <div class="mv-alert mv-alert--info">
        <Icon name="info" :size="15" />
        <span>跨磁盘移动需要完整复制一遍内容，源文件会在写入成功后才删除。</span>
      </div>
    </div>

    <template v-else>
      <div v-if="!targets.length" class="mv-empty mv-empty--sm">
        <div class="mv-empty__icon"><Icon name="folder" :size="22" /></div>
        <div class="mv-empty__title">没有可选的目标</div>
        <p class="mv-empty__desc">
          需要至少两个同类型媒体库才能移动，请先到设置页添加文件夹。
        </p>
      </div>

      <div v-else class="mv-col">
        <button
          v-for="lib in targets"
          :key="lib.id"
          class="mv-dir"
          type="button"
          :disabled="!lib.path_exists"
          @click="submitMove(lib.id)"
        >
          <Icon name="folder" :size="17" />
          <span class="mv-dir__name">
            {{ lib.name }}
            <span class="mv-dim mv-mono">{{ lib.folder_path }}</span>
          </span>
          <span v-if="!lib.path_exists" class="mv-tag mv-tag--danger">离线</span>
        </button>
      </div>

      <div v-if="ops.error" class="mv-alert mv-alert--danger" style="margin-top: 14px">
        <Icon name="warn" :size="15" />
        <span>{{ ops.error }}</span>
      </div>
    </template>
  </Modal>

  <!-- ── 删除 ───────────────────────────────────────── -->
  <Modal
    v-else-if="ops.mode === 'delete'"
    title="永久删除"
    :closable="!ops.busy"
    @close="ops.close()"
  >
    <div class="mv-col">
      <div class="mv-alert mv-alert--danger">
        <Icon name="warn" :size="15" />
        <span>
          将从磁盘永久删除该{{ kindLabel }}，<b>不进回收站、无法恢复</b>。
        </span>
      </div>
      <div>
        <div class="mv-row__title">{{ item?.name }}</div>
        <div class="mv-mono mv-dim" style="margin-top: 4px; word-break: break-all">
          {{ item?.absolute_path }}
        </div>
      </div>
      <div v-if="ops.error" class="mv-alert mv-alert--danger">
        <Icon name="warn" :size="15" />
        <span>{{ ops.error }}</span>
      </div>
    </div>

    <template #foot>
      <button class="mv-btn mv-btn--ghost" type="button" @click="copyPath">
        <Icon name="copy" :size="15" /> 复制路径
      </button>
      <div class="mv-grow" />
      <button class="mv-btn mv-btn--ghost" type="button" :disabled="ops.busy" @click="ops.close()">
        取消
      </button>
      <button class="mv-btn mv-btn--danger" type="button" :disabled="ops.busy" @click="submitDelete">
        <Icon v-if="ops.busy" name="spinner" :size="15" class="mv-spin" />
        确认删除
      </button>
    </template>
  </Modal>
</template>
