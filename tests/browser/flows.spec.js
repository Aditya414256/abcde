const {test,expect} = require('@playwright/test');
const credentials={customer:['customer@example.com','customer123'],pharmacy:['ram@pharmacy.com','pharmacy123'],admin:['admin@medifind.com','admin123']};
async function login(page,role) {
    const [email,password]=credentials[role];
    expect((await page.request.post('/api/auth/login',{data:{email,password}})).ok()).toBeTruthy();
}
test.beforeEach(async ({page})=> {
    await page.route(/fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com/,route=>route.abort());
});

test('apostrophes are safe in delivery and pickup store selection',async ({page})=> {
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await login(page,'customer');
    await page.goto('/FindMedi.html?medicine_id=1');
    await page.locator('#choice-delivery-card').click();
    await page.locator('[data-delivery-store="1"]').click();
    await expect(page.locator('#delivery-order-form')).toBeVisible();
    await expect(page.getByRole('heading',{name:"Patil's Pharmacy",exact:true})).toBeVisible();
    await page.locator('#choice-store-card').click();
    await page.locator('[data-pickup-store="1"]').click();
    await expect(page.locator('#confirm-pickup-btn')).toBeVisible();
    expect(errors).toEqual([]);
    await page.screenshot({path:'test-results/pickup-confirmation.png',fullPage:true});
});

test('new pharmacy can set location, upload license and add first inventory item',async ({page})=> {
    const data={full_name:'Browser Owner',email:'browser-owner@test.example',password:'password123',
        confirm_password:'password123',pharmacy_name:"Browser's Pharmacy",license_number:'BROWSER-001',
        address:'Test road',city:'Surat',state:'Gujarat',pincode:'395001'};
    const registered=await page.request.post('/api/auth/register-pharmacy',{data});
    expect(registered.status()).toBe(201);
    const pharmacy=(await registered.json()).pharmacy;
    await page.goto('/pharmacy-dashboard.html?setup=1');
    await page.locator('#store-latitude').fill('21.17');
    await page.locator('#store-longitude').fill('72.83');
    await page.locator('#store-delivery').check();
    await page.locator('#store-delivery-fee').fill('20');
    await page.getByRole('button',{name:'Save Store Settings'}).click();
    await expect(page.locator('#settings-message')).toHaveText('Store settings saved.');
    await page.locator('#verification-file').setInputFiles({name:'license.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 browser test')});
    await page.getByRole('button',{name:'Upload Document',exact:true}).click();
    await expect(page.locator('#verification-message')).toHaveText('Document uploaded successfully.');
    await page.getByRole('button',{name:'💊 Inventory',exact:true}).click();
    await page.locator('#inventory-search').fill('Dolo');
    await page.getByRole('button',{name:'Search Medicines'}).click();
    await expect(page.locator('#inventory-medicine option')).toHaveCount(2);
    await page.locator('#inventory-medicine').selectOption('1');
    await page.locator('#inventory-quantity').fill('10');
    await page.locator('#inventory-price').fill('35');
    await page.getByRole('button',{name:'Add to Inventory',exact:true}).click();
    await expect(page.locator('#inventory-message')).toHaveText('Medicine added to your inventory.');
    await expect(page.locator('#qty-1')).toHaveValue('10');
    await page.screenshot({path:'test-results/owner-inventory.png',fullPage:true});
    await login(page,'admin');
    await page.goto('/admin-dashboard.html');
    const card=page.locator('#admin-pharmacies-list > div').filter({hasText:"Browser's Pharmacy"});
    await expect(card.getByRole('link',{name:'View Verification Document'})).toBeVisible();
    page.on('dialog',d=>d.accept());
    await card.getByRole('button',{name:'Approve & Verify'}).click();
    await expect(card).toContainText('APPROVED & VERIFIED');
    const response=await page.request.get(`/api/pharmacies/${pharmacy.id}`);
    expect((await response.json()).pharmacy.latitude).toBe(21.17);
});

test('delivery survives refresh and lost response; owner reviews Rx and completes order',async ({page})=> {
    await login(page,'customer');
    await page.goto('/FindMedi.html?medicine_id=5');
    await page.locator('#choice-delivery-card').click();
    await page.locator('[data-delivery-store="1"]').click();
    await page.locator('#delivery-address').fill('Browser test address');
    await page.locator('#delivery-phone').fill('9999999999');
    await page.locator('#delivery-notes').fill('Browser retry test');
    await page.reload();
    await expect(page.locator('#delivery-address')).toHaveValue('Browser test address');
    await expect(page.locator('#delivery-phone')).toHaveValue('9999999999');
    await page.locator('#delivery-prescription').setInputFiles({name:'rx.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 test prescription')});
    await page.route('**/api/orders/create',async route=>{
        await route.fetch();
        await route.abort('failed');
        await page.unroute('**/api/orders/create');
    });
    await page.getByRole('button',{name:'Confirm & Place Delivery Order',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Your order has been placed.',exact:true})).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading',{name:'Your order has been placed.',exact:true})).toBeVisible();
    const {orders}=await (await page.request.get('/api/orders/my-orders')).json();
    const matches=orders.filter(o=>o.customer_notes==='Browser retry test');
    expect(matches).toHaveLength(1);
    const order=matches[0];
    await login(page,'pharmacy');
    await page.goto('/pharmacy-dashboard.html');
    const card=page.locator('#orders-list-container > div').filter({hasText:order.order_number});
    await card.getByRole('button',{name:'Accept Order',exact:true}).click();
    await expect(card.getByRole('button',{name:'Confirm Order',exact:true})).toBeDisabled();
    page.on('dialog',d=>d.accept());
    await card.getByRole('button',{name:'Approve Prescription',exact:true}).click();
    await expect(card).toContainText('APPROVED');
    for (const name of ['Confirm Order','Mark Preparing','Out for Delivery','Complete Order']) {
        await card.getByRole('button',{name,exact:true}).click();
    }
    await expect(card).toContainText('COMPLETED');
    await page.screenshot({path:'test-results/completed-delivery.png',fullPage:true});
});

test('untrusted store names remain text and cannot execute click-handler code',async ({page})=> {
    await login(page,'customer');
    await page.route('**/api/orders/delivery-pharmacies*',route=>route.fulfill({json:{pharmacies:[{
        pharmacy_id:1,pharmacy_name:"'); window.auditMarker=1; //",address:'Test',city:'Test',unit_price:10,delivery_fee:0
    }]}}));
    await page.goto('/FindMedi.html?medicine_id=1');
    await page.locator('#choice-delivery-card').click();
    await page.locator('[data-delivery-store="1"]').click();
    await expect(page.locator('#delivery-order-form')).toBeVisible();
    expect(await page.evaluate(()=>window.auditMarker)).toBeUndefined();
});

test('prescription pickup needs no upload, restores on refresh and permits a new order',async ({page})=> {
    await login(page,'customer');
    await page.goto('/FindMedi.html?medicine_id=5');
    await page.locator('#choice-store-card').click();
    await page.locator('[data-pickup-store="1"]').click();
    await expect(page.locator('input[type=file]')).toHaveCount(0);
    await page.locator('#pickup-notes').fill('Browser pickup repeat');
    await page.locator('#confirm-pickup-btn').click();
    await expect(page.getByRole('heading',{name:'Your order has been placed.',exact:true})).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading',{name:'Your order has been placed.',exact:true})).toBeVisible();
    await page.locator('#choice-store-card').click();
    await page.locator('[data-pickup-store="1"]').click();
    await page.locator('#pickup-notes').fill('Browser pickup repeat');
    await page.locator('#confirm-pickup-btn').click();
    await expect(page.getByRole('heading',{name:'Your order has been placed.',exact:true})).toBeVisible();
    const {orders}=await (await page.request.get('/api/orders/my-orders')).json();
    const matches=orders.filter(o=>o.customer_notes==='Browser pickup repeat');
    expect(matches).toHaveLength(2);
    expect(matches[0].idempotency_key).not.toBe(matches[1].idempotency_key);
});
