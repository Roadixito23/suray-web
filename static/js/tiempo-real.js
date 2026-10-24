// Actualizacion en vivo de Inicio y Horarios. El contenedor [data-live-url] trae el ETag del
// HTML que ya muestra; cada ~15 s se pide el fragmento con If-None-Match: un 304 no cambia nada
// y un 200 reemplaza el contenido y destella solo los bloques que cambiaron. Sin JS, o si el
// endpoint falla, la pagina sigue mostrando lo que renderizo el servidor.
(function (root) {
  'use strict';

  var MAX_ESPERA = 120000;
  var BLOQUES = '.departure, .day-card';

  // Espera hasta el proximo sondeo: intervalo con jitter de +-10 %, y tras errores seguidos
  // se duplica por cada fallo hasta 2 minutos. `azar` es un numero en [0, 1).
  function proximoRetraso(intervalo, fallos, azar) {
    var base = intervalo * Math.pow(2, Math.min(fallos, 10));
    var jitter = 1 + (azar * 0.2 - 0.1);
    return Math.min(Math.round(base * jitter), MAX_ESPERA);
  }

  // Indices de los bloques cuyo HTML cambio, o que son nuevos.
  function bloquesCambiados(antes, despues) {
    var res = [];
    for (var i = 0; i < despues.length; i++) {
      if (antes[i] !== despues[i]) { res.push(i); }
    }
    return res;
  }

  function hhmm(fecha) {
    function p(n) { return ('0' + n).slice(-2); }
    return p(fecha.getHours()) + ':' + p(fecha.getMinutes());
  }

  function iniciar(doc, ventana) {
    var caja = doc.querySelector('[data-live-url]');
    if (!caja || !ventana.fetch) { return; }

    var url = caja.getAttribute('data-live-url');
    var intervalo = parseInt(caja.getAttribute('data-live-interval'), 10) || 15000;
    var etag = caja.getAttribute('data-live-etag');
    var estado = doc.querySelector('[data-live-status]');
    var anuncio = doc.querySelector('[data-live-announce]');
    var fallos = 0, timer = null, enCurso = false;

    function htmlBloques() {
      return Array.prototype.map.call(caja.querySelectorAll(BLOQUES), function (b) { return b.outerHTML; });
    }

    function mostrarHora() {
      if (!estado) { return; }
      estado.textContent = 'Actualizado ' + hhmm(new Date());
      estado.hidden = false;
    }

    function aplicar(html) {
      var antes = htmlBloques();
      caja.innerHTML = html;
      var bloques = caja.querySelectorAll(BLOQUES);
      bloquesCambiados(antes, htmlBloques()).forEach(function (i) {
        var b = bloques[i];
        b.classList.add('live-flash');
        b.addEventListener('animationend', function () { b.classList.remove('live-flash'); });
      });
      if (anuncio) {
        anuncio.textContent = '';
        // Reasigna en otro turno para que el lector de pantalla repita el aviso.
        ventana.setTimeout(function () { anuncio.textContent = 'Horarios actualizados'; }, 50);
      }
    }

    function programar() {
      ventana.clearTimeout(timer);
      if (doc.hidden) { return; }
      timer = ventana.setTimeout(sondear, proximoRetraso(intervalo, fallos, Math.random()));
    }

    function sondear() {
      ventana.clearTimeout(timer);
      if (enCurso) { return; }
      enCurso = true;
      ventana.fetch(url, { cache: 'no-store', headers: { 'If-None-Match': etag || '' }, credentials: 'same-origin' })
        .then(function (r) {
          if (r.status === 304) { return null; }
          if (!r.ok) { throw new Error('HTTP ' + r.status); }
          return r.text().then(function (html) { return { html: html, etag: r.headers.get('ETag') }; });
        })
        .then(function (nuevo) {
          fallos = 0;
          // Mientras se genera la imagen de Horarios no se toca el contenido; se reintenta despues.
          if (nuevo && nuevo.etag !== etag && !caja.hasAttribute('data-live-busy')) {
            etag = nuevo.etag;
            aplicar(nuevo.html);
          }
          mostrarHora();
        })
        .catch(function () { fallos += 1; })
        .then(function () { enCurso = false; programar(); });
    }

    doc.addEventListener('visibilitychange', function () {
      if (doc.hidden) { ventana.clearTimeout(timer); } else { sondear(); }
    });
    ventana.addEventListener('online', sondear);
    ventana.addEventListener('pageshow', function (e) { if (e.persisted) { sondear(); } });
    programar();
  }

  if (typeof document !== 'undefined' && typeof window !== 'undefined') {
    iniciar(document, window);
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { proximoRetraso: proximoRetraso, bloquesCambiados: bloquesCambiados, hhmm: hhmm, iniciar: iniciar };
  }
}(this));
