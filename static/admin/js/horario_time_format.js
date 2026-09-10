// Formatea el campo "Hora salida" del admin insertando ":" en tiempo real
// mientras se escriben o borran digitos (ej. "0830" -> "08:30").
(function () {
  function formatHora(digits) {
    digits = digits.slice(0, 4);
    if (digits.length <= 2) return digits;
    return digits.slice(0, 2) + ':' + digits.slice(2);
  }

  function attach(input) {
    input.addEventListener('input', function () {
      var cursor = input.selectionStart;
      var before = input.value;
      var digits = before.replace(/\D/g, '');
      input.value = formatHora(digits);
      var newCursor = cursor + (input.value.length - before.length);
      input.setSelectionRange(Math.max(newCursor, 0), Math.max(newCursor, 0));
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input.vTimeField').forEach(attach);
  });
})();
