<script setup>
import { computed } from 'vue'

import Icon from './Icon.vue'
import MediaCard from './MediaCard.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  kind: { type: String, default: 'video' },
  loading: { type: Boolean, default: false },
  gridClass: { type: String, default: '' },
  showFilename: { type: Boolean, default: false },
  emptyTitle: { type: String, default: '这里还没有内容' },
  emptyDesc: { type: String, default: '' },
})
const emit = defineEmits(['open', 'fav', 'action'])

const isPhoto = computed(() => props.kind === 'photo')
const classes = computed(() => [
  'mv-grid',
  isPhoto.value ? 'mv-grid--photo' : '',
  props.gridClass,
])
</script>

<template>
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

  <div v-else :class="classes">
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
</template>
