// Navbar management for authentication state & consistent navigation

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Ensure "Find Medicine" nav button is visible and navigates properly
    const findMediButtons = document.querySelectorAll('.find-medicine');
    findMediButtons.forEach(btn => {
        btn.style.display = '';
        btn.onclick = () => {
            const targetPage = window.location.pathname.includes('Medifinder') ? 'Medifinder.html' : 'FindMedi.html';
            window.location.href = targetPage;
        };
    });

    // 2. Check current authentication state
    try {
        const res = await API.getCurrentUser();
        const section2 = document.querySelector('.section2');
        const section3 = document.querySelector('.section3');

        if (res && res.authenticated && res.user) {
            const user = res.user;

            // If Pharmacy or Admin, provide quick link to their dashboard
            if (section2) {
                if (user.role === 'pharmacy' && !document.querySelector('.nav-dashboard')) {
                    const dashBtn = document.createElement('button');
                    dashBtn.className = 'pharmacies nav-dashboard';
                    dashBtn.textContent = 'Pharmacy Dashboard';
                    dashBtn.onclick = () => window.location.href = 'pharmacy-dashboard.html';
                    section2.appendChild(dashBtn);
                } else if (user.role === 'admin' && !document.querySelector('.nav-admin')) {
                    const adminBtn = document.createElement('button');
                    adminBtn.className = 'pharmacies nav-admin';
                    adminBtn.textContent = 'Admin Portal';
                    adminBtn.onclick = () => window.location.href = 'admin-dashboard.html';
                    section2.appendChild(adminBtn);
                }
            }

            // Update Section 3 (User badge & Logout)
            if (section3) {
                const displayName = user.full_name.split(' ')[0] || user.full_name;
                const roleBadge = user.role.charAt(0).toUpperCase() + user.role.slice(1);

                section3.innerHTML = `
                    <div style="display:flex; align-items:center; gap:8px; font-family:'Plus Jakarta Sans',sans-serif; font-size:0.85rem; font-weight:600; color:#0f172a; margin-right:5px;">
                        <span>👤 ${escapeHtml(displayName)}</span>
                        <span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:999px; font-size:0.75rem;">${roleBadge}</span>
                    </div>
                    <button class="login" id="nav-logout-btn" style="padding:0.45rem 1rem;">
                        Logout
                    </button>
                `;

                const logoutBtn = document.getElementById('nav-logout-btn');
                if (logoutBtn) {
                    logoutBtn.addEventListener('click', async () => {
                        try {
                            await API.logout();
                            window.location.href = 'HomePage.html';
                        } catch (err) {
                            console.error('Logout error:', err);
                            window.location.href = 'HomePage.html';
                        }
                    });
                }
            }
        }
    } catch (err) {
        console.warn('Navbar auth check failed:', err);
    }
});

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    })[m]);
}
