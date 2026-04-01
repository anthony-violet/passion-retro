/**
 * ============================================================
 * Thème VHS — Passion Rétro
 * Effets JavaScript : glitch cassettes, tracking distortion,
 * compteur VHS, aberrations chromatiques, scanlines
 * ============================================================
 */
(function () {
    'use strict';

    /* ────────────────────────────────────────────────────────
       1. GLITCH ALÉATOIRE SUR LES CASSETTES
       Simule des artefacts VHS sur les cartes forum home
    ────────────────────────────────────────────────────────── */
    function initCassetteGlitch() {
        const cassettes = document.querySelectorAll('.vhs-cassette');
        if (!cassettes.length) return;

        cassettes.forEach((el) => {
            scheduleGlitch(el);
        });

        function scheduleGlitch(el) {
            const delay = 4000 + Math.random() * 14000;
            setTimeout(() => {
                doGlitch(el);
                scheduleGlitch(el);
            }, delay);
        }

        function doGlitch(el) {
            const lines = 2 + Math.floor(Math.random() * 4);
            const fragments = [];

            for (let i = 0; i < lines; i++) {
                const div = document.createElement('div');
                const top  = Math.random() * 90;
                const h    = 1 + Math.random() * 6;
                const shift = (Math.random() - 0.5) * 12;
                const color = Math.random() > 0.5
                    ? `rgba(0,229,255,${0.15 + Math.random() * 0.25})`
                    : `rgba(255,0,110,${0.15 + Math.random() * 0.2})`;

                div.style.cssText = [
                    'position:absolute',
                    `top:${top}%`,
                    'left:0', 'right:0',
                    `height:${h}px`,
                    `background:${color}`,
                    `transform:translateX(${shift}px)`,
                    'pointer-events:none',
                    `z-index:10`,
                    'transition:opacity 0.05s',
                ].join(';');

                el.style.position = 'relative';
                el.appendChild(div);
                fragments.push(div);
            }

            // Durée du glitch : 80–200ms
            const duration = 80 + Math.random() * 120;
            setTimeout(() => {
                fragments.forEach(d => {
                    d.style.opacity = '0';
                    setTimeout(() => d.remove(), 60);
                });
            }, duration);
        }
    }

    /* ────────────────────────────────────────────────────────
       2. EFFET "TRACKING" SUR LES LIGNES DU GUIDE TV
       Décalage horizontal aléatoire au survol
    ────────────────────────────────────────────────────────── */
    function initTrackingEffect() {
        const rows = document.querySelectorAll('.vhs-guide__row');
        if (!rows.length) return;

        rows.forEach((row) => {
            row.addEventListener('mouseenter', () => {
                // 30% de chance de déclencher une petite distorsion
                if (Math.random() > 0.7) {
                    const shift = (Math.random() - 0.5) * 4;
                    row.style.transition = 'transform 0.05s';
                    row.style.transform = `translateX(${shift}px)`;
                    setTimeout(() => {
                        row.style.transform = 'translateX(0)';
                        setTimeout(() => { row.style.transition = ''; }, 100);
                    }, 80);
                }
            });
        });
    }

    /* ────────────────────────────────────────────────────────
       3. COMPTEUR VHS ANIMÉ dans la barre de lecture
       Simule un compteur de cassette qui défile
    ────────────────────────────────────────────────────────── */
    function initVhsCounter() {
        const counter = document.getElementById('vhs-post-counter');
        if (!counter) return;

        let frames = 0;
        const interval = setInterval(() => {
            frames++;
            const s  = Math.floor(frames / 25) % 60;
            const m  = Math.floor(frames / (25 * 60)) % 60;
            const h  = Math.floor(frames / (25 * 3600)) % 10;
            const fr = frames % 25;
            counter.textContent =
                `0${h}:` +
                String(m).padStart(2, '0') + ':' +
                String(s).padStart(2, '0') + '.' +
                String(fr).padStart(2, '0');
        }, 40);

        // Arrêt propre si on quitte la page
        window.addEventListener('beforeunload', () => clearInterval(interval));
    }

    /* ────────────────────────────────────────────────────────
       4. ABERRATION CHROMATIQUE SUR LE TITRE DE LECTURE
       Décale légèrement les couches rouge/cyan du titre
    ────────────────────────────────────────────────────────── */
    function initChromaticAberration() {
        const title = document.querySelector('.vhs-playback-title');
        if (!title) return;

        const text = title.textContent;
        title.innerHTML = '';
        title.style.position = 'relative';
        title.style.display = 'inline-block';

        // Couche cyan (décalée à gauche)
        const cyan = document.createElement('span');
        cyan.textContent = text;
        cyan.style.cssText = [
            'position:absolute',
            'top:0', 'left:0',
            'color:#00e5ff',
            'opacity:0.5',
            'transform:translateX(-2px)',
            'mix-blend-mode:screen',
            'pointer-events:none',
            'clip-path:inset(0 0 50% 0)',
        ].join(';');

        // Couche rose (décalée à droite)
        const pink = document.createElement('span');
        pink.textContent = text;
        pink.style.cssText = [
            'position:absolute',
            'top:0', 'left:0',
            'color:#ff006e',
            'opacity:0.5',
            'transform:translateX(2px)',
            'mix-blend-mode:screen',
            'pointer-events:none',
            'clip-path:inset(50% 0 0 0)',
        ].join(';');

        // Couche principale
        const main = document.createElement('span');
        main.textContent = text;
        main.style.cssText = ['position:relative', 'z-index:1'].join(';');

        title.appendChild(cyan);
        title.appendChild(pink);
        title.appendChild(main);

        // Animation subtile de l'aberration
        let t = 0;
        function tick() {
            t += 0.03;
            const cx = -2 + Math.sin(t * 0.7) * 1.5;
            const px =  2 + Math.sin(t * 0.9) * 1.5;
            cyan.style.transform = `translateX(${cx}px)`;
            pink.style.transform = `translateX(${px}px)`;
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    /* ────────────────────────────────────────────────────────
       5. EFFET "PERTE DE SIGNAL" aléatoire sur les segments
       Fait clignoter brièvement un post comme une perte VHS
    ────────────────────────────────────────────────────────── */
    function initSignalLoss() {
        const segments = document.querySelectorAll('.vhs-segment');
        if (!segments.length) return;

        function scheduleSignalLoss(el) {
            const delay = 8000 + Math.random() * 25000;
            setTimeout(() => {
                triggerSignalLoss(el);
                scheduleSignalLoss(el);
            }, delay);
        }

        function triggerSignalLoss(el) {
            // Séquence : flash blanc → déformation → retour normal
            const steps = [
                { filter: 'brightness(1.8) contrast(0.6)', transform: 'skewX(0.5deg)' },
                { filter: 'brightness(0.4) contrast(2)',   transform: 'skewX(-0.3deg) translateX(3px)' },
                { filter: 'brightness(1.2)',               transform: 'skewX(0.2deg)' },
                { filter: '',                              transform: '' },
            ];

            let i = 0;
            const run = () => {
                if (i >= steps.length) {
                    el.style.filter    = '';
                    el.style.transform = '';
                    return;
                }
                el.style.filter    = steps[i].filter;
                el.style.transform = steps[i].transform;
                i++;
                setTimeout(run, 60 + Math.random() * 80);
            };
            run();
        }

        segments.forEach((el, idx) => {
            // Décaler chaque segment pour ne pas tous glitcher en même temps
            setTimeout(() => scheduleSignalLoss(el), idx * 1200);
        });
    }

    /* ────────────────────────────────────────────────────────
       6. SCANLINES ANIMÉES superposées sur la page entière
       Légère bande de luminosité qui descend (like a TV beam)
    ────────────────────────────────────────────────────────── */
    function initScanBeam() {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes vhs-scan-beam {
                0%   { top: -4%; }
                100% { top: 104%; }
            }
            #vhs-scan-beam {
                position: fixed;
                left: 0; right: 0;
                height: 60px;
                background: linear-gradient(
                    to bottom,
                    transparent 0%,
                    rgba(0, 229, 255, 0.022) 30%,
                    rgba(0, 229, 255, 0.018) 50%,
                    transparent 100%
                );
                pointer-events: none;
                z-index: 9998;
                animation: vhs-scan-beam 6s linear infinite;
            }
        `;
        document.head.appendChild(style);

        const beam = document.createElement('div');
        beam.id = 'vhs-scan-beam';
        document.body.appendChild(beam);
    }

    /* ────────────────────────────────────────────────────────
       7. INDICATEUR "TAPE" dans les cassettes du store
       Anime la bobine visible dans chaque cassette (::before)
    ────────────────────────────────────────────────────────── */
    function initCassetteReels() {
        const injectStyle = document.createElement('style');
        injectStyle.textContent = `
            .vhs-cassette:hover .vhs-cassette__body::before {
                background: radial-gradient(
                    circle at 40% 50%, #003040 0%, #001520 40%, #050505 100%
                ) !important;
                box-shadow: inset 0 0 6px rgba(0,229,255,0.15),
                            4px 0 0 2px #050505,
                            12px 0 0 2px #050505,
                            4px 0 0 3px rgba(0,229,255,0.1),
                            12px 0 0 3px rgba(0,229,255,0.1) !important;
            }
        `;
        document.head.appendChild(injectStyle);
    }

    /* ────────────────────────────────────────────────────────
       INITIALISATION
    ────────────────────────────────────────────────────────── */
    function init() {
        initScanBeam();
        initCassetteGlitch();
        initTrackingEffect();
        initVhsCounter();
        initChromaticAberration();
        initSignalLoss();
        initCassetteReels();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
