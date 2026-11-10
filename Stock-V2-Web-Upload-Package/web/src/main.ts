import { createApp } from 'vue'
import App from './App.vue'
import './styles.css'

createApp(App).mount('#app')

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      await navigator.serviceWorker.register('/sw.js', { scope: '/' })
      await navigator.serviceWorker.ready
      // The first visit installs the Service Worker. Reload once the current page is controlled,
      // so the dedicated analysis Worker and its Pyodide CDN requests can be cached offline.
      if (!navigator.serviceWorker.controller) {
        navigator.serviceWorker.addEventListener('controllerchange', () => window.location.reload(), { once: true })
      }
    } catch (error) {
      console.error('[Stock V2.0] Service Worker registration failed:', error)
    }
  })
}
