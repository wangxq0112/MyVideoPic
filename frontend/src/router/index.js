/**
 * 路由表 —— 只有四个页面 + 播放页。
 *
 * 搜索与历史是顶栏浮层（见 stores/ui.js），不占路由：
 * 它们覆盖在当前页之上，关闭后不该丢失原页面的滚动位置与筛选条件。
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/videos' },
  { path: '/videos', name: 'videos', component: () => import('../views/Videos.vue') },
  { path: '/images', name: 'images', component: () => import('../views/Images.vue') },
  { path: '/favorites', name: 'favorites', component: () => import('../views/Favorites.vue') },
  { path: '/settings', name: 'settings', component: () => import('../views/Settings.vue') },
  { path: '/play/:id', name: 'player', component: () => import('../views/Player.vue') },
  // 手输错地址时回首页，而不是留在空白页
  { path: '/:pathMatch(.*)*', redirect: '/videos' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, saved) => saved || { top: 0 },
})
