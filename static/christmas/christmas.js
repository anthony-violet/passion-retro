/* Décor de Noël : neige, guirlande et bonnet. Chargé uniquement pendant la période. */
(function () {
    'use strict';

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var HAT_SVG = '<svg viewBox="0 0 64 56" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<path d="M6 44 C14 18 30 4 50 8 C46 18 46 30 52 40 Z" fill="#d62828"/>' +
        '<rect x="2" y="40" width="54" height="12" rx="6" fill="#fff"/>' +
        '<circle cx="54" cy="10" r="7" fill="#fff"/></svg>';

    function addGarland() {
        var host = document.querySelector('.banner-container');
        var garland = document.createElement('ul');
        garland.className = 'xmas-garland';
        garland.setAttribute('aria-hidden', 'true');
        var count = Math.max(12, Math.round(window.innerWidth / 42));
        for (var i = 0; i < count; i++) garland.appendChild(document.createElement('li'));
        if (host) {
            if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
            host.appendChild(garland);
        } else {
            garland.classList.add('xmas-garland--page');
            document.body.appendChild(garland);
        }
    }

    function addHat() {
        var title = document.querySelector('.banner-container .rpg-title, .banner-container .banner-text');
        var host = document.querySelector('.banner-container');
        if (!title || !host) return;
        var hat = document.createElement('span');
        hat.className = 'xmas-hat';
        hat.innerHTML = HAT_SVG;
        host.appendChild(hat);

        function place() {
            var t = title.getBoundingClientRect();
            var h = host.getBoundingClientRect();
            if (!t.width) { hat.style.display = 'none'; return; }
            hat.style.display = '';
            hat.style.left = (t.left - h.left - hat.offsetWidth * 0.35) + 'px';
            // Jamais au-dessus du bord de la bannière, sinon le bonnet est coupé.
            hat.style.top = Math.max(0, t.top - h.top - hat.offsetHeight * 0.6) + 'px';
        }
        place();
        window.addEventListener('resize', place);
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(place);
    }

    function addSnow() {
        var canvas = document.createElement('canvas');
        canvas.className = 'xmas-snow';
        canvas.setAttribute('aria-hidden', 'true');
        document.body.appendChild(canvas);
        var ctx = canvas.getContext('2d');
        if (!ctx) return;

        var flakes = [];
        var width = 0, height = 0, ratio = window.devicePixelRatio || 1;
        var total = reduceMotion ? 35 : 60;

        function resize() {
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = width * ratio;
            canvas.height = height * ratio;
            ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        }

        function flake(randomY) {
            return {
                x: Math.random() * width,
                y: randomY ? Math.random() * height : -10,
                r: 1 + Math.random() * 2.6,
                speed: 0.4 + Math.random() * 1.1,
                drift: Math.random() * Math.PI * 2,
                alpha: 0.5 + Math.random() * 0.5
            };
        }

        function draw() {
            ctx.clearRect(0, 0, width, height);
            for (var i = 0; i < flakes.length; i++) {
                var f = flakes[i];
                ctx.beginPath();
                ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(255,255,255,' + f.alpha + ')';
                ctx.shadowColor = 'rgba(120,160,200,.6)';
                ctx.shadowBlur = 2;
                ctx.fill();
            }
        }

        function step() {
            for (var i = 0; i < flakes.length; i++) {
                var f = flakes[i];
                f.drift += 0.01;
                f.y += f.speed;
                f.x += Math.sin(f.drift) * 0.5;
                if (f.y > height + 5) flakes[i] = flake(false);
                if (f.x > width + 5) f.x = -5;
                if (f.x < -5) f.x = width + 5;
            }
            draw();
            if (!document.hidden) frame = requestAnimationFrame(step);
            else frame = null;
        }

        resize();
        for (var i = 0; i < total; i++) flakes.push(flake(true));
        window.addEventListener('resize', resize);

        if (reduceMotion) { draw(); window.addEventListener('resize', draw); return; }

        var frame = requestAnimationFrame(step);
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden && !frame) frame = requestAnimationFrame(step);
        });
    }

    function bindToggle() {
        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.classList || !form.classList.contains('xmas-toggle-form')) return;
            event.preventDefault();
            fetch(form.action, {
                method: 'POST', body: new FormData(form), credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }).then(function (r) { if (!r.ok) throw new Error(); window.location.reload(); })
              .catch(function () { form.submit(); });
        });
    }

    bindToggle();
    if (!document.body.classList.contains('xmas')) return;
    addSnow();
    addGarland();
    addHat();
})();
