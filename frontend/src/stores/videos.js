/**
 * 视频状态 —— 视频页、收藏页、播放页共用同一份缓存。
 */
import { defineStore } from 'pinia'

import { deleteVideo, fetchVideos, moveVideo, renameVideo } from '../api/api.js'
import { createMediaState } from './media.js'

export const useVideosStore = defineStore('videos', () => {
  const state = createMediaState({
    fetchList: fetchVideos,
    renameItem: renameVideo,
    moveItem: moveVideo,
    deleteItem: deleteVideo,
  })

  /** 播放页优先用列表里的缓存，避免从卡片点进去还要等一次请求 */
  function findById(id) {
    return state.list.value.find((v) => v.id === id) || null
  }

  return { ...state, findById }
})
