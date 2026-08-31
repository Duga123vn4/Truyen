// Light Novel Audio Reader — Progressive Web App Service Worker V1.0
const CACHE_NAME = 'novel-reader-v1';
const STATIC_ASSETS = [
  './',
  './Doc_Truyen.html',
  './index.html',
  './chapters.js',
  './manifest.json',
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// 1. Install & Pre-cache static shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Caching static shell');
      return cache.addAll(STATIC_ASSETS).catch(err => console.warn('PWA Precache partial warning:', err));
    })
  );
  self.skipWaiting();
});

// 2. Activate & Clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(keyList.map((key) => {
        if (key !== CACHE_NAME) {
          console.log('[ServiceWorker] Removing old cache', key);
          return caches.delete(key);
        }
      }));
    })
  );
  self.clients.claim();
});

// 3. Fetch Strategy: Network First with Cache Fallback for dynamic novel content
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Không cache TTS audio stream trực tiếp để tránh tràn storage
  if (url.pathname.includes('/translate_tts') || url.pathname.includes('speech') || url.searchParams.has('ie')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache bản mới nếu thành công
        if (response && response.status === 200 && event.request.method === 'GET') {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback về cache khi mất mạng
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) return cachedResponse;
          if (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html')) {
            return caches.match('./Doc_Truyen.html');
          }
        });
      })
  );
});