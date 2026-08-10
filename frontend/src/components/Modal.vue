<script setup>
/**
 * 模态外壳 —— 遮罩 + 标题栏 + 内容 + 底栏，Esc 关闭。
 *
 * teleport 到 body，避免被父级的 transform / overflow 影响定位。
 */
import { onBeforeUnmount, onMounted } from 'vue'

import Icon from './Icon.vue'

const props = defineProps({
  title: { type: String, default: '' },
  wide: { type: Boolean, default: false },
  flush: { type: Boolean, default: false },
  closable: { type: Boolean, default: true },
})
const emit = defineEmits(['close'])

function onKey(e) {
  if (e.key === 'Escape' && props.closable) emit('close')
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="mv-scrim" @click="closable && emit('close')" />
    <div class="mv-modal" :class="{ 'mv-modal--wide': wide }" role="dialog" aria-modal="true">
      <div v-if="title" class="mv-modal__head">
        <div class="mv-modal__title mv-grow">{{ title }}</div>
        <button
          v-if="closable"
          class="mv-icon-btn"
          type="button"
          aria-label="关闭"
          @click="emit('close')"
        >
          <Icon name="x" :size="17" />
        </button>
      </div>

      <div class="mv-modal__body" :class="{ 'mv-modal__body--flush': flush }">
        <slot />
      </div>

      <div v-if="$slots.foot" class="mv-modal__foot">
        <slot name="foot" />
      </div>
    </div>
  </Teleport>
</template>
