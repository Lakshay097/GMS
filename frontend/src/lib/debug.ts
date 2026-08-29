/**
 * Debug logging utility.
 * Only outputs when VITE_DEBUG=true is set in the environment.
 * Usage: import { debug, warn, error } from './debug'
 */
const enabled = import.meta.env.VITE_DEBUG === 'true'

export function debug(...args: unknown[]) {
  if (enabled) console.log('[debug]', ...args)
}

export function warn(...args: unknown[]) {
  if (enabled) console.warn('[warn]', ...args)
}

export function error(...args: unknown[]) {
  // Always log errors — these indicate real problems
  console.error('[error]', ...args)
}
