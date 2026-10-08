// Medicine Selection & Two-Choice Ordering Flow (Store Pickup & Delivery)

document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const medicineId = urlParams.get('medicine_id');
    const searchQuery = urlParams.get('q');

    const container = document.querySelector('.FindMedi');
    if (!container) return;

    if (medicineId) {
        await loadMedicineSelectionFlow(medicineId);
    } else if (searchQuery) {
        await searchAndRenderMedicines(searchQuery);
    } else {
        // Default: display search bar or popular catalogue items
        await searchAndRenderMedicines('');
    }

    // Connect page search input
    const pageSearchInput = document.querySelector('.medicine-search input');
    const pageSearchBtn = document.querySelector('.medicine-search button');
    if (pageSearchInput && pageSearchBtn) {
        if (searchQuery) pageSearchInput.value = searchQuery;

        const performSearch = () => {
            const val = pageSearchInput.value.trim();
            if (val) {
                window.location.href = `FindMedi.html?q=${encodeURIComponent(val)}`;
            }
        };

        pageSearchBtn.addEventListener('click', performSearch);
        pageSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') performSearch();
        });
    }
});

// Search and list medicines
async function searchAndRenderMedicines(query) {
    const resultsContainer = document.querySelector('.medicine-results');
    const headingContainer = document.querySelector('.page-heading');
    if (!resultsContainer) return;

    if (headingContainer) {
        headingContainer.innerHTML = `
            <h1>Find Medicine</h1>
            <p>${query ? `Showing results for "${escapeHtml(query)}"` : 'Search and select a medicine to proceed with Store Pickup or Home Delivery.'}</p>
        `;
    }

    resultsContainer.innerHTML = `<div style="text-align:center; padding:30px; color:#64748b; font-family:'Plus Jakarta Sans',sans-serif;">Loading available medicines...</div>`;

    try {
        const url = query ? `/api/medicines/search?q=${encodeURIComponent(query)}` : '/api/medicines/search?q=a';
        const res = await API.get(url);
        const medicines = res.results || [];

        if (medicines.length === 0) {
            resultsContainer.innerHTML = `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; color:#64748b; font-family:'Plus Jakarta Sans',sans-serif;">
                    <h3>No medicines found</h3>
                    <p>We could not find any medicine matching "${escapeHtml(query)}". Please try another generic or brand name.</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = medicines.map(med => {
            const rxBadge = med.requires_prescription
                ? '<span class="badge" style="background:#fef3c7; color:#b45309;">Rx Prescription Required</span>'
                : '<span class="badge badge-success">✓ OTC</span>';
            const strengthBadge = med.strength
                ? `<span class="badge badge-primary">${escapeHtml(med.strength)}</span>`
                : '';
            const formBadge = med.dosage_form
                ? `<span class="badge">${escapeHtml(med.dosage_form)}</span>`
                : '';

            return `
                <div class="medicine-card" id="medicine-card-${med.id}">
                    <div class="medicine-details">
                        <div class="medicine-badges">
                            ${formBadge}
                            ${strengthBadge}
                            ${rxBadge}
                        </div>
                        <h3>${escapeHtml(med.name)}</h3>
                        <div class="medicine-generic">
                            <strong>Generic:</strong> ${escapeHtml(med.generic_name)}
                        </div>
                        <div class="medicine-description">
                            ${escapeHtml(med.description || 'Medicine verified in local pharmacy catalogues.')}
                        </div>
                        <div class="pharmacy-count">
                            ✓ Available in verified nearby pharmacies
                        </div>
                    </div>
                    <div class="medicine-action">
                        <button class="view-stores-button" onclick="selectMedicine(${med.id})">
                            Select Medicine
                        </button>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        resultsContainer.innerHTML = `<div style="text-align:center; padding:30px; color:#ef4444; font-family:'Plus Jakarta Sans',sans-serif;">Error loading medicines: ${escapeHtml(err.message)}</div>`;
    }
}

function selectMedicine(id) {
    window.location.href = `FindMedi.html?medicine_id=${encodeURIComponent(id)}`;
}

// Load Medicine Selection Flow (Requirement #7: Show Medicine Name + exactly two choices)
async function loadMedicineSelectionFlow(medicineId) {
    const container = document.querySelector('.FindMedi');
    if (!container) return;

    container.innerHTML = `
        <div style="text-align:center; padding:60px 20px; font-family:'Plus Jakarta Sans',sans-serif; color:#64748b;">
            Loading medicine details...
        </div>
    `;

    try {
        const res = await API.get(`/api/medicines/${medicineId}`);
        const medicine = res.medicine;

        if (!medicine) {
            container.innerHTML = `<div style="padding:40px; text-align:center;">Medicine not found.</div>`;
            return;
        }

        const rxBadge = medicine.requires_prescription
            ? '<span class="badge" style="background:#fef3c7; color:#b45309;">Rx Prescription Required</span>'
            : '<span class="badge badge-success">✓ OTC</span>';
        const strengthBadge = medicine.strength
            ? `<span class="badge badge-primary">${escapeHtml(medicine.strength)}</span>`
            : '';
        const formBadge = medicine.dosage_form
            ? `<span class="badge">${escapeHtml(medicine.dosage_form)}</span>`
            : '';

        // Render the simple selection page
        container.innerHTML = `
            <div class="page-heading" style="text-align:center; margin-bottom:30px;">
                <div style="display:inline-flex; gap:8px; margin-bottom:12px;">
                    ${formBadge}
                    ${strengthBadge}
                    ${rxBadge}
                </div>
                <h1 style="font-family:'Space Grotesk',sans-serif; font-size:2.4rem; color:#0f172a; margin:0 0 10px;">
                    ${escapeHtml(medicine.name)}
                </h1>
                <p style="font-family:'Plus Jakarta Sans',sans-serif; color:#64748b; font-size:1.05rem; margin:0 0 25px;">
                    Generic: <strong>${escapeHtml(medicine.generic_name)}</strong>
                </p>
                <div style="max-width:550px; margin:0 auto; background:#f1f5f9; padding:12px 18px; border-radius:12px; font-size:0.9rem; color:#475569; font-family:'Plus Jakarta Sans',sans-serif;">
                    How would you like to receive your medicine? Select an option below.
                </div>
            </div>

            <!-- TWO CHOICES CONTAINER -->
            <div id="ordering-choices" style="max-width:720px; margin:0 auto 40px; display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                
                <!-- CHOICE 1: TAKE FROM STORE -->
                <div class="choice-card" id="choice-store-card" style="background:#ffffff; border:2px solid #e2e8f0; border-radius:16px; padding:30px 24px; text-align:center; transition:all 0.2s ease; cursor:pointer;" onclick="handleStorePickup(${medicine.id})">
                    <div style="width:52px; height:52px; border-radius:12px; background:#e0f2fe; color:#0284c7; display:flex; align-items:center; justify-content:center; font-size:1.5rem; margin:0 auto 16px;">
                        🏪
                    </div>
                    <h3 style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem; color:#0f172a; margin:0 0 8px;">
                        Take From Store
                    </h3>
                    <p style="font-family:'Plus Jakarta Sans',sans-serif; font-size:0.88rem; color:#64748b; line-height:1.5; margin:0 0 20px;">
                        We automatically locate your nearest verified pharmacy with available stock.
                    </p>
                    <button class="search-button" style="width:100%;" id="btn-take-store">
                        Take From Store
                    </button>
                </div>

                <!-- CHOICE 2: TAKE FROM DELIVERY -->
                <div class="choice-card" id="choice-delivery-card" style="background:#ffffff; border:2px solid #e2e8f0; border-radius:16px; padding:30px 24px; text-align:center; transition:all 0.2s ease; cursor:pointer;" onclick="handleDeliveryChoice(${medicine.id})">
                    <div style="width:52px; height:52px; border-radius:12px; background:#d1fae5; color:#059669; display:flex; align-items:center; justify-content:center; font-size:1.5rem; margin:0 auto 16px;">
                        🚚
                    </div>
                    <h3 style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem; color:#0f172a; margin:0 0 8px;">
                        Take From Delivery
                    </h3>
                    <p style="font-family:'Plus Jakarta Sans',sans-serif; font-size:0.88rem; color:#64748b; line-height:1.5; margin:0 0 20px;">
                        Choose from verified pharmacies delivering directly to your address.
                    </p>
                    <button class="search-button" style="width:100%; background:#059669;" id="btn-take-delivery">
                        Take From Delivery
                    </button>
                </div>

            </div>

            <!-- DYNAMIC FLOW CONTAINER (MODAL / INLINE STEP) -->
            <div id="flow-content-area" style="max-width:720px; margin:0 auto;"></div>
        `;

    } catch (err) {
        container.innerHTML = `<div style="padding:40px; text-align:center; color:#ef4444;">Error loading medicine: ${escapeHtml(err.message)}</div>`;
    }
}

// ==========================================
// STORE PICKUP FLOW (Requirements #8, 9, 10, 11)
// ==========================================
async function handleStorePickup(medicineId) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    // Check login state first
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated) {
        renderAuthRequiredNotice(flowArea, 'Store Pickup');
        return;
    }

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="font-size:1.8rem; margin-bottom:12px;">📍</div>
            <h3 style="margin:0 0 8px; font-family:'Space Grotesk',sans-serif; color:#0f172a;">Detecting Your Location</h3>
            <p style="color:#64748b; font-size:0.95rem; margin:0 0 20px;">
                Please allow browser location permission so MediFind can automatically select your nearest verified pharmacy with available stock.
            </p>
            <div style="display:inline-block; padding:8px 16px; background:#f1f5f9; border-radius:8px; font-size:0.85rem; color:#475569;">
                Requesting GPS coordinates...
            </div>
        </div>
    `;

    if (!navigator.geolocation) {
        renderLocationError(flowArea, 'Geolocation is not supported by your browser.');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            await executePickupOrder(medicineId, lat, lon);
        },
        (err) => {
            let msg = 'Location permission was denied. Please allow location access in your browser to find your nearest verified pharmacy.';
            if (err.code === err.POSITION_UNAVAILABLE) msg = 'Location unavailable from your device. Unable to determine nearest pharmacy.';
            if (err.code === err.TIMEOUT) msg = 'Location request timed out. Please try again.';
            renderLocationError(flowArea, msg);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

async function executePickupOrder(medicineId, lat, lon) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
            <h3 style="margin:0 0 8px; font-family:'Space Grotesk',sans-serif; color:#0f172a;">Locating Nearest Eligible Pharmacy...</h3>
            <p style="color:#64748b; font-size:0.92rem; margin:0;">
                Checking verified pharmacies, real-time inventory, and distance...
            </p>
        </div>
    `;

    try {
        const res = await API.post('/api/orders/pickup-nearest', {
            medicine_id: medicineId,
            latitude: lat,
            longitude: lon,
            quantity: 1
        });

        const order = res.order;
        const pharmacy = res.pharmacy;
        const distanceText = res.distance_text;

        // Requirement #11: Clear customer confirmation: "Your order has been placed."
        flowArea.innerHTML = `
            <div style="background:#ffffff; border:2px solid #059669; border-radius:16px; padding:35px 28px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif; box-shadow:0 10px 25px rgba(5, 150, 105, 0.1);">
                <div style="width:56px; height:56px; border-radius:50%; background:#d1fae5; color:#059669; display:flex; align-items:center; justify-content:center; font-size:1.8rem; margin:0 auto 16px;">
                    ✓
                </div>
                <h2 style="font-family:'Space Grotesk',sans-serif; color:#0f172a; margin:0 0 6px;">
                    Your order has been placed.
                </h2>
                <p style="color:#059669; font-weight:600; font-size:0.95rem; margin:0 0 24px;">
                    Store Pickup Order #${escapeHtml(order.order_number)}
                </p>

                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:20px; text-align:left; margin-bottom:24px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
                        <div>
                            <span style="font-size:0.8rem; color:#64748b; text-transform:uppercase; font-weight:700;">Nearest Eligible Store</span>
                            <div style="font-weight:700; font-size:1.15rem; color:#0f172a; font-family:'Space Grotesk',sans-serif;">${escapeHtml(pharmacy.name)}</div>
                        </div>
                        <div style="text-align:right;">
                            <span style="background:#e0f2fe; color:#0369a1; padding:4px 10px; border-radius:999px; font-size:0.85rem; font-weight:700;">
                                📍 ${escapeHtml(distanceText)}
                            </span>
                        </div>
                    </div>

                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Address:</strong> ${escapeHtml(pharmacy.address)}, ${escapeHtml(pharmacy.city)}
                    </div>
                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Item:</strong> ${escapeHtml(order.medicine_name)} (Qty: ${order.quantity})
                    </div>
                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Total Amount:</strong> ₹${order.total_amount.toFixed(2)}
                    </div>
                    <div style="font-size:0.9rem; color:#059669; font-weight:600;">
                        <strong>Status:</strong> Preparing for Pickup
                    </div>
                </div>

                <button class="search-button" style="padding:10px 24px;" onclick="window.location.href='HomePage.html'">
                    Back to Home
                </button>
            </div>
        `;

    } catch (err) {
        flowArea.innerHTML = `
            <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:16px; padding:25px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
                <h4 style="color:#e11d48; margin:0 0 8px;">Pickup Order Notice</h4>
                <p style="color:#475569; font-size:0.92rem; margin:0 0 16px;">${escapeHtml(err.message)}</p>
                <button class="search-button" onclick="handleStorePickup(${medicineId})">Try Again</button>
            </div>
        `;
    }
}

// ==========================================
// DELIVERY FLOW (Requirements #12, 13)
// ==========================================
async function handleDeliveryChoice(medicineId) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    // Check login state first
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated) {
        renderAuthRequiredNotice(flowArea, 'Home Delivery');
        return;
    }

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
            <p style="color:#64748b; font-size:0.95rem; margin:0;">
                Finding delivery-enabled verified pharmacies carrying this medicine...
            </p>
        </div>
    `;

    // Try to get location for distance display
    let userLat = null;
    let userLon = null;

    if (navigator.geolocation) {
        try {
            const pos = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000 });
            });
            userLat = pos.coords.latitude;
            userLon = pos.coords.longitude;
        } catch (e) {
            console.log('Location not granted for delivery listing, listing without distance sorting.');
        }
    }

    try {
        let url = `/api/orders/delivery-pharmacies?medicine_id=${medicineId}`;
        if (userLat !== null && userLon !== null) {
            url += `&latitude=${userLat}&longitude=${userLon}`;
        }

        const res = await API.get(url);
        const pharmacies = res.pharmacies || [];

        if (pharmacies.length === 0) {
            flowArea.innerHTML = `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
                    <h3 style="color:#0f172a; margin:0 0 8px;">No Delivery Stores Available</h3>
                    <p style="color:#64748b; font-size:0.9rem; margin:0 0 20px;">
                        Currently no verified pharmacies with available stock offer delivery for this medicine. You may try Store Pickup.
                    </p>
                    <button class="search-button" onclick="handleStorePickup(${medicineId})">
                        Try Store Pickup Instead
                    </button>
                </div>
            `;
            return;
        }

        // Requirement #12: First pharmacy-selection screen shows ONLY: Pharmacy Name + Distance
        flowArea.innerHTML = `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:25px; font-family:'Plus Jakarta Sans',sans-serif;">
                <h3 style="margin:0 0 6px; font-family:'Space Grotesk',sans-serif; color:#0f172a;">
                    Select a Verified Pharmacy for Delivery
                </h3>
                <p style="color:#64748b; font-size:0.88rem; margin:0 0 20px;">
                    Select your preferred store to enter delivery details:
                </p>

                <div style="display:flex; flex-direction:column; gap:12px; margin-bottom:20px;">
                    ${pharmacies.map(p => `
                        <div class="delivery-pharmacy-item" style="border:1px solid #e2e8f0; border-radius:12px; padding:16px 20px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; transition:all 0.15s ease;"
                             onclick="showDeliveryForm(${medicineId}, ${p.pharmacy_id}, '${escapeHtml(p.pharmacy_name)}', ${p.unit_price}, ${p.delivery_fee})">
                            <div>
                                <div style="font-weight:700; font-size:1.05rem; color:#0f172a; font-family:'Space Grotesk',sans-serif;">
                                    ${escapeHtml(p.pharmacy_name)}
                                </div>
                                <div style="font-size:0.82rem; color:#64748b; margin-top:3px;">
                                    Medicine Price: ₹${p.unit_price.toFixed(2)} • Delivery Fee: ₹${p.delivery_fee.toFixed(2)}
                                </div>
                            </div>
                            <div style="text-align:right;">
                                <span style="display:inline-block; font-weight:700; font-size:0.95rem; color:#0284c7; background:#e0f2fe; padding:6px 14px; border-radius:999px;">
                                    ${escapeHtml(p.distance_text)}
                                </span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

    } catch (err) {
        flowArea.innerHTML = `<div style="padding:30px; text-align:center; color:#ef4444;">Error loading delivery pharmacies: ${escapeHtml(err.message)}</div>`;
    }
}

// Requirement #13: Delivery Order Form
window.showDeliveryForm = function(medicineId, pharmacyId, pharmacyName, unitPrice, deliveryFee) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:28px 24px; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; border-bottom:1px solid #f1f5f9; padding-bottom:12px;">
                <div>
                    <span style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700;">Selected Pharmacy</span>
                    <h3 style="margin:0; font-family:'Space Grotesk',sans-serif; color:#0f172a;">${escapeHtml(pharmacyName)}</h3>
                </div>
                <button onclick="handleDeliveryChoice(${medicineId})" style="background:transparent; border:none; color:#0284c7; font-weight:600; cursor:pointer; font-size:0.85rem;">
                    Change Store
                </button>
            </div>

            <form id="delivery-order-form" onsubmit="submitDeliveryOrder(event, ${medicineId}, ${pharmacyId})">
                <div class="form-group" style="margin-bottom:16px;">
                    <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;">
                        Delivery Address *
                    </label>
                    <textarea id="delivery-address" required style="width:100%; box-sizing:border-box; padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; font-family:'Plus Jakarta Sans',sans-serif; font-size:0.9rem;" rows="2" placeholder="House/Flat No, Street, Landmark, Pincode"></textarea>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px;">
                    <div class="form-group">
                        <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;">
                            Contact Phone *
                        </label>
                        <input type="tel" id="delivery-phone" required style="width:100%; box-sizing:border-box; padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; font-family:'Plus Jakarta Sans',sans-serif; font-size:0.9rem;" placeholder="10-digit number">
                    </div>

                    <div class="form-group">
                        <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;">
                            Quantity *
                        </label>
                        <input type="number" id="delivery-quantity" min="1" max="20" value="1" required style="width:100%; box-sizing:border-box; padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; font-family:'Plus Jakarta Sans',sans-serif; font-size:0.9rem;">
                    </div>
                </div>

                <div class="form-group" style="margin-bottom:16px;">
                    <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;">
                        Prescription Document (If required by medicine)
                    </label>
                    <input type="file" id="delivery-prescription" accept=".jpg,.jpeg,.png,.pdf" style="width:100%; box-sizing:border-box; padding:8px 0; font-size:0.85rem;">
                </div>

                <div class="form-group" style="margin-bottom:20px;">
                    <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;">
                        Instructions for Delivery Partner
                    </label>
                    <input type="text" id="delivery-notes" style="width:100%; box-sizing:border-box; padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; font-family:'Plus Jakarta Sans',sans-serif; font-size:0.9rem;" placeholder="e.g. Leave at door, call on arrival">
                </div>

                <div id="delivery-error-box" style="display:none; color:#e11d48; font-size:0.85rem; margin-bottom:16px; background:#fff1f2; padding:10px; border-radius:8px;"></div>

                <button type="submit" class="search-button" style="width:100%; padding:12px; background:#059669;" id="submit-delivery-btn">
                    Confirm & Place Delivery Order
                </button>
            </form>
        </div>
    `;
};

window.submitDeliveryOrder = async function(event, medicineId, pharmacyId) {
    event.preventDefault();

    const address = document.getElementById('delivery-address').value.trim();
    const phone = document.getElementById('delivery-phone').value.trim();
    const quantity = parseInt(document.getElementById('delivery-quantity').value, 10) || 1;
    const notes = document.getElementById('delivery-notes').value.trim();
    const prescriptionInput = document.getElementById('delivery-prescription');
    const submitBtn = document.getElementById('submit-delivery-btn');
    const errBox = document.getElementById('delivery-error-box');

    errBox.style.display = 'none';
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing Order...';

    try {
        let prescriptionId = null;

        // Upload prescription if attached
        if (prescriptionInput && prescriptionInput.files && prescriptionInput.files.length > 0) {
            const formData = new FormData();
            formData.append('file', prescriptionInput.files[0]);
            formData.append('pharmacy_id', pharmacyId);

            const uploadRes = await fetch('/api/prescriptions/upload', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            const uploadData = await uploadRes.json();
            if (!uploadRes.ok) throw new Error(uploadData.error || 'Failed to upload prescription');
            prescriptionId = uploadData.prescription.id;
        }

        const res = await API.post('/api/orders/create', {
            pharmacy_id: pharmacyId,
            medicine_id: medicineId,
            quantity: quantity,
            order_type: 'DELIVERY',
            delivery_address: address,
            contact_phone: phone,
            customer_notes: notes,
            prescription_id: prescriptionId
        });

        const order = res.order;
        const flowArea = document.getElementById('flow-content-area');

        // Requirement #11/13: Clear confirmation: "Your order has been placed."
        flowArea.innerHTML = `
            <div style="background:#ffffff; border:2px solid #059669; border-radius:16px; padding:35px 28px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif; box-shadow:0 10px 25px rgba(5, 150, 105, 0.1);">
                <div style="width:56px; height:56px; border-radius:50%; background:#d1fae5; color:#059669; display:flex; align-items:center; justify-content:center; font-size:1.8rem; margin:0 auto 16px;">
                    ✓
                </div>
                <h2 style="font-family:'Space Grotesk',sans-serif; color:#0f172a; margin:0 0 6px;">
                    Your order has been placed.
                </h2>
                <p style="color:#059669; font-weight:600; font-size:0.95rem; margin:0 0 24px;">
                    Delivery Order #${escapeHtml(order.order_number)}
                </p>

                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:20px; text-align:left; margin-bottom:24px;">
                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Delivering From:</strong> ${escapeHtml(order.pharmacy_name)}
                    </div>
                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Delivery Address:</strong> ${escapeHtml(order.delivery_address)}
                    </div>
                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Medicine:</strong> ${escapeHtml(order.medicine_name)} (Qty: ${order.quantity})
                    </div>
                    <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                        <strong>Total Amount:</strong> ₹${order.total_amount.toFixed(2)} (inc. delivery fee)
                    </div>
                    <div style="font-size:0.9rem; color:#059669; font-weight:600;">
                        <strong>Status:</strong> Order Placed (Pending Pharmacy Confirmation)
                    </div>
                </div>

                <button class="search-button" style="padding:10px 24px;" onclick="window.location.href='HomePage.html'">
                    Back to Home
                </button>
            </div>
        `;

    } catch (err) {
        errBox.textContent = err.message || 'Failed to place order.';
        errBox.style.display = 'block';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Confirm & Place Delivery Order';
    }
};

function renderLocationError(flowArea, message) {
    flowArea.innerHTML = `
        <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:16px; padding:25px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="font-size:1.8rem; margin-bottom:8px;">⚠️</div>
            <h4 style="color:#e11d48; margin:0 0 8px; font-family:'Space Grotesk',sans-serif;">Location Unavailable</h4>
            <p style="color:#475569; font-size:0.92rem; margin:0 0 16px;">${escapeHtml(message)}</p>
            <p style="color:#64748b; font-size:0.85rem; margin:0 0 16px;">
                MediFind requires your device location to accurately locate the nearest verified store.
            </p>
        </div>
    `;
}

function renderAuthRequiredNotice(flowArea, actionName) {
    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
            <h3 style="margin:0 0 8px; font-family:'Space Grotesk',sans-serif; color:#0f172a;">Sign In Required</h3>
            <p style="color:#64748b; font-size:0.92rem; margin:0 0 20px;">
                Please sign in or create an account to proceed with ${escapeHtml(actionName)}.
            </p>
            <div style="display:flex; justify-content:center; gap:12px;">
                <button class="login" onclick="window.location.href='login.html'">Sign In</button>
                <button class="register" onclick="window.location.href='register-customer.html'">Register Account</button>
            </div>
        </div>
    `;
}

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
