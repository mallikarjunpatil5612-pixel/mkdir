// Main Frontend Interactions
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 400);
        }, 5000);
    });

    // Handle AJAX toggle favourites if present
    document.querySelectorAll('.btn-fav-toggle').forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const propId = button.getAttribute('data-id');
            if (!propId) return;

            try {
                const response = await fetch(`/favourites/toggle/${propId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }

                const data = await response.json();
                if (data.success) {
                    if (data.is_favourite) {
                        button.innerHTML = '❤️ Saved in Favourites';
                        button.classList.add('btn-primary');
                        button.classList.remove('btn-outline');
                    } else {
                        button.innerHTML = '🤍 Add to Favourites';
                        button.classList.remove('btn-primary');
                        button.classList.add('btn-outline');
                    }
                }
            } catch (err) {
                console.error('Error toggling favourite:', err);
            }
        });
    });
});

