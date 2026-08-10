<script setup>
/**
 * 媒体网格 —— 首屏骨架、空状态、无限滚动三件事都在这里收口，
 * 视频页/图片页/收藏页只负责给数据。
 */
import { computed } from 'vue'

import Icon from './Icon.vue'
import MediaCard from './MediaCard.vue'
import { useInfiniteScroll } from '../composables/useInView.js'

const props = defineProps({
  items: { type: Array, default: () => [] },
  kind: { type: String, default: 'video' },
  loading: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: false },
  gridClass: { type: String, default: '' },
  showFilename: { type: Boolean, default: false },
  emptyTitle: { type: String, default: '这里还没有内容' },
  emptyDesc: { type: String, default: '' },
})
const emit = defineEmits(['open', 'fav', 'action', 'more'])

const { sentinel } = useInfiniteScroll(() => {
  if (props.hasMore && !props.loadingMore && !props.loading) emit('more')
})

const isPhoto = computed(() => props.kind === 'photo')
const classes = computed(() => [
  'mv-grid',
  isPhoto.value ? 'mv-grid--photo' : '',
  props.gridClass,
])
</script>

<template>
  <!-- 首屏骨架：格子数量与常见首屏可见数接近，避免撑出多余滚动条 -->
  <div v-if="loading && !items.length" :class="classes">
    <div
      v-for="n in 12"
      :key="n"
      class="mv-skeleton"
      :class="isPhoto ? 'mv-skeleton--square' : 'mv-skeleton--card'"
    />
  </div>

  <div v-else-if="!items.length" class="mv-empty">
    <div class="mv-empty__icon">
      <Icon :name="isPhoto ? 'image' : 'film'" :size="26" />
    </div>
    <div class="mv-empty__title">{{ emptyTitle }}</div>
    <p v-if="emptyDesc" class="mv-empty__desc">{{ emptyDesc }}</p>
    <div class="mv-empty__actions"><slot name="empty-actions" /></div>
  </div>

  <template v-else>
    <div :class="classes">
      <MediaCard
        v-for="item in items"
        :key="item.id"
        :item="item"
        :kind="kind"
        :show-filename="showFilename"
        @open="emit('open', $event)"
        @fav="emit('fav', $event)"
        @action="(action, target) => emit('action', action, target)"
      />
    </div>

    <div ref="sentinel" aria-hidden="true" />
    <div v-if="loadingMore" class="mv-center-pad">
      <Icon name="spinner" :size="18" class="mv-spin" />
    </div>
    <div v-else-if="!hasMore && items.length > 24" class="mv-center-pad">
      已经到底了
    </div>
  </template>
</template>
