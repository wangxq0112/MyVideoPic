<script setup>
/**
 * 扫描面板 —— 概念图里的「扫描与更新」区域。
 *
 * 空闲时显示上次扫描记录与开始按钮；运行时显示阶段、百分比、
 * 当前文件、四个计数与预计剩余时间，并提供取消。
 */
import { computed, onMounted } from 'vue'

import Icon from './Icon.vue'
import { useScanStore } from '../stores/scan.js'
import { fmtCount, fmtDate, fmtEta } from '../utils.js'

const scan = useScanStore()

const t = computed(() => scan.task)

const finishedTag = computed(() => {
  const s = t.value?.status
  if (s === 'completed') return { cls: 'mv-tag--ok', text: '已完成' }
  if (s === 'cancelled') return { cls: 'mv-tag--warn', text: '已取消' }
  if (s === 'failed') return { cls: 'mv-tag--danger', text: '失败' }
  return null
})

const lastTag = computed(() => {
  const s = scan.lastScan?.status
  if (s === 'completed') return 'mv-tag--ok'
  if (s === 'cancelled') return 'mv-tag--warn'
  if (s === 'failed') return 'mv-tag--danger'
  return ''
})

onMounted(() => scan.refreshStatus())
</script>

<template>
  <div class="mv-col" style="gap: 14px">
    <!-- 运行中 / 刚结束 -->
    <div v-if="t" class="mv-scan">
      <div class="mv-scan__top">
        <div class="mv-scan__stage">
          <Icon
            :name="scan.running ? 'spinner' : (finishedTag ? 'check' : 'refresh')"
            :size="15"
            :class="{ 'mv-spin': scan.running }"
          />
          {{ t.stage_label || '扫描中' }}
        </div>
        <span v-if="finishedTag" class="mv-tag" :class="finishedTag.cls">
          {{ finishedTag.text }}
        </span>
        <div class="mv-scan__pct">
          {{ scan.indeterminate ? '—' : scan.percent.toFixed(1) + '%' }}
        </div>
      </div>

      <div class="mv-progress">
        <div
          class="mv-progress__bar"
          :class="{
            'mv-progress__bar--idle': scan.indeterminate,
            'mv-progress__bar--ok': t.status === 'completed',
            'mv-progress__bar--danger': t.status === 'failed',
          }"
          :style="{ width: scan.percent + '%' }"
        />
      </div>

      <div class="mv-scan__file">{{ t.current_file || t.message }}</div>

      <div class="mv-scan__counts">
        <span>进度 <b>{{ fmtCount(t.progress) }}</b> / {{ fmtCount(t.total) }}</span>
        <span>新增 <b>{{ fmtCount(t.added) }}</b></span>
        <span>更新 <b>{{ fmtCount(t.updated) }}</b></span>
        <span>移除 <b>{{ fmtCount(t.removed) }}</b></span>
        <span v-if="t.failed">失败 <b>{{ fmtCount(t.failed) }}</b></span>
        <span v-if="scan.running && t.total">剩余 <b>{{ fmtEta(t.eta_seconds) }}</b></span>
        <div class="mv-grow" />
        <button
          v-if="scan.running"
          class="mv-btn mv-btn--danger mv-btn--sm"
          type="button"
          :disabled="t.cancel_requested"
          @click="scan.cancel()"
        >
          <Icon name="stop" :size="14" />
          {{ t.cancel_requested ? '正在停止…' : '取消扫描' }}
        </button>
        <button v-else class="mv-btn mv-btn--ghost mv-btn--sm" type="button" @click="scan.dismiss()">
          收起
        </button>
      </div>

      <!-- 离线库提示：这些库本次整体跳过，编目未被清理 -->
      <div v-if="t.skipped_libraries?.length" class="mv-alert mv-alert--warn" style="margin-top: 12px">
        <Icon name="warn" :size="15" />
        <span>
          以下媒体库本次无法访问，已整体跳过（其编目与封面均未改动）：
          <template v-for="(s, i) in t.skipped_libraries" :key="s.path">
            <template v-if="i">、</template>{{ s.name }}（{{ s.reason }}）
          </template>
        </span>
      </div>
    </div>

    <!-- 空闲：上次扫描记录 -->
    <div v-else-if="scan.lastScan" class="mv-scan">
      <div class="mv-scan__top">
        <div class="mv-scan__stage">
          <Icon name="clock" :size="15" />上次扫描记录
        </div>
        <span class="mv-tag" :class="lastTag">{{ scan.lastScan.message || scan.lastScan.status }}</span>
      </div>
      <div class="mv-scan__counts">
        <span>{{ fmtDate(scan.lastScan.started_at) }}</span>
        <span>耗时 <b>{{ fmtCount(scan.lastScan.duration_seconds) }}</b> 秒</span>
        <span>共 <b>{{ fmtCount(scan.lastScan.total_files) }}</b> 个文件</span>
        <span>新增 <b>{{ fmtCount(scan.lastScan.added) }}</b></span>
        <span>更新 <b>{{ fmtCount(scan.lastScan.updated) }}</b></span>
        <span>移除 <b>{{ fmtCount(scan.lastScan.removed) }}</b></span>
      </div>
    </div>

    <div v-if="scan.error" class="mv-alert mv-alert--danger">
      <Icon name="warn" :size="15" />
      <span>{{ scan.error }}</span>
    </div>

    <div class="mv-row-flex">
      <button
        class="mv-btn mv-btn--primary"
        type="button"
        :disabled="scan.running || scan.starting"
        @click="scan.start()"
      >
        <Icon name="refresh" :size="15" :class="{ 'mv-spin': scan.starting }" />
        {{ scan.running ? '扫描进行中…' : '开始扫描' }}
      </button>
      <span class="mv-dim">
        只扫描已启用的媒体库；原文件只读，缩略图写入 .app_data/。
      </span>
    </div>
  </div>
</template>
