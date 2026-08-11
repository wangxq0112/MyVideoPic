/**
 * Backwards-compatible API facade.
 *
 * New code should import the focused module in this directory. Existing views
 * keep using this facade so the internal reorganization has no UI behavior
 * change or large import-only diff.
 */
export { API_BASE, errMsg } from './client.js'
export { default } from './client.js'
export * from './libraries.js'
export * from './media.js'
export * from './settings.js'
export * from './tasks.js'
