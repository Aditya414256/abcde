// Owner-only setup controls. The API derives ownership from the authenticated session.
window.loadPharmacySettings = async function() {
    try {
        const {user} = await API.getCurrentUser();
        const p = user.pharmacy;
        document.getElementById('store-latitude').value = p.latitude ?? '';
        document.getElementById('store-longitude').value = p.longitude ?? '';
        document.getElementById('store-pickup').checked = p.supports_pickup;
        document.getElementById('store-delivery').checked = p.supports_delivery;
        document.getElementById('store-delivery-fee').value = p.delivery_fee ?? 0;
        document.getElementById('verification-view').hidden = !p.has_verification_doc;
    } catch (e) { document.getElementById('settings-message').textContent = e.message; }
};

document.addEventListener('DOMContentLoaded', () => {
    const message = (id, value) => { document.getElementById(id).textContent = value; };
    const search = async () => {
        try {
            const q = document.getElementById('inventory-search').value.trim();
            if (!q) return message('inventory-message', 'Enter a medicine name.');
            const {results} = await API.get(`/api/medicines/search?q=${encodeURIComponent(q)}`);
            const select = document.getElementById('inventory-medicine');
            select.replaceChildren(new Option('Select a medicine', ''));
            results.forEach(m => select.add(new Option(`${m.name} ${m.strength || ''}`, m.id)));
            message('inventory-message', results.length ? 'Select a medicine and enter its stock and price.' : 'No matching medicines found.');
        } catch (e) { message('inventory-message', e.message); }
    };
    document.getElementById('inventory-search-btn').addEventListener('click', search);
    document.getElementById('inventory-search').addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); search(); }
    });
    document.getElementById('add-inventory-form').addEventListener('submit', async e => {
        e.preventDefault();
        const button = e.submitter;
        button.disabled = true;
        try {
            const id = Number(document.getElementById('inventory-medicine').value);
            const existing = await API.get('/api/pharmacy/inventory');
            if (existing.inventory.some(item => item.medicine_id === id)) {
                message('inventory-message', 'This medicine is already listed. Edit its stock in the table below.');
                return;
            }
            await API.post('/api/pharmacy/inventory', {
                medicine_id:id,
                quantity:Number(document.getElementById('inventory-quantity').value),
                price:Number(document.getElementById('inventory-price').value)
            });
            message('inventory-message', 'Medicine added to your inventory.');
            await loadPharmacyInventory();
        } catch (err) { message('inventory-message', err.message); }
        finally { button.disabled = false; }
    });
    document.getElementById('store-use-location').addEventListener('click', () => {
        if (!navigator.geolocation) return message('settings-message', 'Location is unavailable. Enter the coordinates manually.');
        navigator.geolocation.getCurrentPosition(pos => {
            document.getElementById('store-latitude').value = pos.coords.latitude;
            document.getElementById('store-longitude').value = pos.coords.longitude;
            message('settings-message', 'Location filled. Save your settings to apply it.');
        }, () => message('settings-message', 'Location permission denied or unavailable. Enter the store coordinates manually.'), {timeout:10000});
    });
    document.getElementById('pharmacy-settings-form').addEventListener('submit', async e => {
        e.preventDefault();
        try {
            await API.patch('/api/pharmacy/profile', {
                latitude:document.getElementById('store-latitude').value || null,
                longitude:document.getElementById('store-longitude').value || null,
                supports_pickup:document.getElementById('store-pickup').checked,
                supports_delivery:document.getElementById('store-delivery').checked,
                delivery_fee:Number(document.getElementById('store-delivery-fee').value)
            });
            message('settings-message', 'Store settings saved.');
        } catch (err) { message('settings-message', err.message); }
    });
    document.getElementById('verification-upload-form').addEventListener('submit', async e => {
        e.preventDefault();
        const button=e.submitter;
        button.disabled=true;
        try {
            const file=document.getElementById('verification-file').files[0];
            if (!file || file.size > 10*1024*1024) throw new Error('Choose a document smaller than 10 MB.');
            const body=new FormData(); body.append('file',file);
            await API.post('/api/pharmacy/verification-doc',body);
            document.getElementById('verification-view').hidden=false;
            message('verification-message','Document uploaded successfully.');
        } catch (err) { message('verification-message',err.message); }
        finally {button.disabled=false;}
    });
});
