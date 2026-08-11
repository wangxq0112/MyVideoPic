<script setup>
import { computed } from 'vue'

import Icon from './Icon.vue'

const props = defineProps({
  currentPage: { type: Number, required: true },
  totalPages: { type: Number, required: true },
  total: { type: Number, required: true },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['page'])

const pages = computed(() => {
  const total = props.totalPages
  const current = props.currentPage
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)

  const result = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  if (start > 2) result.push(null)
  for (let page = start; page <= end; page += 1) {
    result.push(page)
  }
  if (end < total - 1) result.push(null)
  result.push(total)
  return result
})

function go(page) {
  if (!page || page === props.currentPage || props.loading) return
  emit('page', page)
}
</script>

<template>
  <nav v-if="totalPages > 1" class="mv-pagination" aria-label="分页">
    <span class="mv-pagination__summary">第 {{ currentPage }} / {{ totalPages }} 页，共 {{ total }} 项</span>
    <div class="mv-pagination__controls">
      <button
        class="mv-icon-btn"
        type="button"
        title="上一页"
        aria-label="上一页"
        :disabled="loading || currentPage <= 1"
        @click="go(currentPage - 1)"
      >
        <Icon name="chevronLeft" :size="16" />
      </button>
      <template v-for="(page, index) in pages" :key="`${page}-${index}`">
        <span v-if="page === null" class="mv-pagination__ellipsis">...</span>
        <button
          v-else
          class="mv-pagination__page"
          :class="{ 'is-active': page === currentPage }"
          type="button"
          :disabled="loading"
          :aria-current="page === currentPage ? 'page' : undefined"
          @click="go(page)"
        >
          {{ page }}
        </button>
      </template>
      <button
        class="mv-icon-btn"
        type="button"
        title="下一页"
        aria-label="下一页"
        :disabled="loading || currentPage >= totalPages"
        @click="go(currentPage + 1)"
      >
        <Icon name="chevronRight" :size="16" />
      </button>
    </div>
  </nav>
</template>
