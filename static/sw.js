self.addEventListener("install", event => {
  console.log("Service Worker instalado");
});

self.addEventListener("fetch", event => {
  // pode melhorar depois com cache
});