// Formato automatico HH:MM en los campos de hora de /edit/ (inputs name="horas_<ruta>").
// Escucha 'input' en el documento, asi tambien cubre las filas que se agregan con JS.
// Al escribir solo deja pasar digitos que pueden formar una hora valida; al pegar o
// autocompletar interpreta "7:30", "0730" o "07.30". Si algo falla, el formulario sigue
// funcionando: el servidor valida igualmente el formato.
(function (root) {
  'use strict';

  var SELECTOR = 'input[name^="horas_"]';

  function pad2(n) { return ('0' + n).slice(-2); }

  // Digitos validos de una hora (maximo 4). Un primer digito 3-9 se completa ("7" -> "07"),
  // y se descartan los que no forman hora ni minutos reales (24-29 h, 60-99 min).
  function limpiarDigitos(texto) {
    var d = String(texto).replace(/\D/g, '');
    var res = [];
    for (var i = 0; i < d.length && res.length < 4; i++) {
      var c = d.charAt(i);
      var pos = res.length;
      if (pos === 0 && c > '2') { res.push('0', c); }
      else if (pos === 1 && res[0] === '2' && c > '3') { continue; }
      else if (pos === 2 && c > '5') { continue; }
      else { res.push(c); }
    }
    return res.join('');
  }

  // "12" se muestra como "12:" al escribir, pero como "12" al borrar, para poder seguir borrando.
  function formatear(digitos, borrando) {
    if (digitos.length < 2) { return digitos; }
    if (digitos.length === 2) { return borrando ? digitos : digitos + ':'; }
    return digitos.slice(0, 2) + ':' + digitos.slice(2);
  }

  // Texto pegado o autocompletado completo ("7:30", "07.30", "0730") -> 4 digitos, o null.
  function interpretarCompleto(texto) {
    var m = /^\s*(\d{1,2})\s*[:.,hH]\s*(\d{1,2})\s*$/.exec(texto) || /^\s*(\d{2})(\d{2})\s*$/.exec(texto);
    return m ? pad2(m[1]) + pad2(m[2]) : null;
  }

  function soloDigitos(texto) { return String(texto).replace(/\D/g, ''); }

  // Calcula el nuevo valor y la posicion del cursor.
  //   valor: texto actual del campo; cursor: selectionStart; tipo: inputType del evento;
  //   dato: event.data (el caracter tecleado, si lo hay); previo: valor antes del evento.
  function normalizar(valor, cursor, tipo, dato, previo) {
    tipo = tipo || '';
    var borrando = tipo.indexOf('delete') === 0;
    var escribiendo = tipo === 'insertText' || tipo === 'insertCompositionText';

    if (borrando) {
      // Al borrar no se valida ni se rellena: solo se vuelve a poner el ":" en su sitio.
      var d = soloDigitos(valor).slice(0, 4);
      var n = soloDigitos(valor.slice(0, cursor)).length;
      // Si lo borrado fue un ":" con minutos detras (los digitos siguen iguales), se borra el
      // digito vecino. Un ":" final ("07:") se quita solo.
      var iDos = previo ? previo.indexOf(':') : -1;
      if (iDos !== -1 && previo.length > iDos + 1 && valor.indexOf(':') === -1 && soloDigitos(previo) === soloDigitos(valor)) {
        if (tipo === 'deleteContentForward') { d = d.slice(0, n) + d.slice(n + 1); }
        else if (n > 0) { d = d.slice(0, n - 1) + d.slice(n); n -= 1; }
      }
      var v = formatear(d, true);
      return { valor: v, cursor: Math.max(0, Math.min(n <= 2 ? n : n + 1, v.length)) };
    }

    if (!borrando && !escribiendo) {
      var completo = interpretarCompleto(valor);
      if (completo) {
        var v = completo.slice(0, 2) + ':' + completo.slice(2);
        return { valor: v, cursor: v.length };
      }
    }

    // Un separador tras un solo digito completa la hora: "7" + ":" -> "07:"
    var digitosActuales = soloDigitos(valor);
    if (dato && /^[:.,]$/.test(dato) && digitosActuales.length === 1) {
      var h = pad2(digitosActuales) + ':';
      return { valor: h, cursor: h.length };
    }

    var nuevo = formatear(limpiarDigitos(valor), false);
    var antes = limpiarDigitos(valor.slice(0, cursor)).length;
    var pos = antes <= 2 ? antes : antes + 1;
    if (antes === 2 && nuevo.length > 2) { pos = 3; }
    return { valor: nuevo, cursor: Math.max(0, Math.min(pos, nuevo.length)) };
  }

  // Valor de cada campo antes del ultimo evento: hace falta para saber que se borro el ":".
  var ultimo = typeof WeakMap !== 'undefined' ? new WeakMap() : null;

  function coincide(e) {
    return e.target && e.target.matches && e.target.matches(SELECTOR);
  }

  // 'beforeinput' y 'keydown' corren antes de cada cambio, con el valor aun intacto;
  // 'focusin' cubre el valor inicial. Se usan los tres por compatibilidad entre navegadores.
  function recordarValor(e) {
    if (ultimo && coincide(e)) { ultimo.set(e.target, e.target.value); }
  }

  function alEscribir(e) {
    if (!coincide(e)) { return; }
    var input = e.target;
    var cursor = input.selectionStart;
    if (cursor === null || cursor === undefined) { cursor = input.value.length; }
    var previo = ultimo ? ultimo.get(input) : undefined;
    var r = normalizar(input.value, cursor, e.inputType, e.data, previo);
    if (r.valor !== input.value) {
      input.value = r.valor;
      try { input.setSelectionRange(r.cursor, r.cursor); } catch (err) { /* tipo sin seleccion */ }
    }
    if (ultimo) { ultimo.set(input, input.value); }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('focusin', recordarValor);
    document.addEventListener('beforeinput', recordarValor);
    document.addEventListener('keydown', recordarValor);
    document.addEventListener('input', alEscribir);
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { limpiarDigitos: limpiarDigitos, formatear: formatear, normalizar: normalizar, interpretarCompleto: interpretarCompleto };
  }
}(this));
