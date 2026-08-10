<script setup>
/** 全局吐司容器 —— 由 ui store 驱动，挂在 App 根节点。 */
import Icon from './Icon.vue'
import { useUiStore } from '../stores/ui.js'

const ui = useUiStore()
</script>

<template>
  <Teleport to="body">
    <div class="mv-toasts" role="status" aria-live="polite">
      <div
        v-for="t in ui.toasts"
        :key="t.id"
        class="mv-toast"
        :class="t.type === 'err' ? 'mv-toast--err' : 'mv-toast--ok'"
      >
        <Icon :name="t.type === 'err' ? 'warn' : 'check'" :size="15" />
        <span>{{ t.message }}</span>
      </div>
    </div>
  </Teleport>
</template>
