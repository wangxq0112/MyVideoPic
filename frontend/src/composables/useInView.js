/**
 * IntersectionObserver 两件套：懒加载封面 + 触底加载更多。
 *
 * 缩略图数量可能上千，一次性发起请求会把浏览器的连接池占满，
 * 因此卡片进入视口才真正给 <img> 赋 src。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

/** 元素进入视口一次后就固定为 true（封面不需要反复卸载） */
export function useInView(options = {}) {
  const el = ref(null)
  const visible = ref(false)
  let observer = null

  function stop() {
    if (observer) {
      observer.disconnect()
      observer = null
    }
  }

  onMounted(() => {
    // 老浏览器/测试环境没有该 API —— 直接当作可见，功能不受影响
    if (typeof IntersectionObserver === 'undefined') {
      visible.value = true
      return
    }
    observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        visible.value = true
        stop()
      }
    }, { rootMargin: '320px 0px', ...options })
    if (el.value) observer.observe(el.value)
  })

  onBeforeUnmount(stop)

  return { el, visible }
}

/** 哨兵元素进入视口就回调，用于无限滚动 */
export function useInfiniteScroll(onHit) {
  const sentinel = ref(null)
  let observer = null

  onMounted(() => {
    if (typeof IntersectionObserver === 'undefined' || !sentinel.value) return
    observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) onHit()
    }, { rootMargin: '600px 0px' })
    observer.observe(sentinel.value)
  })

  onBeforeUnmount(() => observer?.disconnect())

  return { sentinel }
}
