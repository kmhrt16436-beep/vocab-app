'use strict';
// Cache only this app's static files. Authentication and study data stay out of CacheStorage.
const CACHE_PREFIX='study-cards:'+self.registration.scope+':';
const SHELL_CACHE=CACHE_PREFIX+'shell-v2',IMAGE_CACHE=CACHE_PREFIX+'images-v1';
const APP_URL=new URL('index.html',self.registration.scope).href;
const STATIC_PATHS=['index.html','manifest.webmanifest','icons/icon-192.png','icons/icon-512.png'];
const STATIC_URLS=new Set(STATIC_PATHS.map(path=>new URL(path,self.registration.scope).href));
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(SHELL_CACHE);
 await cache.addAll(STATIC_PATHS.map(path=>new Request(new URL(path,self.registration.scope),{cache:'reload'})));
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 for(const name of await caches.keys())if(name.startsWith(CACHE_PREFIX)&&![SHELL_CACHE,IMAGE_CACHE].includes(name))await caches.delete(name);
 await self.clients.claim();
})()));
self.addEventListener('message',event=>{if(event.data?.type==='SKIP_WAITING')self.skipWaiting()});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url),scope=new URL(self.registration.scope);
 if(request.method!=='GET'||url.origin!==scope.origin||!url.pathname.startsWith(scope.pathname))return;
 const relative=url.pathname.slice(scope.pathname.length);
 if(request.mode==='navigate'&&(relative===''||relative==='index.html')){
  event.respondWith((async()=>{
   const cache=await caches.open(SHELL_CACHE),controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4500);
   try{
    const response=await fetch(new Request(request,{cache:'no-cache',signal:controller.signal}));
    if(!response.ok)throw Error('Application unavailable');
    try{await cache.put(APP_URL,response.clone())}catch(e){}return response;
   }catch(error){const saved=await cache.match(APP_URL);if(saved)return saved;throw error}
   finally{clearTimeout(timeout)}
  })());return;
 }
 if(STATIC_URLS.has(url.href)){
  event.respondWith((async()=>{const cache=await caches.open(SHELL_CACHE),saved=await cache.match(request);return saved||fetch(request)})());return;
 }
 if(/^toeic-\d{3}\.png$/.test(relative)&&!url.search){
  event.respondWith((async()=>{
   const cache=await caches.open(IMAGE_CACHE),saved=await cache.match(request);if(saved)return saved;
   const response=await fetch(request);
   if(response.ok){try{await cache.put(request,response.clone());const keys=await cache.keys();for(const key of keys.slice(0,Math.max(0,keys.length-32)))await cache.delete(key)}catch(e){}}
   return response;
  })());
 }
});
