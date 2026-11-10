const SHELL_CACHE = 'stock-v2-shell-v1'
const PYODIDE_CACHE = 'stock-v2-pyodide-314-0-6'
const APP_SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/python/rules.json',
]

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE)
    await cache.addAll(APP_SHELL)
    await self.skipWaiting()
  })())
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.filter((key) => key.startsWith('stock-v2-') && ![SHELL_CACHE, PYODIDE_CACHE].includes(key)).map((key) => caches.delete(key)))
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)

  // Cache same-origin application assets. Navigation falls back to the app shell offline.
  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cache = await caches.open(SHELL_CACHE)
      if (request.mode === 'navigate') {
        try {
          const response = await fetch(request)
          if (response.ok) cache.put('/index.html', response.clone())
          return response
        } catch {
          return (await cache.match('/index.html')) || Response.error()
        }
      }
      const cached = await cache.match(request)
      if (cached) return cached
      const response = await fetch(request)
      if (response.ok && response.type !== 'opaque') await cache.put(request, response.clone())
      return response
    })())
    return
  }

  // Pyodide runtime is loaded from a pinned CDN URL. Cache successful runtime/package responses for offline use.
  if (url.hostname === 'cdn.jsdelivr.net' && url.pathname.startsWith('/pyodide/v314.0.6/')) {
    event.respondWith((async () => {
      const cache = await caches.open(PYODIDE_CACHE)
      const cached = await cache.match(request)
      if (cached) return cached
      const response = await fetch(request)
      if (response.ok && response.type !== 'opaque') await cache.put(request, response.clone())
      return response
    })())
  }
})
