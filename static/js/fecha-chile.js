// Campos de fecha del panel en formato chileno DD-MM-AAAA. Se escribe solo con numeros (la
// mascara pone los guiones) o se elige en un calendario; el servidor traduce a fecha de la base
// de datos (ver FORMATOS_FECHA en sitio/forms.py).
(function () {
  'use strict';

  function mascara(texto) {
    var d = texto.replace(/\D/g, '').slice(0, 8);
    var partes = [d.slice(0, 2), d.slice(2, 4), d.slice(4)].filter(Boolean);
    return partes.join('-');
  }

  function iso(texto) {
    var m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(texto);
    return m ? m[3] + '-' + m[2] + '-' + m[1] : '';
  }

  function preparar(campo) {
    // Un valor ISO (o con barras) que venga del servidor se muestra en formato chileno.
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(campo.value);
    if (m) { campo.value = m[3] + '-' + m[2] + '-' + m[1]; }
    campo.value = campo.value.replace(/\//g, '-');

    campo.addEventListener('input', function (e) {
      if (e.inputType && e.inputType.indexOf('delete') === 0) { return; }
      campo.value = mascara(campo.value);
    });

    // Calendario nativo opcional: elige la fecha y la vuelca al campo de texto.
    var calendario = document.createElement('input');
    calendario.type = 'date';
    calendario.tabIndex = -1;
    calendario.setAttribute('aria-hidden', 'true');
    calendario.style.cssText = 'position:absolute;opacity:0;pointer-events:none;width:1px;height:1px';
    var boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'btn btn--small fecha-cl__boton';
    boton.textContent = 'Calendario';
    boton.setAttribute('aria-label', 'Elegir fecha en el calendario');
    boton.addEventListener('click', function () {
      calendario.value = iso(campo.value);
      if (calendario.showPicker) { calendario.showPicker(); } else { calendario.focus(); calendario.click(); }
    });
    calendario.addEventListener('change', function () {
      var f = /^(\d{4})-(\d{2})-(\d{2})$/.exec(calendario.value);
      if (f) {
        campo.value = f[3] + '-' + f[2] + '-' + f[1];
        campo.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    var envoltorio = document.createElement('div');
    envoltorio.className = 'fecha-cl';
    campo.parentNode.insertBefore(envoltorio, campo);
    envoltorio.appendChild(campo);
    envoltorio.appendChild(boton);
    envoltorio.appendChild(calendario);
  }

  Array.prototype.forEach.call(document.querySelectorAll('input[data-fecha-cl]'), preparar);
})();
