// Verified Pharmacies Locator Page JavaScript

document.addEventListener('DOMContentLoaded', async () => {
    const listContainer = document.querySelector('.pharmacy-list');
    if (!listContainer) return;

    listContainer.innerHTML = `
        <div style="text-align:center; padding:40px; font-family:'Plus Jakarta Sans',sans-serif; color:#64748b;">
            Locating verified pharmacies...
        </div>
    `;

    // Try to get location for distance calculation
    let userLat = null;
    let userLon = null;

    if (navigator.geolocation) {
        try {
            const pos = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 3500 });
            });
            userLat = pos.coords.latitude;
            userLon = pos.coords.longitude;
        } catch (e) {
            console.log('Location not granted for pharmacy locator; continuing without distance sorting.');
        }
    }

    try {
        let url = '/api/pharmacies';
        if (userLat !== null && userLon !== null) {
            url += `?latitude=${userLat}&longitude=${userLon}`;
        }

        const res = await API.get(url);
        const pharmacies = res.pharmacies || [];

        if (pharmacies.length === 0) {
            listContainer.innerHTML = `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:35px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif; color:#64748b;">
                    <h3>No Verified Pharmacies Found</h3>
                    <p>There are currently no verified active pharmacies registered in this area.</p>
                </div>
            `;
            return;
        }

        listContainer.innerHTML = pharmacies.map(p => {
            const pickupBadge = p.supports_pickup
                ? '<span>✓ Pickup Available</span>'
                : '';
            const deliveryBadge = p.supports_delivery
                ? `<span>✓ Delivery Available (₹${p.delivery_fee.toFixed(2)})</span>`
                : '';
            const distanceTag = p.distance_text
                ? `<span style="background:#e0f2fe; color:#0369a1; padding:3px 9px; border-radius:999px; font-size:0.75rem; font-weight:700; margin-left:8px;">📍 ${escapeHtml(p.distance_text)}</span>`
                : '';

            return `
                <div class="pharmacy-card" id="pharmacy-${p.id}">
                    <div class="pharmacy-details">
                        <div class="pharmacy-top">
                            <div>
                                <div style="display:flex; align-items:center; flex-wrap:wrap; gap:6px;">
                                    <h3>${escapeHtml(p.name)}</h3>
                                    ${distanceTag}
                                </div>
                                <span class="pharmacy-status">
                                    ✓ Verified Pharmacy
                                </span>
                            </div>
                        </div>

                        <p class="pharmacy-address">
                            ${escapeHtml(p.address)}, ${escapeHtml(p.city)}, ${escapeHtml(p.state)} — ${escapeHtml(p.pincode)}
                            ${p.phone ? `<br><small style="color:#64748b;">📞 Phone: ${escapeHtml(p.phone)}</small>` : ''}
                        </p>

                        <div class="pharmacy-info">
                            ${pickupBadge}
                            ${deliveryBadge}
                        </div>

                        <div class="pharmacy-hours">
                            Drug License: <strong>${escapeHtml(p.license_number)}</strong>
                        </div>
                    </div>

                    <div class="pharmacy-action">
                        <button class="view-pharmacy-button" onclick="viewPharmacyInventory(${p.id})">
                            View Medicines
                        </button>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        listContainer.innerHTML = `
            <div style="text-align:center; padding:30px; color:#ef4444; font-family:'Plus Jakarta Sans',sans-serif;">
                Error loading verified pharmacies: ${escapeHtml(err.message)}
            </div>
        `;
    }
});

// View a pharmacy's verified inventory
window.viewPharmacyInventory = async function(pharmacyId) {
    const card = document.getElementById(`pharmacy-${pharmacyId}`);
    if (!card) return;

    let invDiv = document.getElementById(`pharmacy-inv-${pharmacyId}`);
    if (invDiv) {
        invDiv.remove();
        return;
    }

    try {
        const res = await API.get(`/api/pharmacies/${pharmacyId}`);
        const inventory = res.pharmacy.inventory || [];

        invDiv = document.createElement('div');
        invDiv.id = `pharmacy-inv-${pharmacyId}`;
        invDiv.style.cssText = "grid-column: 1 / -1; border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 10px; font-family: 'Plus Jakarta Sans', sans-serif;";

        if (inventory.length === 0) {
            invDiv.innerHTML = `<p style="color:#64748b; font-size:0.88rem; margin:0;">No medicines currently listed in inventory for this pharmacy.</p>`;
        } else {
            invDiv.innerHTML = `
                <div style="font-weight:700; font-size:0.95rem; color:#0f172a; margin-bottom:10px;">Available Medicines In Stock:</div>
                <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap:10px;">
                    ${inventory.map(item => `
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:10px 12px; cursor:pointer;" onclick="window.location.href='FindMedi.html?medicine_id=${item.medicine_id}'">
                            <div style="font-weight:600; font-size:0.9rem; color:#0f172a;">${escapeHtml(item.medicine ? item.medicine.name : 'Medicine')}</div>
                            <div style="font-size:0.8rem; color:#64748b;">${escapeHtml(item.medicine ? item.medicine.strength || '' : '')} • ₹${item.price.toFixed(2)}</div>
                            <div style="font-size:0.75rem; color:#059669; font-weight:600; margin-top:4px;">${escapeHtml(item.stock_status.replace('_', ' '))}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        card.appendChild(invDiv);

    } catch (err) {
        console.error('Error fetching pharmacy inventory:', err);
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
