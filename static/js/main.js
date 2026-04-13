// Smart Student Planner — Main JavaScript

document.addEventListener('DOMContentLoaded', () => {
    // Animate stat values on dashboard
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(el => {
        const text = el.textContent;
        const num = parseFloat(text.replace(/[^0-9.]/g, ''));
        if (!isNaN(num)) {
            let start = 0;
            const duration = 1000;
            const step = num / (duration / 16);
            const timer = setInterval(() => {
                start += step;
                if (start >= num) {
                    el.textContent = text.replace(/[0-9.]+/, num.toFixed(1));
                    clearInterval(timer);
                } else {
                    el.textContent = text.replace(/[0-9.]+/, start.toFixed(1));
                }
            }, 16);
        }
    });

    // Animate progress bars
    const progressBars = document.querySelectorAll('.progress-fill');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.width = width;
        }, 100);
    });
});