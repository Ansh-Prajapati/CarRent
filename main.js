// Auto-hide flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 500);
        });
    }, 5000);
});

// Add close button to alerts
document.querySelectorAll('.alert').forEach(alert => {
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '×';
    closeBtn.className = 'alert-close';
    closeBtn.onclick = function() {
        alert.remove();
    };
    alert.appendChild(closeBtn);
});

// Confirm delete actions
document.querySelectorAll('.confirm-delete').forEach(button => {
    button.addEventListener('click', function(e) {
        if (!confirm('Are you sure you want to delete this item?')) {
            e.preventDefault();
        }
    });
});

// Format currency
function formatCurrency(amount) {
    return '₹' + parseFloat(amount).toFixed(2);
}

// Format date
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

// Mobile menu toggle
const createMobileMenu = () => {
    const nav = document.querySelector('.nav-links');
    if (window.innerWidth <= 768) {
        const toggle = document.createElement('button');
        toggle.className = 'mobile-menu-toggle';
        toggle.innerHTML = '☰';
        toggle.style.cssText = `
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
            display: block;
            margin: 10px auto;
        `;

        const navContainer = document.querySelector('.nav-container');
        navContainer.insertBefore(toggle, nav);

        nav.style.display = 'none';

        toggle.addEventListener('click', () => {
            if (nav.style.display === 'none') {
                nav.style.display = 'flex';
                nav.style.flexDirection = 'column';
                toggle.innerHTML = '✕';
            } else {
                nav.style.display = 'none';
                toggle.innerHTML = '☰';
            }
        });
    }
};

// Run on load and resize
window.addEventListener('load', createMobileMenu);
window.addEventListener('resize', createMobileMenu);