/**
 * 图片状态 —— 图片页、收藏页共用。
 */
import { defineStore } from 'pinia'

import { deletePhoto, fetchPhotos, movePhoto, renamePhoto } from '../api/api.js'
import { createMediaState } from './media.js'

export const usePhotosStore = defineStore('photos', () => {
  const state = createMediaState({
    fetchList: fetchPhotos,
    renameItem: renamePhoto,
    moveItem: movePhoto,
    deleteItem: deletePhoto,
  })

  function findById(id) {
    return state.list.value.find((p) => p.id === id) || null
  }

  return { ...state, findById }
})
