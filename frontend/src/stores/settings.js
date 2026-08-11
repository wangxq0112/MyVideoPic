/**
 * 应用偏好 —— 播放/外观/扫描三组，结构与后端 DEFAULT_SETTINGS 对齐。
 *
 * 本地默认值只是首帧兜底，页面挂载后立刻用后端值覆盖，
 * 避免"设置页改了、播放页没生效"的不一致。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchSettings, saveSettings } from '../api/api.js'

const DEFAULTS = {
  playback: {
    autoplay: false,
    default_volume: 80,
    seek_step: 10,
    remember_position: true,
  },
  appearance: {
    grid_density: 'comfortable',
    show_filename: false,
  },
  scan: {
    generate_video_thumbnails: true,
    skip_hidden: true,
  },
}

/** 深拷贝默认值，避免多处共享同一对象引用 */
const cloneDefaults = () => JSON.parse(JSON.stringify(DEFAULTS))

export const useSettingsStore = defineStore('settings', () => {
  const data = ref(cloneDefaults())
  const loaded = ref(false)
  const saving = ref(false)

  const playback = computed(() => data.value.playback)
  const appearance = computed(() => data.value.appearance)
  const scan = computed(() => data.value.scan)

  /** 网格密度 → 对应的 CSS 修饰类 */
  const gridClass = computed(() => {
    const d = data.value.appearance.grid_density
    if (d === 'compact') return 'mv-grid--compact'
    if (d === 'spacious') return 'mv-grid--spacious'
    return ''
  })

  async function load(force = false) {
    if (loaded.value && !force) return
    try {
      const res = await fetchSettings()
      const merged = cloneDefaults()
      for (const group of Object.keys(merged)) {
        Object.assign(merged[group], res.data?.[group] || {})
      }
      data.value = merged
      loaded.value = true
    } catch {
      // 读不到就用默认值，不阻塞页面渲染
      loaded.value = true
    }
  }

  /** 改一个键并立刻落库（设置页开关都是即时生效，没有"保存"按钮） */
  async function set(group, key, value) {
    if (!data.value[group] || !(key in data.value[group])) return
    const prev = data.value[group][key]
    data.value[group][key] = value
    saving.value = true
    try {
      await saveSettings({ [group]: { [key]: value } })
    } catch (e) {
      data.value[group][key] = prev   // 回滚，保持 UI 与后端一致
      throw e
    } finally {
      saving.value = false
    }
  }

  return { data, loaded, saving, playback, appearance, scan, gridClass, load, set }
})
