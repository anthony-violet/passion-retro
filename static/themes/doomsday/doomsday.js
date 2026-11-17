/* Édition spéciale Doomsday : compte à rebours vivant de l'encart d'accueil.
   Le serveur affiche déjà les jours ; ce script ajoute heures, minutes, secondes. */
(function () {
    "use strict";
    var box = document.querySelector(".dd-countdown[data-release]");
    if (!box) return;
    var units = {};
    ["d", "h", "m", "s"].forEach(function (u) { units[u] = box.querySelector('[data-unit="' + u + '"]'); });
    var parts = box.getAttribute("data-release").split("-");
    var target = new Date(+parts[0], +parts[1] - 1, +parts[2]).getTime(); // minuit, heure locale
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    function tick() {
        var s = Math.max(0, Math.floor((target - Date.now()) / 1000));
        units.d.textContent = Math.floor(s / 86400);
        units.h.textContent = pad(Math.floor(s % 86400 / 3600));
        units.m.textContent = pad(Math.floor(s % 3600 / 60));
        units.s.textContent = pad(s % 60);
        if (s > 0) setTimeout(tick, 1000 - Date.now() % 1000);
    }
    tick();
})();
