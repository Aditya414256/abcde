// Navbar management for authentication state & consistent navigation

document.addEventListener('DOMContentLoaded', async () => {
    // Check current authentication state
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
                } else if (user.role === 'customer' && !document.querySelector('.nav-orders')) {
                    const ordersBtn = document.createElement('button');
                    ordersBtn.className = 'pharmacies nav-orders';
                    ordersBtn.textContent = 'My Orders';
                    ordersBtn.onclick = () => showCustomerOrdersModal();
                    section2.appendChild(ordersBtn);
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

window.showCustomerOrdersModal = async function() {
    let modal = document.getElementById('customer-orders-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'customer-orders-modal';
        modal.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(15,23,42,0.6); display:flex; align-items:center; justify-content:center; z-index:9999; padding:20px; box-sizing:border-box;';
        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = 'none';
        };
        document.body.appendChild(modal);
    }

    modal.style.display = 'flex';
    modal.innerHTML = `
        <div style="background:#ffffff; border-radius:18px; max-width:650px; width:100%; max-height:85vh; overflow-y:auto; padding:28px; font-family:'Plus Jakarta Sans',sans-serif; box-shadow:0 20px 40px rgba(0,0,0,0.2); position:relative;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #f1f5f9; padding-bottom:14px; margin-bottom:18px;">
                <h3 style="margin:0; font-family:'Space Grotesk',sans-serif; color:#0f172a; font-size:1.3rem;">My Orders</h3>
                <button onclick="document.getElementById('customer-orders-modal').style.display='none'" style="background:transparent; border:none; font-size:1.4rem; cursor:pointer; color:#64748b; line-height:1;">&times;</button>
            </div>
            <div id="customer-orders-content" style="text-align:center; padding:30px; color:#64748b;">Loading your orders...</div>
        </div>
    `;

    try {
        const res = await API.get('/api/orders/my-orders');
        const orders = res.orders || [];
        const content = document.getElementById('customer-orders-content');
        if (!content) return;

        if (orders.length === 0) {
            content.innerHTML = `
                <div style="padding:20px 0; color:#64748b;">
                    <p style="margin:0 0 8px; font-size:1rem; font-weight:600; color:#0f172a;">No orders yet</p>
                    <p style="margin:0; font-size:0.88rem;">When you place a store pickup or home delivery order, it will appear here.</p>
                </div>
            `;
            return;
        }

        content.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:12px; text-align:left;">
                ${orders.map(o => {
                    const isPickup = o.order_type === 'PICKUP';
                    const typeBadge = isPickup
                        ? '<span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">STORE PICKUP</span>'
                        : '<span style="background:#d1fae5; color:#047857; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">HOME DELIVERY</span>';

                    return `
                        <div style="border:1px solid #e2e8f0; border-radius:12px; padding:16px 18px; background:#f8fafc;">
                            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                                <div>
                                    <div style="font-weight:700; color:#0f172a; font-size:0.95rem;">Order #${escapeHtml(o.order_number)}</div>
                                    <div style="font-size:0.8rem; color:#64748b; margin-top:2px;">${o.created_at ? new Date(o.created_at).toLocaleString() : ''}</div>
                                </div>
                                <div>${typeBadge}</div>
                            </div>
                            <div style="font-size:0.88rem; color:#334155; margin-bottom:4px;">
                                <strong>${escapeHtml(o.medicine_name || '')}</strong> (Qty: ${o.quantity}) • ₹${parseFloat(o.total_amount || 0).toFixed(2)}
                            </div>
                            <div style="font-size:0.82rem; color:#64748b; margin-bottom:6px;">
                                <strong>Pharmacy:</strong> ${escapeHtml(o.pharmacy_name || '')}
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px dashed #e2e8f0; padding-top:8px; margin-top:8px;">
                                <span style="font-size:0.85rem; color:#059669; font-weight:600;">Status: ${escapeHtml(o.status)}</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    } catch (err) {
        const content = document.getElementById('customer-orders-content');
        if (content) {
            content.innerHTML = `<div style="color:#ef4444; padding:20px;">Could not load orders: ${escapeHtml(err.message)}</div>`;
        }
    }
};

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
