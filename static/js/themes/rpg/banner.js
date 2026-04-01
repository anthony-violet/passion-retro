(function() {
    'use strict';

    const canvas = document.getElementById('rpg-stars-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width, height;
    let stars = [];
    let shootingStars = [];
    let gaiaAngle = 0;
    let animationId;

    const STAR_COUNT = 150;
    const SHOOTING_STAR_CHANCE = 0.002;

    function resize() {
        const container = canvas.parentElement;
        width = container.offsetWidth;
        height = container.offsetHeight;
        canvas.width = width;
        canvas.height = height;
        initStars();
    }

    function initStars() {
        stars = [];
        for (let i = 0; i < STAR_COUNT; i++) {
            stars.push({
                x: Math.random() * width,
                y: Math.random() * height * 0.7,
                size: Math.random() * 1.5 + 0.5,
                brightness: Math.random() * 0.5 + 0.5,
                twinkleSpeed: Math.random() * 0.02 + 0.01,
                twinkleOffset: Math.random() * Math.PI * 2,
                color: Math.random() > 0.7 ? 'blue' : (Math.random() > 0.5 ? 'gold' : 'white')
            });
        }
    }

    function drawGaia() {
        const gaiaX = width * 0.75;
        const gaiaY = height * 0.5;
        const gaiaRadius = Math.min(width, height) * 0.18;

        ctx.save();
        ctx.globalAlpha = 0.35;
        
        const gradient = ctx.createRadialGradient(
            gaiaX - gaiaRadius * 0.3, gaiaY - gaiaRadius * 0.3, 0,
            gaiaX, gaiaY, gaiaRadius
        );
        gradient.addColorStop(0, 'rgba(100, 180, 255, 0.9)');
        gradient.addColorStop(0.2, 'rgba(80, 160, 240, 0.8)');
        gradient.addColorStop(0.5, 'rgba(60, 140, 200, 0.6)');
        gradient.addColorStop(0.8, 'rgba(40, 100, 160, 0.4)');
        gradient.addColorStop(1, 'rgba(20, 60, 120, 0.1)');

        ctx.beginPath();
        ctx.arc(gaiaX, gaiaY, gaiaRadius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        ctx.globalAlpha = 0.15;
        ctx.beginPath();
        ctx.arc(gaiaX, gaiaY, gaiaRadius * 1.15, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(100, 180, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.restore();
    }

    function drawStars() {
        const time = Date.now() * 0.001;

        stars.forEach(star => {
            const twinkle = Math.sin(time * star.twinkleSpeed * 10 + star.twinkleOffset) * 0.3 + 0.7;
            const alpha = star.brightness * twinkle;

            ctx.beginPath();
            ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);

            if (star.color === 'blue') {
                ctx.fillStyle = `rgba(150, 180, 255, ${alpha})`;
            } else if (star.color === 'gold') {
                ctx.fillStyle = `rgba(255, 220, 100, ${alpha})`;
            } else {
                ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
            }
            ctx.fill();

            if (star.size > 1.2) {
                ctx.beginPath();
                ctx.arc(star.x, star.y, star.size * 1.5, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.15})`;
                ctx.fill();
            }
        });
    }

    function updateShootingStars() {
        if (Math.random() < SHOOTING_STAR_CHANCE) {
            shootingStars.push({
                x: Math.random() * width * 0.5,
                y: Math.random() * height * 0.3,
                speed: Math.random() * 3 + 2,
                angle: Math.PI / 4,
                length: Math.random() * 50 + 30,
                life: 1
            });
        }

        shootingStars = shootingStars.filter(star => {
            star.x += Math.cos(star.angle) * star.speed;
            star.y += Math.sin(star.angle) * star.speed;
            star.life -= 0.015;
            return star.life > 0;
        });
    }

    function drawShootingStars() {
        shootingStars.forEach(star => {
            const gradient = ctx.createLinearGradient(
                star.x, star.y,
                star.x - Math.cos(star.angle) * star.length,
                star.y - Math.sin(star.angle) * star.length
            );
            gradient.addColorStop(0, `rgba(255, 255, 255, ${star.life})`);
            gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

            ctx.beginPath();
            ctx.moveTo(star.x, star.y);
            ctx.lineTo(
                star.x - Math.cos(star.angle) * star.length,
                star.y - Math.sin(star.angle) * star.length
            );
            ctx.strokeStyle = gradient;
            ctx.lineWidth = 2;
            ctx.stroke();
        });
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);

        drawGaia();
        drawStars();
        updateShootingStars();
        drawShootingStars();

        animationId = requestAnimationFrame(animate);
    }

    function init() {
        resize();
        animate();
        window.addEventListener('resize', resize);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
