// Medicine Selection & Two-Choice Ordering Flow (Store Pickup & Delivery)

// Module-level flag: set to true when the currently selected medicine requires a prescription
let _currentMedicineRequiresPrescription = false;

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
                const currentPage = window.location.pathname.includes('Medifinder') ? 'Medifinder.html' : 'FindMedi.html';
                window.location.href = `${currentPage}?q=${encodeURIComponent(val)}`;
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
    clearPickupSession();
    const currentPage = window.location.pathname.includes('Medifinder') ? 'Medifinder.html' : 'FindMedi.html';
    window.location.href = `${currentPage}?medicine_id=${encodeURIComponent(id)}`;
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

        // Store prescription requirement for use in downstream steps
        _currentMedicineRequiresPrescription = !!medicine.requires_prescription;
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
                        Browse verified pharmacies with stock and choose your preferred store for pickup.
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

                      <!-- DYNAMIC FLOW CONTAINER (MODAL / INLINE STEP) -->
            <div id="flow-content-area" style="max-width:720px; margin:0 auto;"></div>
        `;

        // Restore active pickup session if refreshing or returning to this medicine
        await restorePickupSessionIfAny(parseInt(medicineId, 10));

    } catch (err) {
        container.innerHTML = `<div style="padding:40px; text-align:center; color:#ef4444;">Error loading medicine: ${escapeHtml(err.message)}</div>`;
    }
}

// ==========================================
// STORE PICKUP SESSION PERSISTENCE HELPERS
// ==========================================
const PICKUP_SESSION_KEY = 'medifind_pickup_session';

function getPickupSession() {
    try {
        const raw = sessionStorage.getItem(PICKUP_SESSION_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        return null;
    }
}

function savePickupSession(state) {
    try {
        if (!state) {
            sessionStorage.removeItem(PICKUP_SESSION_KEY);
            return;
        }
        const existing = getPickupSession() || {};
        const merged = Object.assign({}, existing, state);
        sessionStorage.setItem(PICKUP_SESSION_KEY, JSON.stringify(merged));
    } catch (e) {
        console.warn('Could not save pickup session state:', e);
    }
}

function clearPickupSession() {
    try {
        sessionStorage.removeItem(PICKUP_SESSION_KEY);
    } catch (e) {}
}

function generateIdempotencyKey() {
    return 'mf_pickup_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Restores pickup progress after browser refresh
async function restorePickupSessionIfAny(medicineId) {
    const session = getPickupSession();
    if (!session || session.medicineId !== medicineId) return;

    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    // Verify authentication before restoring sensitive stages
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated) {
        clearPickupSession();
        return;
    }

    // Step: Order Placed — Retrieve confirmed order from backend database
    if (session.step === 'ORDER_CONFIRMED' && session.orderId) {
        flowArea.innerHTML = `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif; color:#64748b;">
                Restoring your order confirmation from server…
            </div>
        `;
        try {
            const res = await API.get(`/api/orders/${session.orderId}`);
            if (res && res.order) {
                renderPickupOrderConfirmation(res.order);
                return;
            }
        } catch (e) {
            console.warn('Could not retrieve order by ID:', e);
            clearPickupSession();
        }
        return;
    }

    // Step: Confirmation form (reviewing store selection)
    if (session.step === 'CONFIRMATION' && session.pharmacyId) {
        // If request was in flight during refresh, check whether order was already created
        if (session.pendingSubmission && session.idempotencyKey) {
            try {
                const checkRes = await API.get(`/api/orders/by-idempotency/${encodeURIComponent(session.idempotencyKey)}`);
                if (checkRes && checkRes.found && checkRes.order) {
                    savePickupSession({
                        step: 'ORDER_CONFIRMED',
                        medicineId: medicineId,
                        orderId: checkRes.order.id,
                        orderNumber: checkRes.order.order_number,
                        pendingSubmission: false
                    });
                    renderPickupOrderConfirmation(checkRes.order);
                    return;
                }
            } catch (e) {}
            session.pendingSubmission = false;
            savePickupSession(session);
        }

        showPickupConfirmation(
            session.medicineId,
            session.pharmacyId,
            session.pharmacyName,
            session.pharmacyAddress,
            session.unitPrice,
            session.userLat !== undefined ? session.userLat : null,
            session.userLon !== undefined ? session.userLon : null,
            session.requiresPrescription,
            session.quantity || 1,
            session.notes || ''
        );
        return;
    }

    // Step: Store list (selecting a pharmacy)
    if (session.step === 'STORE_LIST') {
        await loadPickupPharmacyList(
            medicineId,
            session.userLat !== undefined ? session.userLat : null,
            session.userLon !== undefined ? session.userLon : null,
            session.quantity || 1
        );
    }
}

// ==========================================
// STORE PICKUP FLOW — pharmacy listing + selection + confirmation
// ==========================================
async function handleStorePickup(medicineId) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    // Auth check
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated) {
        renderAuthRequiredNotice(flowArea, 'Store Pickup');
        return;
    }

    // Show loading skeleton while we (optionally) fetch location then pharmacies
    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="font-size:1.8rem; margin-bottom:12px;">📍</div>
            <h3 style="margin:0 0 8px; font-family:'Space Grotesk',sans-serif; color:#0f172a;">Finding Nearby Pharmacies</h3>
            <p style="color:#64748b; font-size:0.95rem; margin:0 0 20px;">
                Checking your location to sort pharmacies by distance…
            </p>
            <div style="display:inline-block; padding:8px 16px; background:#f1f5f9; border-radius:8px; font-size:0.85rem; color:#475569;">
                Loading eligible stores…
            </div>
        </div>
    `;

    // Optionally get location for distance sorting — not required
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
            console.log('Location not granted for pickup listing; showing without distance sort.');
        }
    }

    savePickupSession({
        step: 'STORE_LIST',
        medicineId: parseInt(medicineId, 10),
        userLat: userLat,
        userLon: userLon,
        quantity: 1
    });

    await loadPickupPharmacyList(medicineId, userLat, userLon, 1);
}

async function loadPickupPharmacyList(medicineId, userLat, userLon, quantity) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    const requiresPrescription = _currentMedicineRequiresPrescription;

    savePickupSession({
        step: 'STORE_LIST',
        medicineId: parseInt(medicineId, 10),
        userLat: userLat !== undefined ? userLat : null,
        userLon: userLon !== undefined ? userLon : null,
        quantity: quantity || 1
    });

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif; color:#64748b;">
            Searching eligible pickup stores…
        </div>
    `;

    try {
        let url = `/api/orders/pickup-pharmacies?medicine_id=${medicineId}&quantity=${quantity || 1}`;
        if (userLat !== null && userLon !== null && userLat !== undefined && userLon !== undefined) {
            url += `&latitude=${userLat}&longitude=${userLon}`;
        }

        const res = await API.get(url);
        const pharmacies = res.pharmacies || [];

        if (pharmacies.length === 0) {
            flowArea.innerHTML = `
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:30px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
                    <div style="font-size:2rem; margin-bottom:12px;">🏪</div>
                    <h3 style="color:#0f172a; margin:0 0 8px;">No Pickup Stores Available</h3>
                    <p style="color:#64748b; font-size:0.9rem; margin:0 0 20px;">
                        Currently no verified pharmacies with sufficient stock offer pickup for this medicine.
                        You may try Home Delivery instead.
                    </p>
                    <button class="search-button" style="background:#059669;" onclick="handleDeliveryChoice(${medicineId})">
                        Try Home Delivery Instead
                    </button>
                </div>
            `;
            return;
        }

        const locationNote = (userLat !== null && userLat !== undefined)
            ? '<span style="color:#059669; font-size:0.8rem;">📍 Sorted by nearest first</span>'
            : '<span style="color:#94a3b8; font-size:0.8rem;">Enable location for distance sorting</span>';

        // Advisory banner for prescription-required medicines
        const rxAdvisory = requiresPrescription
            ? `<div style="background:#fffbeb; border:1px solid #fde68a; border-radius:12px; padding:14px 16px; margin-bottom:18px; display:flex; align-items:flex-start; gap:10px; font-family:'Plus Jakarta Sans',sans-serif;">
                <span style="font-size:1.3rem; flex-shrink:0;">📋</span>
                <div style="font-size:0.88rem; color:#78350f; line-height:1.55;">
                    <strong>Prescription Required:</strong> This medicine requires a valid prescription.
                    Please bring your <strong>physical prescription</strong> when collecting your order.
                    The pharmacy will verify it before dispensing.
                </div>
              </div>`
            : '';

        flowArea.innerHTML = `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:25px; font-family:'Plus Jakarta Sans',sans-serif;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
                    <div>
                        <h3 style="margin:0 0 4px; font-family:'Space Grotesk',sans-serif; color:#0f172a;">Choose a Pickup Store</h3>
                        <p style="color:#64748b; font-size:0.85rem; margin:0;">Select a verified pharmacy to collect your medicine from.</p>
                    </div>
                    ${locationNote}
                </div>

                ${rxAdvisory}

                <div style="display:flex; flex-direction:column; gap:14px;">
                    ${pharmacies.map(p => {
                        const stockBadge = p.stock_status === 'IN_STOCK'
                            ? '<span style="background:#d1fae5; color:#065f46; padding:3px 10px; border-radius:999px; font-size:0.75rem; font-weight:700;">In Stock</span>'
                            : p.stock_status === 'LOW_STOCK'
                                ? '<span style="background:#fef3c7; color:#92400e; padding:3px 10px; border-radius:999px; font-size:0.75rem; font-weight:700;">Low Stock</span>'
                                : '<span style="background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:999px; font-size:0.75rem; font-weight:700;">Limited</span>';
                        const verifiedBadge = p.is_verified
                            ? '<span style="color:#0284c7; font-size:0.75rem; font-weight:600;">✓ Verified</span>'
                            : '';
                        const distBadge = p.distance_text
                            ? `<span style="background:#e0f2fe; color:#0369a1; padding:4px 12px; border-radius:999px; font-size:0.85rem; font-weight:700;">📍 ${escapeHtml(p.distance_text)}</span>`
                            : '';

                        return `
                            <div style="border:1.5px solid #e2e8f0; border-radius:14px; padding:18px 20px; font-family:'Plus Jakarta Sans',sans-serif; transition:box-shadow 0.15s ease;">
                                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                                    <div>
                                        <div style="font-weight:700; font-size:1.05rem; color:#0f172a; font-family:'Space Grotesk',sans-serif; margin-bottom:4px;">
                                            ${escapeHtml(p.pharmacy_name)}
                                        </div>
                                        <div style="font-size:0.82rem; color:#64748b;">
                                            ${escapeHtml(p.address)}, ${escapeHtml(p.city)}
                                        </div>
                                    </div>
                                    ${distBadge}
                                </div>
                                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:14px;">
                                    ${stockBadge}
                                    ${verifiedBadge}
                                    <span style="font-size:0.82rem; color:#475569;">₹${p.unit_price.toFixed(2)} / unit</span>
                                    <span style="font-size:0.82rem; color:#94a3b8;">Stock: ${p.stock_quantity} units</span>
                                </div>
                                <button
                                    class="search-button"
                                    style="width:100%; padding:10px;"
                                    id="select-store-btn-${p.pharmacy_id}"
                                    onclick="showPickupConfirmation(${medicineId}, ${p.pharmacy_id}, '${escapeHtml(p.pharmacy_name).replace(/'/g, "\\'")}', '${escapeHtml(p.address + ', ' + p.city).replace(/'/g, "\\'")}', ${p.unit_price}, ${userLat !== null && userLat !== undefined ? userLat : 'null'}, ${userLon !== null && userLon !== undefined ? userLon : 'null'}, ${requiresPrescription}, ${quantity || 1})"
                                >
                                    Select This Store
                                </button>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;

    } catch (err) {
        flowArea.innerHTML = `
            <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:16px; padding:25px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif;">
                <h4 style="color:#e11d48; margin:0 0 8px;">Could Not Load Pharmacies</h4>
                <p style="color:#475569; font-size:0.92rem; margin:0 0 16px;">${escapeHtml(err.message)}</p>
                <button class="search-button" onclick="handleStorePickup(${medicineId})">Retry</button>
            </div>
        `;
    }
}

window.onChangeStoreClicked = function(medicineId, userLat, userLon) {
    savePickupSession({
        step: 'STORE_LIST',
        medicineId: parseInt(medicineId, 10),
        userLat: userLat !== undefined ? userLat : null,
        userLon: userLon !== undefined ? userLon : null,
        quantity: 1
    });
    loadPickupPharmacyList(medicineId, userLat, userLon, 1);
};

// Step 2: Review & confirm — shown after customer taps "Select This Store"
window.showPickupConfirmation = function(medicineId, pharmacyId, pharmacyName, pharmacyAddress, unitPrice, userLat, userLon, requiresPrescription, quantity, savedNotes) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    const qty = quantity ? parseInt(quantity, 10) : 1;
    const price = parseFloat(unitPrice) || 0;
    const total = (price * qty).toFixed(2);
    const existingSession = getPickupSession() || {};
    const notesValue = savedNotes !== undefined ? savedNotes : (existingSession.notes || '');

    // Reuse existing idempotency key or generate a fresh one
    const idempotencyKey = existingSession.idempotencyKey || generateIdempotencyKey();

    savePickupSession({
        step: 'CONFIRMATION',
        medicineId: parseInt(medicineId, 10),
        pharmacyId: parseInt(pharmacyId, 10),
        pharmacyName: pharmacyName,
        pharmacyAddress: pharmacyAddress,
        unitPrice: price,
        quantity: qty,
        userLat: userLat !== undefined ? userLat : null,
        userLon: userLon !== undefined ? userLon : null,
        requiresPrescription: !!requiresPrescription,
        notes: notesValue,
        idempotencyKey: idempotencyKey,
        pendingSubmission: false
    });

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:1.5px solid #0284c7; border-radius:16px; padding:28px 24px; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid #f1f5f9; padding-bottom:14px;">
                <div>
                    <span style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700;">Confirm Pickup</span>
                    <h3 style="margin:4px 0 0; font-family:'Space Grotesk',sans-serif; color:#0f172a;">${escapeHtml(pharmacyName)}</h3>
                    <div style="font-size:0.82rem; color:#64748b; margin-top:2px;">${escapeHtml(pharmacyAddress)}</div>
                </div>
                <button
                    onclick="onChangeStoreClicked(${medicineId}, ${userLat !== null && userLat !== undefined ? userLat : 'null'}, ${userLon !== null && userLon !== undefined ? userLon : 'null'})"
                    style="background:transparent; border:none; color:#0284c7; font-weight:600; cursor:pointer; font-size:0.85rem; white-space:nowrap;"
                >
                    ← Change Store
                </button>
            </div>

            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px 18px; margin-bottom:20px;">
                <div style="font-size:0.88rem; color:#475569; margin-bottom:8px;">
                    <strong style="color:#0f172a;">Store:</strong> ${escapeHtml(pharmacyName)}
                </div>
                <div style="font-size:0.88rem; color:#475569; margin-bottom:8px;">
                    <strong style="color:#0f172a;">Address:</strong> ${escapeHtml(pharmacyAddress)}
                </div>
                <div style="font-size:0.88rem; color:#475569; margin-bottom:8px;">
                    <strong style="color:#0f172a;">Quantity:</strong> ${qty}
                </div>
                <div style="font-size:0.88rem; color:#475569; margin-bottom:8px;">
                    <strong style="color:#0f172a;">Unit Price:</strong> ₹${price.toFixed(2)}
                </div>
                <div style="font-size:1rem; color:#0f172a; font-weight:700; border-top:1px dashed #e2e8f0; padding-top:10px; margin-top:10px;">
                    Total: ₹${total}
                </div>
            </div>

            <div style="margin-bottom:14px;">
                <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;">Notes for Pharmacy (optional)</label>
                <input type="text" id="pickup-notes" style="width:100%; box-sizing:border-box; padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; font-family:'Plus Jakarta Sans',sans-serif; font-size:0.9rem;" placeholder="e.g. I'll arrive after 6pm">
            </div>

            <div id="pickup-error-box" style="display:none; color:#e11d48; font-size:0.85rem; margin-bottom:14px; background:#fff1f2; padding:10px; border-radius:8px;"></div>

            <button
                class="search-button"
                style="width:100%; padding:13px;"
                id="confirm-pickup-btn"
                onclick="confirmPickupOrder(${medicineId}, ${pharmacyId}, ${qty})"
            >
                Confirm & Place Pickup Order
            </button>
        </div>
    `;

    // Restore any previously typed notes and attach real-time persistence
    const notesInput = document.getElementById('pickup-notes');
    if (notesInput) {
        notesInput.value = notesValue;
        notesInput.addEventListener('input', (e) => {
            const s = getPickupSession();
            if (s) {
                s.notes = e.target.value;
                savePickupSession(s);
            }
        });
    }
};

let _pickupSubmitting = false;

window.confirmPickupOrder = async function(medicineId, pharmacyId, quantity) {
    if (_pickupSubmitting) return;
    _pickupSubmitting = true;

    const btn = document.getElementById('confirm-pickup-btn');
    const errBox = document.getElementById('pickup-error-box');
    const notesEl = document.getElementById('pickup-notes');
    const notes = (notesEl ? notesEl.value.trim() : '') || '';

    if (btn) {
        btn.disabled = true;
        btn.style.pointerEvents = 'none';
        btn.textContent = 'Placing Order…';
    }
    if (errBox) errBox.style.display = 'none';

    let session = getPickupSession() || {};
    if (!session.idempotencyKey) {
        session.idempotencyKey = generateIdempotencyKey();
    }
    session.pendingSubmission = true;
    session.notes = notes;
    savePickupSession(session);

    try {
        const res = await API.post('/api/orders/pickup', {
            pharmacy_id: pharmacyId,
            medicine_id: medicineId,
            quantity: quantity,
            customer_notes: notes || undefined,
            idempotency_key: session.idempotencyKey
        });

        // Verification: ensure the response matches a valid, successfully saved order
        if (!res || !res.order || !res.order.id || !res.order.order_number) {
            throw new Error('Order creation could not be verified by server response.');
        }

        const order = res.order;

        // Persist submitted order state so browser refresh restores this exact confirmation
        savePickupSession({
            step: 'ORDER_CONFIRMED',
            medicineId: parseInt(medicineId, 10),
            orderId: order.id,
            orderNumber: order.order_number,
            pharmacyId: pharmacyId,
            pendingSubmission: false
        });

        renderPickupOrderConfirmation(order);

    } catch (err) {
        // If a network timeout or glitch occurred, check if server created order before showing error
        if (session.idempotencyKey) {
            try {
                const checkRes = await API.get(`/api/orders/by-idempotency/${encodeURIComponent(session.idempotencyKey)}`);
                if (checkRes && checkRes.found && checkRes.order) {
                    savePickupSession({
                        step: 'ORDER_CONFIRMED',
                        medicineId: parseInt(medicineId, 10),
                        orderId: checkRes.order.id,
                        orderNumber: checkRes.order.order_number,
                        pharmacyId: pharmacyId,
                        pendingSubmission: false
                    });
                    renderPickupOrderConfirmation(checkRes.order);
                    return;
                }
            } catch (checkErr) {
                // Ignore checkErr, proceed with error handling
            }
        }

        session.pendingSubmission = false;
        savePickupSession(session);

        if (err.status === 401 || (err.data && err.data.require_login)) {
            const flowArea = document.getElementById('flow-content-area');
            if (flowArea) {
                renderAuthRequiredNotice(flowArea, 'Store Pickup');
            }
            return;
        }

        if (errBox) {
            errBox.textContent = err.message || 'Failed to place order. Please try again.';
            errBox.style.display = 'block';
        }
        if (btn) {
            btn.disabled = false;
            btn.style.pointerEvents = 'auto';
            btn.textContent = 'Confirm & Place Pickup Order';
        }
    } finally {
        _pickupSubmitting = false;
    }
};

function renderPickupOrderConfirmation(order) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    const rxNotice = order.prescription_pending_at_pickup
        ? `<div style="background:#fffbeb; border:1px solid #fde68a; border-radius:12px; padding:12px 16px; margin-bottom:20px; font-size:0.88rem; color:#78350f; text-align:left; line-height:1.5;">
            <strong>📋 Prescription Notice:</strong> This medicine requires a valid prescription. Please bring your <strong>physical prescription</strong> when picking up this order at the pharmacy. The pharmacy will verify it before dispensing.
           </div>`
        : '';

    flowArea.innerHTML = `
        <div style="background:#ffffff; border:2px solid #059669; border-radius:16px; padding:35px 28px; text-align:center; font-family:'Plus Jakarta Sans',sans-serif; box-shadow:0 10px 25px rgba(5,150,105,0.1);">
            <div style="width:56px; height:56px; border-radius:50%; background:#d1fae5; color:#059669; display:flex; align-items:center; justify-content:center; font-size:1.8rem; margin:0 auto 16px;">
                ✓
            </div>
            <h2 style="font-family:'Space Grotesk',sans-serif; color:#0f172a; margin:0 0 6px;">
                Your order has been placed.
            </h2>
            <p style="color:#059669; font-weight:600; font-size:0.95rem; margin:0 0 24px;">
                Store Pickup Order #${escapeHtml(order.order_number)}
            </p>

            ${rxNotice}

            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:20px; text-align:left; margin-bottom:24px;">
                <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                    <strong>Pickup From:</strong> ${escapeHtml(order.pharmacy_name || '')}
                </div>
                <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                    <strong>Medicine:</strong> ${escapeHtml(order.medicine_name || '')} (Qty: ${order.quantity})
                </div>
                <div style="font-size:0.9rem; color:#475569; margin-bottom:8px;">
                    <strong>Total Amount:</strong> ₹${parseFloat(order.total_amount || 0).toFixed(2)}
                </div>
                <div style="font-size:0.9rem; color:#059669; font-weight:600;">
                    <strong>Status:</strong> ${escapeHtml(order.status)}
                </div>
            </div>

            <div style="display:flex; justify-content:center; gap:12px;">
                <button class="search-button" style="padding:10px 24px;" onclick="clearPickupSession(); window.location.href='HomePage.html'">
                    Back to Home
                </button>
            </div>
        </div>
    `;
}

// ==========================================
// DELIVERY FLOW (Requirements #12, 13)
// ==========================================
async function handleDeliveryChoice(medicineId) {
    clearPickupSession();
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    // Check login state first
    const auth = await API.getCurrentUser().catch(() => null);
    if (!auth || !auth.authenticated) {
        renderAuthRequiredNotice(flowArea, 'Home Delivery');
        return;
    }

    // Capture the prescription flag in the local scope of this flow
    const requiresPrescription = _currentMedicineRequiresPrescription;

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
                             onclick="showDeliveryForm(${medicineId}, ${p.pharmacy_id}, '${escapeHtml(p.pharmacy_name)}', ${p.unit_price}, ${p.delivery_fee}, ${requiresPrescription})">
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
window.showDeliveryForm = function(medicineId, pharmacyId, pharmacyName, unitPrice, deliveryFee, requiresPrescription) {
    const flowArea = document.getElementById('flow-content-area');
    if (!flowArea) return;

    // Prescription section varies by whether the medicine requires one
    const prescriptionSection = requiresPrescription
        ? `<div class="form-group" style="margin-bottom:16px;">
            <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#b45309;"
                   for="delivery-prescription">
                📋 Prescription Document <span style="color:#e11d48;">*</span> (Required)
            </label>
            <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:10px 12px; font-size:0.82rem; color:#78350f; margin-bottom:8px; line-height:1.5;">
                This medicine requires a valid prescription for home delivery.
                Please upload a clear photo or PDF of your prescription.
            </div>
            <input type="file" id="delivery-prescription" accept=".jpg,.jpeg,.png,.pdf" required
                   style="width:100%; box-sizing:border-box; padding:8px 0; font-size:0.85rem;">
          </div>`
        : `<div class="form-group" style="margin-bottom:16px;">
            <label style="display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; color:#0f172a;"
                   for="delivery-prescription">
                Prescription Document (If required by medicine)
            </label>
            <input type="file" id="delivery-prescription" accept=".jpg,.jpeg,.png,.pdf"
                   style="width:100%; box-sizing:border-box; padding:8px 0; font-size:0.85rem;">
          </div>`;

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

            <form id="delivery-order-form" onsubmit="submitDeliveryOrder(event, ${medicineId}, ${pharmacyId}, ${requiresPrescription})">
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

                ${prescriptionSection}

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

window.submitDeliveryOrder = async function(event, medicineId, pharmacyId, requiresPrescription) {
    event.preventDefault();

    const address = document.getElementById('delivery-address').value.trim();
    const phone = document.getElementById('delivery-phone').value.trim();
    const quantity = parseInt(document.getElementById('delivery-quantity').value, 10) || 1;
    const notes = document.getElementById('delivery-notes').value.trim();
    const prescriptionInput = document.getElementById('delivery-prescription');
    const submitBtn = document.getElementById('submit-delivery-btn');
    const errBox = document.getElementById('delivery-error-box');

    errBox.style.display = 'none';

    // Client-side guard: for Rx medicines, prescription file must be attached for delivery
    if (requiresPrescription && (!prescriptionInput || !prescriptionInput.files || prescriptionInput.files.length === 0)) {
        errBox.textContent = 'This medicine requires a prescription for home delivery. Please upload your prescription document.';
        errBox.style.display = 'block';
        return;
    }

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
