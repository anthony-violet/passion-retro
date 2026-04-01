document.addEventListener('DOMContentLoaded', () => {
    const pixelFrames = document.querySelectorAll('.cadre-pixel-art');

    pixelFrames.forEach(frame => {
        const img = frame.querySelector('img');
        if (img && !img.dataset.pixelated) {
            img.dataset.pixelated = 'true';

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');

            const targetSize = 88;
            canvas.width = targetSize;
            canvas.height = targetSize;

            img.onload = () => {
                ctx.imageSmoothingEnabled = false;
                ctx.drawImage(img, 0, 0, targetSize, targetSize);

                const pixelatedImg = document.createElement('img');
                pixelatedImg.src = canvas.toDataURL('image/png');
                pixelatedImg.style.width = '100%';
                pixelatedImg.style.height = '100%';
                pixelatedImg.style.imageRendering = 'pixelated';
                pixelatedImg.style.imageRendering = 'crisp-edges';

                img.replaceWith(pixelatedImg);
            };

            if (img.complete) {
                img.onload();
            }
        }
    });
});
