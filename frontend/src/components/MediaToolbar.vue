<script setup>
/**
 * 筛选工具条 —— 分类胶囊、媒体库下拉、排序下拉和固定翻页按钮。
 *
 * 所有条件都提交给后端处理（SQLite 上千条也是毫秒级），
 * 前端不做本地过滤，避免"分页数据只筛到了当前页"的错觉。
 */
import Icon from './Icon.vue'

const props = defineProps({
  filters: { type: Object, required: true },
  categories: { type: Array, default: () => [] },
  libraries: { type: Array, default: () => [] },
  orderings: { type: Array, required: true },
  currentPage: { type: Number, default: 1 },
  totalPages: { type: Number, default: 1 },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['change', 'page'])

function go(page) {
  if (props.loading || page < 1 || page > props.totalPages || page === props.currentPage) return
  emit('page', page)
}
</script>

<template>
  <div class="mv-toolbar">
    <div class="mv-pillbar mv-toolbar__grow">
      <button
        class="mv-pill mv-pill--soft"
        :class="{ 'is-active': filters.category === 'all' }"
        type="button"
        @click="emit('change', { category: 'all' })"
      >
        全部
      </button>
      <button
        v-for="cat in categories"
        :key="cat"
        class="mv-pill mv-pill--soft"
        :class="{ 'is-active': filters.category === cat }"
        type="button"
        @click="emit('change', { category: cat })"
      >
        {{ cat }}
      </button>
      <button
        class="mv-pill mv-pill--soft"
        :class="{ 'is-active': filters.favorited }"
        type="button"
        @click="emit('change', { favorited: !filters.favorited })"
      >
        <Icon name="star" :size="13" /> 仅收藏
      </button>
    </div>

    <div class="mv-toolbar__actions">
      <select
        v-if="libraries.length > 1"
        class="mv-select"
        :value="filters.library"
        aria-label="按媒体库筛选"
        @change="emit('change', { library: $event.target.value })"
      >
        <option value="">所有媒体库</option>
        <option v-for="lib in libraries" :key="lib.id" :value="lib.id">
          {{ lib.name }}
        </option>
      </select>

      <select
        class="mv-select"
        :value="filters.ordering"
        aria-label="排序方式"
        @change="emit('change', { ordering: $event.target.value })"
      >
        <option v-for="o in orderings" :key="o.key" :value="o.key">{{ o.label }}</option>
      </select>

      <div class="mv-toolbar__pager" aria-label="列表翻页">
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
    </div>
  </div>
</template>
