<script setup>
/**
 * 媒体卡片 —— 视频（16:9 + 时长）与图片（方图）共用。
 *
 * 概念图里的四个元素都在这里：左上分辨率角标、右上收藏星、
 * 右下 ⋮ 菜单、底部继续观看进度条。
 */
import { computed } from 'vue'

import Icon from './Icon.vue'
import LazyCover from './LazyCover.vue'
import MoreMenu from './MoreMenu.vue'
import {
  browserPlayableVideoMime, fmtDuration, fmtSize, photoCoverUrl, videoCoverUrl,
} from '../utils.js'

const props = defineProps({
  item: { type: Object, required: true },
  kind: { type: String, default: 'video' },        // 'video' | 'photo'
  showFilename: { type: Boolean, default: false },
})
const emit = defineEmits(['open', 'fav', 'action'])

const isVideo = computed(() => props.kind === 'video')
const browserPlayable = computed(() =>
  !isVideo.value || !!browserPlayableVideoMime(props.item),
)

const coverUrl = computed(() =>
  props.item.has_cover
    ? (isVideo.value ? videoCoverUrl(props.item.id) : photoCoverUrl(props.item.id))
    : '',
)

const percent = computed(() => {
  const p = props.item.play_percent || 0
  return p > 1 && p < 98 ? p : 0
})

const subtitle = computed(() => {
  const parts = []
  if (props.item.library_name) parts.push(props.item.library_name)
  if (props.item.file_size) parts.push(fmtSize(props.item.file_size))
  if (isVideo.value && props.item.year) parts.push(String(props.item.year))
  return parts
})

const MENU = [
  { key: 'rename', label: '重命名', icon: 'pencil' },
  { key: 'move', label: '移动到…', icon: 'move' },
  { key: 'copy', label: '复制文件路径', icon: 'copy' },
  { key: 'delete', label: '永久删除', icon: 'trash', danger: true },
]
</script>

<template>
  <article class="mv-card">
    <a
      class="mv-card__thumb"
      :class="{ 'mv-card__thumb--square': !isVideo }"
      href="#"
      :title="item.name"
      @click.prevent="emit('open', item)"
    >
      <LazyCover
        :src="coverUrl"
        :alt="item.name"
        :icon="isVideo ? 'film' : 'image'"
      />

      <span v-if="item.resolution_label" class="mv-badge mv-badge--res">
        {{ item.resolution_label }}
      </span>
      <span
        v-if="isVideo && !browserPlayable"
        class="mv-badge mv-badge--warn"
        :style="{ top: item.resolution_label ? '30px' : '6px' }"
        title="浏览器无法直接播放此编码，可用系统默认播放器打开"
      >
        需外部播放
      </span>

      <span v-if="isVideo && item.duration" class="mv-badge mv-badge--duration">
        {{ fmtDuration(item.duration) }}
      </span>

      <span class="mv-card__play">
        <span><Icon :name="isVideo ? 'play' : 'eye'" :size="20" /></span>
      </span>

      <div v-if="percent" class="mv-card__progress">
        <i :style="{ width: percent + '%' }" />
      </div>
    </a>

    <button
      class="mv-card__fav"
      :class="{ 'is-on': item.is_favorited }"
      type="button"
      :title="item.is_favorited ? '取消收藏' : '加入收藏'"
      :aria-label="item.is_favorited ? '取消收藏' : '加入收藏'"
      @click.stop.prevent="emit('fav', item)"
    >
      <Icon name="star" :size="15" />
    </button>

    <div class="mv-card__body">
      <div class="mv-card__text">
        <div class="mv-card__name" :title="item.name">{{ item.name }}</div>
        <div class="mv-card__sub">
          <template v-for="(part, i) in subtitle" :key="part + i">
            <i v-if="i" />
            <span>{{ part }}</span>
          </template>
        </div>
        <div v-if="showFilename" class="mv-card__sub mv-mono mv-truncate" :title="item.original_filename">
          {{ item.original_filename }}
        </div>
      </div>
      <MoreMenu :items="MENU" @select="emit('action', $event, item)" />
    </div>
  </article>
</template>
