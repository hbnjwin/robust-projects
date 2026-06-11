import { ref, onMounted, onUnmounted, type Ref } from 'vue'

const FULLSCREEN_CONTAINER_ID = 'fullscreen-container'

/**
 * Fullscreen composable for the report preview page.
 *
 * Fixes three bugs:
 *
 * 1. el-dialog disappears in fullscreen because it mounts to body,
 *    which is outside the fullscreen layer. getAppendTo() returns the
 *    fullscreen container selector during fullscreen so overlays render
 *    inside the fullscreen element.
 *
 * 2. ElMessageBox / ElNotification also mount to body by default.
 *    The same getAppendTo() helper is used as their `appendTo` option.
 *
 * 3. Pressing ESC triggers the browser's native fullscreen exit,
 *    bypassing toggleFullscreen(). The isFullscreen ref was never
 *    updated. We fix this by listening to the `fullscreenchange` event
 *    on document and reading document.fullscreenElement to keep the
 *    reactive state in sync regardless of how fullscreen was exited.
 */
export function useFullscreen(containerRef: Ref<HTMLElement | undefined>) {
  const isFullscreen = ref(false)

  // Fix #3: sync state whenever the browser enters/exits fullscreen,
  // including ESC key which we cannot intercept directly.
  function onFullscreenChange() {
    isFullscreen.value = !!document.fullscreenElement
  }

  async function toggleFullscreen() {
    if (!containerRef.value) return

    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await containerRef.value.requestFullscreen()
    }
  }

  /**
   * Returns the CSS selector of the element that overlays (dialog,
   * message-box, notification) should be appended to.
   *
   * During fullscreen the browser only renders descendants of the
   * fullscreen element, so we must mount overlays there instead of body.
   */
  function getAppendTo(): string {
    return isFullscreen.value ? `#${FULLSCREEN_CONTAINER_ID}` : 'body'
  }

  onMounted(() => {
    document.addEventListener('fullscreenchange', onFullscreenChange)
  })

  onUnmounted(() => {
    document.removeEventListener('fullscreenchange', onFullscreenChange)
  })

  return {
    isFullscreen,
    toggleFullscreen,
    getAppendTo,
    FULLSCREEN_CONTAINER_ID,
  }
}
