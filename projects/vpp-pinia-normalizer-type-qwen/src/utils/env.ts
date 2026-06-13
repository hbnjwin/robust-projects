// ---------------------------------------------------------------------------
// Environment detection utilities
// ---------------------------------------------------------------------------

/**
 * Detect whether we are running inside a Tauri webview.
 *
 * BUG (fixed): The previous implementation checked `window.__TAURI__`
 * via direct property access. In production builds Vite's minifier can
 * statically evaluate `window.__TAURI__` as `undefined` (because no
 * import creates the binding at compile time) and replace the whole
 * expression with `false`, causing every invoke call to fall through
 * to the mock branch.
 *
 * FIX: Use the `in` operator (`'__TAURI_INTERNALS__' in window`) which
 * is a runtime-only check that no bundler can tree-shake or statically
 * evaluate away. We also check the Tauri v1 global (`__TAURI__`) for
 * backwards compatibility, and add `import.meta.env.VITE_TAURI` as a
 * build-time signal for hybrid builds.
 */
export function isTauri(): boolean {
  if (typeof window === 'undefined') return false

  // Build-time flag: set VITE_TAURI=true in .env or tauri.conf.json > build > beforeBuildCommand
  if (import.meta.env.VITE_TAURI === 'true') return true

  // Tauri v2 injects __TAURI_INTERNALS__ on the window object at runtime.
  // The `in` operator is a pure runtime check — bundlers cannot eliminate it.
  if ('__TAURI_INTERNALS__' in window) return true

  // Tauri v1 fallback
  if ('__TAURI__' in window) return true

  return false
}

/**
 * Safely invoke a Tauri command. Falls back to `mockFn` when not in a
 * Tauri context (e.g. during web development or SSR).
 */
export async function tauriInvoke<T>(
  command: string,
  args?: Record<string, unknown>,
  mockFn?: () => T | Promise<T>,
): Promise<T> {
  if (isTauri()) {
    // Dynamic import keeps the Tauri API out of web-only bundles.
    const { invoke } = await import('@tauri-apps/api/core')
    return invoke<T>(command, args)
  }

  if (mockFn) return mockFn()

  throw new Error(
    `Tauri is not available and no mock was provided for command "${command}"`,
  )
}
