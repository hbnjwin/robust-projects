import { ref, onMounted, onUnmounted, type Ref } from 'vue'

const FULLSCREEN_CONTAINER_ID = 'fullscreen-container'

export function useFullscreen(containerRef: Ref<HTMLElement | undefined>) {
  const isFullscreen = ref(false)

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
   * Returns the element that overlays (dialog, message-box, notification)
   * should mount into. During fullscreen the browser only renders content
   * inside the fullscreen element, so we must append there instead of body.
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
