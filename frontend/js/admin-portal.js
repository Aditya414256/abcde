// Admin Portal Logic (Verifying drug licenses, approvals, toggling active states)

document.addEventListener('DOMContentLoaded', async () => {
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated || auth.user.role !== 'admin') {
        alert('Access denied. Administrator privileges required.');
        window.location.href = 'login.html';
        return;
    }

    await loadAdminData();
});

window.loadAdminData = async function() {
    await loadStats();
    await loadPharmacies();
};

async function loadStats() {
    try {
        const res = await API.get('/api/admin/stats');
        const s = res.stats || {};
        document.getElementById('stat-pharmacies').textContent = s.total_pharmacies || 0;
        document.getElementById('stat-pending').textContent = s.pending_verifications || 0;
        document.getElementById('stat-verified').textContent = s.verified_pharmacies || 0;
        document.getElementById('stat-orders').textContent = s.total_orders || 0;
    } catch (err) {
        console.error('Error loading admin stats:', err);
    }
}

async function loadPharmacies() {
    const container = document.getElementById('admin-pharmacies-list');
    container.innerHTML = `<div style="padding:25px; text-align:center; color:#64748b;">Loading pharmacy registrations...</div>`;

    try {
        const res = await API.get('/api/admin/pharmacies');
        const pharmacies = res.pharmacies || [];

        if (pharmacies.length === 0) {
            container.innerHTML = `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:30px; text-align:center; color:#64748b;">
                    No pharmacies registered yet.
                </div>
            `;
            return;
        }

        container.innerHTML = pharmacies.map(p => {
            const isApproved = p.verification_status === 'APPROVED';
            const isPending = p.verification_status === 'PENDING';
            const statusBadge = isApproved
                ? '<span style="background:#d1fae5; color:#047857; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">APPROVED & VERIFIED</span>'
                : isPending
                ? '<span style="background:#fef3c7; color:#b45309; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">PENDING REVIEW</span>'
                : '<span style="background:#fee2e2; color:#b91c1c; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">REJECTED</span>';

            const activeText = p.is_active ? 'Active' : 'Inactive';
            const activeColor = p.is_active ? '#059669' : '#dc2626';

            return `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:20px 24px; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px; border-bottom:1px solid #f1f5f9; padding-bottom:10px;">
                        <div>
                            <span style="font-weight:700; font-size:1.15rem; color:#0f172a; font-family:'Space Grotesk',sans-serif;">${escapeHtml(p.name)}</span>
                            <span style="margin-left:8px;">${statusBadge}</span>
                        </div>
                        <div>
                            <span style="font-size:0.85rem; font-weight:600; color:${activeColor};">
                                Store Status: ${activeText}
                            </span>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; font-size:0.88rem; color:#334155; margin-bottom:14px;">
                        <div>
                            <strong style="color:#0f172a;">Drug License Number:</strong><br>
                            <span style="font-family:monospace; font-size:0.95rem; color:#0369a1; font-weight:600;">${escapeHtml(p.license_number)}</span>
                        </div>
                        <div>
                            <strong style="color:#0f172a;">Owner:</strong><br>
                            ${p.owner ? `${escapeHtml(p.owner.full_name)} (${escapeHtml(p.owner.email)})` : 'N/A'}
                        </div>
                        <div>
                            <strong style="color:#0f172a;">Address:</strong><br>
                            ${escapeHtml(p.address)}, ${escapeHtml(p.city)}, ${escapeHtml(p.state)} — ${escapeHtml(p.pincode)}
                        </div>
                        <div>
                            <strong style="color:#0f172a;">Services Supported:</strong><br>
                            ${p.supports_pickup ? '✓ Pickup' : ''} ${p.supports_delivery ? '✓ Delivery' : ''}
                        </div>
                    </div>

                    <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:14px; border-top:1px solid #f1f5f9; padding-top:12px;">
                        <button class="login" style="padding:6px 12px; font-size:0.82rem;" onclick="toggleStoreActive(${p.id})">
                            Toggle ${p.is_active ? 'Inactive' : 'Active'}
                        </button>
                        ${!isApproved ? `
                            <button class="search-button" style="padding:6px 14px; font-size:0.82rem; background:#059669;" onclick="verifyStore(${p.id}, 'approve')">
                                Approve & Verify
                            </button>
                        ` : ''}
                        ${p.verification_status !== 'REJECTED' ? `
                            <button class="login" style="padding:6px 14px; font-size:0.82rem; color:#ef4444;" onclick="verifyStore(${p.id}, 'reject')">
                                Reject
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        container.innerHTML = `<div style="padding:20px; text-align:center; color:#ef4444;">Error loading pharmacies: ${escapeHtml(err.message)}</div>`;
    }
}

window.verifyStore = async function(pharmacyId, action) {
    if (!confirm(`Are you sure you want to ${action} this pharmacy?`)) return;

    try {
        await API.post(`/api/admin/pharmacies/${pharmacyId}/verify`, { action });
        loadAdminData();
    } catch (err) {
        alert('Action failed: ' + err.message);
    }
};

window.toggleStoreActive = async function(pharmacyId) {
    try {
        await API.post(`/api/admin/pharmacies/${pharmacyId}/toggle-active`, {});
        loadAdminData();
    } catch (err) {
        alert('Toggle failed: ' + err.message);
    }
};

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    })[m]);
}
