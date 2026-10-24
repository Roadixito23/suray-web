// Vista previa del aviso en /edit/avisos/: arma la misma estructura que sitio/_aviso.html
// con los valores actuales del formulario (solo DOM y textContent, nada de innerHTML).
(function () {
  'use strict';

  var form = document.getElementById('aviso-form');
  var destino = document.getElementById('aviso-preview');
  if (!form || !destino) { return; }

  function valor(nombre) {
    var el = form.elements[nombre];
    return el ? el.value : '';
  }

  function luminancia(hex) {
    var c = [1, 3, 5].map(function (i) {
      var v = parseInt(hex.substr(i, 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }

  function tinta(estilo, principal, secundario) {
    if (estilo === 'borde') { return '#FFFFFF'; }
    var cols = [principal];
    if (estilo === 'degradado') { cols.push(secundario); }
    var lums = cols.map(luminancia);
    var conNegro = Math.min.apply(null, lums.map(function (l) { return (l + 0.05) / 0.05; }));
    var conBlanco = Math.min.apply(null, lums.map(function (l) { return 1.05 / (l + 0.05); }));
    return conNegro > conBlanco ? '#000000' : '#FFFFFF';
  }

  function pintar() {
    var propios = form.elements.colores_propios && form.elements.colores_propios.checked;
    var estilo = propios ? valor('estilo_color') : 'borde';
    var art = document.createElement('article');
    art.className = 'notice notice--' + valor('tipo') + ' notice--' + estilo + ' notice--' + valor('formato');
    if (propios) {
      var p = valor('color_principal'), s = valor('color_secundario') || p;
      art.style.setProperty('--n-main', p);
      art.style.setProperty('--n-alt', s);
      art.style.setProperty('--n-ink', tinta(estilo, p, s));
    }
    var url = valor('imagen_url').trim();
    if (/^https:\/\/\S+$/i.test(url)) {
      var marco = document.createElement('div');
      marco.className = 'notice__img';
      var img = document.createElement('img');
      img.alt = '';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', function () { marco.hidden = true; });
      img.src = url;
      marco.appendChild(img);
      art.appendChild(marco);
    }
    var cuerpo = document.createElement('div');
    cuerpo.className = 'notice__body';
    var h = document.createElement('h2');
    h.className = 'notice__title';
    h.textContent = valor('titulo') || 'Título del aviso';
    cuerpo.appendChild(h);
    var texto = valor('mensaje');
    if (valor('formato') === 'carrusel') {
      cuerpo.classList.add('notice__body--ticker');
      var linea = texto.split('\n').map(function (l) { return l.trim(); }).filter(Boolean).join(' · ');
      if (linea) {
        var cinta = document.createElement('div');
        cinta.className = 'ticker';
        var pista = document.createElement('div');
        pista.className = 'ticker__track';
        var pxs = { lenta: 40, normal: 80, rapida: 140 }[valor('velocidad')] || 80;
        pista.style.animationDuration = Math.max(4, Math.round(Math.max(1200, linea.length * 11) / pxs)) + 's';
        if (valor('direccion') === 'der_izq') { cinta.classList.add('ticker--der_izq'); }
        [false, true].forEach(function (copia) {
          var it = document.createElement('span');
          it.className = 'ticker__item';
          if (copia) { it.setAttribute('aria-hidden', 'true'); }
          it.textContent = linea;
          pista.appendChild(it);
        });
        cinta.appendChild(pista);
        cuerpo.appendChild(cinta);
      }
    } else if (texto) {
      var t = document.createElement('p');
      t.className = 'notice__text';
      texto.split('\n').forEach(function (linea, i) {
        if (i) { t.appendChild(document.createElement('br')); }
        t.appendChild(document.createTextNode(linea));
      });
      cuerpo.appendChild(t);
    }
    art.appendChild(cuerpo);
    destino.textContent = '';
    destino.appendChild(art);
  }

  // Direccion y velocidad solo aplican al carrusel: se muestran cuando ese formato esta elegido.
  function opcionesCarrusel() {
    var activo = valor('formato') === 'carrusel';
    ['direccion', 'velocidad'].forEach(function (n) {
      var campo = form.elements[n];
      if (campo && campo.closest('label')) { campo.closest('label').hidden = !activo; }
    });
  }

  form.addEventListener('input', pintar);
  form.addEventListener('change', function () { opcionesCarrusel(); pintar(); });
  opcionesCarrusel();
  pintar();
})();
