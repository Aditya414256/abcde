// Pharmacy Portal Logic (Order state transitions, inventory update, prescription review)

document.addEventListener('DOMContentLoaded', async () => {
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated || auth.user.role !== 'pharmacy') {
        alert('Access denied. Please login with a pharmacy owner account.');
        window.location.href = 'login.html';
        return;
    }

    await loadPharmacyProfile();
    await loadPharmacyOrders();
});

window.showTab = function(tabName) {
    document.getElementById('tab-orders').style.display = tabName === 'orders' ? 'block' : 'none';
    document.getElementById('tab-inventory').style.display = tabName === 'inventory' ? 'block' : 'none';

    if (tabName === 'inventory') {
        loadPharmacyInventory();
    } else {
        loadPharmacyOrders();
    }
};

let currentPharmacy = null;

async function loadPharmacyProfile() {
    try {
        const res = await API.get('/api/pharmacy/orders');
        currentPharmacy = res.pharmacy;

        if (currentPharmacy) {
            document.getElementById('pharmacy-name-title').textContent = currentPharmacy.name;
            document.getElementById('pharmacy-license-sub').textContent = `Drug License: ${currentPharmacy.license_number} • ${currentPharmacy.address}, ${currentPharmacy.city}`;

            const badge = document.getElementById('pharmacy-status-badge');
            if (currentPharmacy.is_verified) {
                badge.textContent = '✓ Verified & Approved Pharmacy';
                badge.style.background = '#d1fae5';
                badge.style.color = '#047857';
            } else if (currentPharmacy.verification_status === 'REJECTED') {
                badge.textContent = 'Verification Rejected';
                badge.style.background = '#fee2e2';
                badge.style.color = '#b91c1c';
            } else {
                badge.textContent = '⏳ Pending Admin Verification';
                badge.style.background = '#fef3c7';
                badge.style.color = '#b45309';
            }
        }
    } catch (err) {
        console.error('Error loading pharmacy profile:', err);
    }
}

// Order Management
window.loadPharmacyOrders = async function() {
    const container = document.getElementById('orders-list-container');
    container.innerHTML = `<div style="padding:25px; text-align:center; color:#64748b;">Loading orders...</div>`;

    try {
        const res = await API.get('/api/pharmacy/orders');
        const orders = res.orders || [];

        if (orders.length === 0) {
            container.innerHTML = `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:35px; text-align:center; color:#64748b;">
                    <h3>No Orders Yet</h3>
                    <p>New customer pickup and delivery orders will appear here in real time.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = orders.map(o => {
            const isPickup = o.order_type === 'PICKUP';
            const typeBadge = isPickup
                ? '<span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">STORE PICKUP</span>'
                : '<span style="background:#d1fae5; color:#047857; padding:3px 8px; border-radius:999px; font-size:0.75rem; font-weight:700;">HOME DELIVERY</span>';

            // Next state action buttons based on strict order state machine
            let actionsHtml = '';
            if (o.status === 'PENDING') {
                actionsHtml = `
                    <button class="search-button" style="padding:6px 14px; font-size:0.85rem;" onclick="updateOrderStatus(${o.id}, 'ACCEPTED')">Accept Order</button>
                    <button class="login" style="padding:6px 14px; font-size:0.85rem; color:#ef4444;" onclick="updateOrderStatus(${o.id}, 'REJECTED')">Reject</button>
                `;
            } else if (o.status === 'ACCEPTED') {
                actionsHtml = `
                    <button class="search-button" style="padding:6px 14px; font-size:0.85rem;" onclick="updateOrderStatus(${o.id}, 'CONFIRMED')">Confirm Order</button>
                `;
            } else if (o.status === 'CONFIRMED') {
                actionsHtml = `
                    <button class="search-button" style="padding:6px 14px; font-size:0.85rem;" onclick="updateOrderStatus(${o.id}, 'PREPARING')">Mark Preparing</button>
                `;
            } else if (o.status === 'PREPARING') {
                if (isPickup) {
                    actionsHtml = `
                        <button class="search-button" style="padding:6px 14px; font-size:0.85rem; background:#059669;" onclick="updateOrderStatus(${o.id}, 'READY_FOR_PICKUP')">Ready for Pickup</button>
                    `;
                } else {
                    actionsHtml = `
                        <button class="search-button" style="padding:6px 14px; font-size:0.85rem; background:#059669;" onclick="updateOrderStatus(${o.id}, 'OUT_FOR_DELIVERY')">Out for Delivery</button>
                    `;
                }
            } else if (o.status === 'READY_FOR_PICKUP' || o.status === 'OUT_FOR_DELIVERY') {
                actionsHtml = `
                    <button class="search-button" style="padding:6px 14px; font-size:0.85rem; background:#059669;" onclick="updateOrderStatus(${o.id}, 'COMPLETED')">Complete Order</button>
                `;
            } else {
                actionsHtml = `<span style="font-size:0.85rem; color:#64748b; font-weight:600;">No further actions</span>`;
            }

            const prescriptionReview = o.prescription_id
                ? `<div style="margin-top:10px; padding:10px; background:#fef3c7; border-radius:8px; font-size:0.85rem;">
                     📄 <strong>Prescription Attached:</strong>
                     <a href="/api/prescriptions/${o.prescription_id}/file" target="_blank" style="color:#b45309; text-decoration:underline; margin-left:6px; font-weight:600;">View File</a>
                   </div>`
                : '';

            return `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:20px 24px; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px; border-bottom:1px solid #f1f5f9; padding-bottom:10px;">
                        <div>
                            <span style="font-size:0.8rem; color:#64748b; font-weight:700;">ORDER #${escapeHtml(o.order_number)}</span>
                            <span style="margin-left:8px;">${typeBadge}</span>
                        </div>
                        <div>
                            <span style="background:#f1f5f9; color:#0f172a; padding:4px 10px; border-radius:999px; font-size:0.8rem; font-weight:700;">
                                STATUS: ${escapeHtml(o.status.replace('_', ' '))}
                            </span>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; font-size:0.9rem; color:#334155; margin-bottom:14px;">
                        <div>
                            <strong style="color:#0f172a;">Customer:</strong> ${escapeHtml(o.customer_name || 'Customer')}
                            ${o.contact_phone ? `<br><small style="color:#64748b;">📞 ${escapeHtml(o.contact_phone)}</small>` : ''}
                        </div>
                        <div>
                            <strong style="color:#0f172a;">Medicine:</strong> ${escapeHtml(o.medicine_name)} (Qty: ${o.quantity})
                            <br><small style="color:#64748b;">Amount: ₹${o.total_amount.toFixed(2)}</small>
                        </div>
                        ${o.delivery_address ? `<div><strong style="color:#0f172a;">Delivery Address:</strong> ${escapeHtml(o.delivery_address)}</div>` : ''}
                    </div>

                    ${prescriptionReview}

                    <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:14px; border-top:1px solid #f1f5f9; padding-top:12px; align-items:center;">
                        ${actionsHtml}
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        container.innerHTML = `<div style="padding:20px; text-align:center; color:#ef4444;">Error loading orders: ${escapeHtml(err.message)}</div>`;
    }
};

window.updateOrderStatus = async function(orderId, newStatus) {
    try {
        await API.post(`/api/orders/${orderId}/status`, { status: newStatus });
        loadPharmacyOrders();
    } catch (err) {
        alert('Failed to update status: ' + err.message);
    }
};

// Inventory Management
window.loadPharmacyInventory = async function() {
    const container = document.getElementById('inventory-list-container');
    container.innerHTML = `<div style="padding:25px; text-align:center; color:#64748b;">Loading inventory items...</div>`;

    try {
        const res = await API.get('/api/pharmacy/inventory');
        const items = res.inventory || [];

        container.innerHTML = `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; overflow:hidden; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                <table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.9rem;">
                    <thead>
                        <tr style="background:#f8fafc; border-bottom:1px solid #e2e8f0; color:#475569; font-weight:600;">
                            <th style="padding:12px 16px;">Medicine</th>
                            <th style="padding:12px 16px;">Quantity</th>
                            <th style="padding:12px 16px;">Price (₹)</th>
                            <th style="padding:12px 16px;">Status</th>
                            <th style="padding:12px 16px;">Batch</th>
                            <th style="padding:12px 16px; text-align:right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map(item => `
                            <tr style="border-bottom:1px solid #f1f5f9;">
                                <td style="padding:14px 16px; font-weight:600; color:#0f172a;">
                                    ${escapeHtml(item.medicine ? item.medicine.name : 'Unknown')}
                                    <br><small style="color:#64748b; font-weight:400;">${escapeHtml(item.medicine ? item.medicine.generic_name : '')}</small>
                                </td>
                                <td style="padding:14px 16px;">
                                    <input type="number" id="qty-${item.medicine_id}" value="${item.quantity}" min="0" style="width:70px; padding:6px; border:1px solid #cbd5e1; border-radius:6px;">
                                </td>
                                <td style="padding:14px 16px;">
                                    <input type="number" step="0.5" id="price-${item.medicine_id}" value="${item.price}" min="0" style="width:80px; padding:6px; border:1px solid #cbd5e1; border-radius:6px;">
                                </td>
                                <td style="padding:14px 16px;">
                                    <span style="font-weight:600; font-size:0.8rem; color:${item.stock_status === 'AVAILABLE' ? '#059669' : item.stock_status === 'LOW_STOCK' ? '#b45309' : '#dc2626'};">
                                        ${escapeHtml(item.stock_status.replace('_', ' '))}
                                    </span>
                                </td>
                                <td style="padding:14px 16px; color:#64748b;">
                                    ${escapeHtml(item.batch_number || 'BAT-01')}
                                </td>
                                <td style="padding:14px 16px; text-align:right;">
                                    <button class="search-button" style="padding:6px 12px; font-size:0.8rem;" onclick="saveInventoryItem(${item.medicine_id})">
                                        Save
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div style="padding:20px; text-align:center; color:#ef4444;">Error loading inventory: ${escapeHtml(err.message)}</div>`;
    }
};

window.saveInventoryItem = async function(medicineId) {
    const qtyInput = document.getElementById(`qty-${medicineId}`);
    const priceInput = document.getElementById(`price-${medicineId}`);
    if (!qtyInput || !priceInput) return;

    const quantity = parseInt(qtyInput.value, 10);
    const price = parseFloat(priceInput.value);

    try {
        await API.post('/api/pharmacy/inventory', {
            medicine_id: medicineId,
            quantity,
            price
        });
        alert('Inventory updated successfully!');
        loadPharmacyInventory();
    } catch (err) {
        alert('Failed to update inventory: ' + err.message);
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
