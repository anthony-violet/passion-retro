/**
 * ============================================================
 * Thème "Années 80" — Passion Rétro
 * Effets JavaScript : étoiles, scintillements néon, cursor trail
 * ============================================================
 */

(function () {
    'use strict';

    /* ────────────────────────────────────────────────
       1. ÉTOILES FILANTES EN ARRIÈRE-PLAN
       Génère un canvas plein-écran avec des étoiles
       qui glissent de droite à gauche (effet hyperspace)
    ────────────────────────────────────────────────── */
    function initStarfield() {
        const canvas = document.createElement('canvas');
        canvas.id = 'retro80s-starfield';
        canvas.style.cssText = [
            'position:fixed',
            'top:0',
            'left:0',
            'width:100%',
            'height:100%',
            'pointer-events:none',
            'z-index:0',
            'opacity:0.55',
        ].join(';');

        document.body.insertBefore(canvas, document.body.firstChild);

        const ctx = canvas.getContext('2d');
        let W = 0, H = 0;
        const STAR_COUNT = 160;
        const stars = [];

        const COLORS = [
            '#ffffff', '#ff00ff', '#00ffff',
            '#cc88ff', '#ff66ff', '#88ccff',
        ];

        function resize() {
            W = canvas.width  = window.innerWidth;
            H = canvas.height = window.innerHeight;
        }

        function makestar() {
            return {
                x: Math.random() * W,
                y: Math.random() * H,
                r: Math.random() * 1.4 + 0.2,
                speed: Math.random() * 0.6 + 0.15,
                alpha: Math.random() * 0.7 + 0.3,
                color: COLORS[Math.floor(Math.random() * COLORS.length)],
                twinkleSpeed: Math.random() * 0.04 + 0.01,
                twinklePhase: Math.random() * Math.PI * 2,
            };
        }

        function init() {
            resize();
            stars.length = 0;
            for (let i = 0; i < STAR_COUNT; i++) stars.push(makestar());
        }

        let lastTime = 0;
        function draw(ts) {
            const dt = Math.min(ts - lastTime, 50);
            lastTime = ts;

            ctx.clearRect(0, 0, W, H);

            for (const s of stars) {
                s.twinklePhase += s.twinkleSpeed;
                const alpha = s.alpha * (0.6 + 0.4 * Math.sin(s.twinklePhase));

                // Traîne lumineuse
                ctx.beginPath();
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(s.x + s.speed * 8, s.y);
                ctx.strokeStyle = s.color;
                ctx.globalAlpha = alpha * 0.25;
                ctx.lineWidth = s.r * 0.5;
                ctx.stroke();

                // Étoile principale
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
                ctx.fillStyle = s.color;
                ctx.globalAlpha = alpha;
                ctx.fill();

                // Déplacement (glisse légèrement vers la gauche)
                s.x -= s.speed * (dt / 16);
                if (s.x < -4) {
                    s.x = W + 4;
                    s.y = Math.random() * H;
                }
            }

            ctx.globalAlpha = 1;
            requestAnimationFrame(draw);
        }

        window.addEventListener('resize', resize);
        init();
        requestAnimationFrame(draw);
    }

    /* ────────────────────────────────────────────────
       2. EFFET SCANLINES CRT (overlay CSS dynamique)
       Crée une légère ondulation scanline sur la page
    ────────────────────────────────────────────────── */
    function initScanlines() {
        const overlay = document.createElement('div');
        overlay.id = 'retro80s-scanlines';
        overlay.style.cssText = [
            'position:fixed',
            'top:0',
            'left:0',
            'width:100%',
            'height:100%',
            'pointer-events:none',
            'z-index:9997',
            'background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.08) 3px,rgba(0,0,0,0.08) 4px)',
            'animation:scanline-move 8s linear infinite',
        ].join(';');

        // Injection keyframes dans <style>
        const style = document.createElement('style');
        style.textContent = `
            @keyframes scanline-move {
                0%   { background-position: 0 0; }
                100% { background-position: 0 80px; }
            }
            @keyframes neon-flicker-element {
                0%,85%,100%  { opacity: 1; }
                87%          { opacity: 0.7; }
                89%          { opacity: 1; }
                91%          { opacity: 0.5; }
                93%          { opacity: 1; }
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(overlay);
    }

    /* ────────────────────────────────────────────────
       3. CURSEUR NÉON TRAIL
       Trace une traîne colorée derrière le curseur
    ────────────────────────────────────────────────── */
    function initCursorTrail() {
        const TRAIL_LENGTH = 14;
        const trail = [];

        const TRAIL_COLORS = [
            '#ff00ff', '#ee00ee', '#cc00cc',
            '#aa00cc', '#8800bb', '#6600aa',
            '#440088', '#330066', '#220044',
            '#00ffff', '#00cccc', '#009999',
            '#006666', '#004444',
        ];

        // Créer les particules de traîne
        for (let i = 0; i < TRAIL_LENGTH; i++) {
            const dot = document.createElement('div');
            const size = Math.max(2, 10 - i * 0.6);
            dot.style.cssText = [
                'position:fixed',
                'pointer-events:none',
                'border-radius:50%',
                `width:${size}px`,
                `height:${size}px`,
                `background:${TRAIL_COLORS[i] || '#220044'}`,
                `box-shadow:0 0 ${size * 2}px ${TRAIL_COLORS[i] || '#220044'}`,
                'z-index:9999',
                'transition:opacity 0.1s',
                'opacity:0',
                'transform:translate(-50%,-50%)',
            ].join(';');
            document.body.appendChild(dot);
            trail.push({ el: dot, x: -100, y: -100 });
        }

        let mx = -100, my = -100;

        document.addEventListener('mousemove', (e) => {
            mx = e.clientX;
            my = e.clientY;
        });

        function animateTrail() {
            // Décaler les positions vers l'arrière
            for (let i = TRAIL_LENGTH - 1; i > 0; i--) {
                trail[i].x = trail[i - 1].x;
                trail[i].y = trail[i - 1].y;
            }
            trail[0].x = mx;
            trail[0].y = my;

            // Mettre à jour chaque dot
            for (let i = 0; i < TRAIL_LENGTH; i++) {
                const t = trail[i];
                t.el.style.left  = t.x + 'px';
                t.el.style.top   = t.y + 'px';
                t.el.style.opacity = (1 - i / TRAIL_LENGTH) * 0.85;
            }

            requestAnimationFrame(animateTrail);
        }

        animateTrail();
    }

    /* ────────────────────────────────────────────────
       4. EFFET NÉON FLICKER sur les titres h2
       Fait clignoter aléatoirement quelques titres
    ────────────────────────────────────────────────── */
    function initNeonFlicker() {
        function flicker(el) {
            const delay   = 3000 + Math.random() * 8000;
            const flashes = 2 + Math.floor(Math.random() * 3);

            setTimeout(() => {
                let count = 0;
                const interval = setInterval(() => {
                    el.style.opacity = (count % 2 === 0) ? '0.3' : '1';
                    count++;
                    if (count >= flashes * 2) {
                        clearInterval(interval);
                        el.style.opacity = '1';
                        flicker(el);
                    }
                }, 80);
            }, delay);
        }

        // Appliquer aux titres h2 des containers
        const titles = document.querySelectorAll('.container h2, .menu h2');
        titles.forEach((el, i) => {
            // Décaler pour que tous ne clignotent pas en même temps
            setTimeout(() => flicker(el), i * 700);
        });
    }

    /* ────────────────────────────────────────────────
       5. COMPTEUR VHS ANIMÉ dans le banner
       Met à jour le "timecode" VHS si présent
    ────────────────────────────────────────────────── */
    function initVhsCounter() {
        const banner = document.querySelector('.banner-container');
        if (!banner) return;

        // Chercher un éventuel élément timecode (sinon la pseudo-décoration CSS suffit)
        const tc = banner.querySelector('[data-timecode]');
        if (!tc) return;

        let frames = 0;
        setInterval(() => {
            frames++;
            const s  = Math.floor(frames / 25) % 60;
            const m  = Math.floor(frames / (25 * 60)) % 60;
            const h  = Math.floor(frames / (25 * 3600)) % 24;
            const fr = frames % 25;
            tc.textContent =
                String(h).padStart(2, '0') + ':' +
                String(m).padStart(2, '0') + ':' +
                String(s).padStart(2, '0') + ':' +
                String(fr).padStart(2, '0');
        }, 40);
    }

    /* ────────────────────────────────────────────────
       6. SONS RÉTRO (optionnel, via Web Audio API)
       Bip léger sur click de bouton
    ────────────────────────────────────────────────── */
    function initRetroBeeps() {
        let audioCtx = null;

        function getCtx() {
            if (!audioCtx) {
                try {
                    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                } catch (e) {
                    return null;
                }
            }
            return audioCtx;
        }

        function beep(freq, type, duration, vol) {
            const ctx = getCtx();
            if (!ctx) return;

            const osc  = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.type      = type || 'square';
            osc.frequency.setValueAtTime(freq || 440, ctx.currentTime);
            gain.gain.setValueAtTime(vol || 0.04, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (duration || 0.08));

            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + (duration || 0.08));
        }

        // Bip sur les boutons principaux
        document.addEventListener('click', (e) => {
            const el = e.target;
            if (
                el.tagName === 'BUTTON' ||
                el.tagName === 'A' ||
                el.type === 'submit' ||
                el.classList.contains('btn')
            ) {
                beep(880, 'square', 0.05, 0.03);
            }
        });

        // Bip différent sur les liens de menu
        document.addEventListener('mouseover', (e) => {
            if (e.target.closest('.menu ul li a') || e.target.closest('.menu-horizontal a')) {
                beep(1320, 'sine', 0.03, 0.015);
            }
        });
    }

    /* ────────────────────────────────────────────────
       INITIALISATION
    ────────────────────────────────────────────────── */
    function init() {
        initStarfield();
        initScanlines();
        initCursorTrail();
        initNeonFlicker();
        initVhsCounter();
        initRetroBeeps();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
