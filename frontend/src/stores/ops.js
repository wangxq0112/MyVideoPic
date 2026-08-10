/**
 * 文件操作中枢 —— 重命名 / 移动 / 删除 / 收藏。
 *
 * 三个对话框在 App.vue 里只挂载一次，任何页面的卡片菜单都通过这个
 * store 打开它们；操作成功后就地同步视频/图片列表，并递增 revision，
 * 让收藏页、搜索浮层这类"派生列表"知道该重新拉取了。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getMoveProgress, toggleFavorite } from '../api/api.js'
import { usePhotosStore } from './photos.js'
import { useVideosStore } from './videos.js'

export const useOpsStore = defineStore('ops', () => {
  const videos = useVideosStore()
  const photos = usePhotosStore()

  const mode = ref('')          // '' | 'rename' | 'move' | 'delete'
  const kind = ref('video')     // 'video' | 'photo'
  const item = ref(null)
  const busy = ref(false)
  const error = ref('')
  const revision = ref(0)       // 每次成功变更 +1
  const removedId = ref('')     // 最近一次被删除的条目（播放页据此退出）
  const moveTask = ref(null)    // 跨盘移动进度快照

  const open = computed(() => mode.value !== '')
  const store = () => (kind.value === 'video' ? videos : photos)

  function start(nextMode, nextKind, target) {
    mode.value = nextMode
    kind.value = nextKind
    item.value = target
    error.value = ''
    busy.value = false
    moveTask.value = null
  }

  function close() {
    if (busy.value) return       // 正在跨盘复制时不允许关掉进度面板
    mode.value = ''
    item.value = null
    error.value = ''
    moveTask.value = null
  }

  /** 跨盘移动是后台线程，轮询到终态为止 */
  async function pollMove(taskId) {
    while (true) {
      await new Promise((r) => setTimeout(r, 700))
      let data
      try {
        data = (await getMoveProgress(taskId)).data
      } catch (e) {
        throw new Error(e.friendlyMessage || '移动任务状态获取失败')
      }
      moveTask.value = data
      if (data.status === 'completed') return data
      if (data.status === 'failed') throw new Error(data.message || '移动失败')
    }
  }

  async function run(fn) {
    busy.value = true
    error.value = ''
    try {
      const result = await fn()
      revision.value++
      return result
    } catch (e) {
      error.value = e.friendlyMessage || e.message || '操作失败'
      throw e
    } finally {
      busy.value = false
    }
  }

  const rename = (name) => run(() => store().rename(item.value.id, name))

  function remove() {
    const id = item.value.id
    return run(async () => {
      const data = await store().remove(id)
      removedId.value = id
      return data
    })
  }

  function move(libraryId) {
    return run(async () => {
      const data = await store().move(item.value.id, libraryId)
      if (!data?.task_id) return data
      // 202 —— 跨盘，等后台线程复制完再更新列表
      moveTask.value = { status: 'running', percent: 0, message: '正在跨盘复制…' }
      const done = await pollMove(data.task_id)
      store().patchItem(item.value.id, { library_id: libraryId })
      return done
    })
  }

  /** 收藏开关 —— 视频页/图片页/收藏页/搜索浮层共用 */
  async function toggleFav(favKind, target) {
    const res = await toggleFavorite(favKind, target.id)
    const favorited = !!res.data.favorited
    ;(favKind === 'video' ? videos : photos).setFavorited(target.id, favorited)
    revision.value++
    return favorited
  }

  return {
    mode, kind, item, busy, error, revision, removedId, moveTask, open,
    start, close, rename, move, remove, toggleFav,
  }
})
