document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.validity.valid) {
                this.style.borderColor = '#4ecdc4';
            } else if (this.value) {
                this.style.borderColor = '#ff6b6b';
            }
        });
    });
});
