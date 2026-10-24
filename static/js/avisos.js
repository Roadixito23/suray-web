// Avisos de Inicio: si una imagen externa no carga, el aviso se ve igual, sin ella. El noticiero
// es solo CSS (static/css/avisos.css). El contenedor vivo reemplaza su HTML al haber cambios,
// asi que se revisa de nuevo al detectarlo.
(function () {
  'use strict';

  function ocultar(img) {
    var marco = img.closest('.notice__img');
    if (marco) { marco.hidden = true; }
  }

  function barrer() {
    Array.prototype.forEach.call(document.querySelectorAll('.notice__img img'), function (img) {
      if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) { ocultar(img); }
    });
  }

  document.addEventListener('error', function (e) {
    if (e.target && e.target.tagName === 'IMG') { ocultar(e.target); }
  }, true);

  barrer();
  var vivo = document.querySelector('[data-live-url]');
  if (vivo && window.MutationObserver) {
    new MutationObserver(barrer).observe(vivo, { childList: true });
  }
})();
