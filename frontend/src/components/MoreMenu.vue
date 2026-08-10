<script setup>
/**
 * 卡片右下角的 ⋮ 菜单。
 *
 * 菜单 teleport 到 body 并用 position: fixed —— 卡片本身有
 * overflow: hidden（为了裁剪封面缩放动画），菜单若留在卡片内部会被切掉。
 */
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

import Icon from './Icon.vue'

const props = defineProps({
  items: { type: Array, required: true },   // [{ key, label, icon, danger }]
  label: { type: String, default: '更多操作' },
})
const emit = defineEmits(['select'])

const open = ref(false)
const btn = ref(null)
const pos = ref({ top: 0, left: 0 })

const MENU_W = 184
const GAP = 6

function place() {
  const r = btn.value?.getBoundingClientRect()
  if (!r) return
  // 估个高度用于判断是否需要向上翻转，8px 是菜单自身的上下内边距
  const h = props.items.length * 33 + 10
  const left = Math.min(Math.max(r.right - MENU_W, GAP), window.innerWidth - MENU_W - GAP)
  const below = r.bottom + GAP
  const top = below + h > window.innerHeight - GAP
    ? Math.max(r.top - h - GAP, GAP)
    : below
  pos.value = { top, left }
}

function close() {
  open.value = false
  window.removeEventListener('scroll', close, true)
  window.removeEventListener('resize', close)
}

async function toggle(e) {
  e.stopPropagation()
  e.preventDefault()
  if (open.value) {
    close()
    return
  }
  open.value = true
  await nextTick()
  place()
  // 滚动或窗口尺寸变化时直接关掉，比持续重算位置更省事也更符合直觉
  window.addEventListener('scroll', close, true)
  window.addEventListener('resize', close)
}

function pick(item) {
  close()
  emit('select', item.key)
}

const style = computed(() => ({
  top: `${pos.value.top}px`,
  left: `${pos.value.left}px`,
  minWidth: `${MENU_W}px`,
}))

onBeforeUnmount(close)
</script>

<template>
  <button
    ref="btn"
    class="mv-dots"
    :class="{ 'is-open': open }"
    type="button"
    :title="label"
    :aria-label="label"
    :aria-expanded="open"
    @click="toggle"
  >
    <Icon name="dots" :size="17" />
  </button>

  <Teleport to="body">
    <div v-if="open" class="mv-menu-scrim" @click="close" @contextmenu.prevent="close" />
    <div v-if="open" class="mv-menu" :style="style" role="menu">
      <button
        v-for="it in items"
        :key="it.key"
        class="mv-menu__item"
        :class="{ 'mv-menu__item--danger': it.danger }"
        type="button"
        role="menuitem"
        @click="pick(it)"
      >
        <Icon v-if="it.icon" :name="it.icon" :size="15" />
        {{ it.label }}
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
/* 透明遮罩：点任意处关菜单，同时挡住底层卡片的 hover 干扰 */
.mv-menu-scrim { position: fixed; inset: 0; z-index: 89; }
</style>
