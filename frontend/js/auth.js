// MediFind Authentication Handler (Login, Customer Register, Pharmacy Register)

document.addEventListener('DOMContentLoaded', () => {
    initLoginForm();
    initCustomerRegisterForm();
    initPharmacyRegisterForm();
});

// 1. Login Form Handler
function initLoginForm() {
    const loginForm = document.querySelector('.login-form-container form');
    if (!loginForm) return;

    // Create error message container
    let errDiv = document.getElementById('auth-error-msg');
    if (!errDiv) {
        errDiv = document.createElement('div');
        errDiv.id = 'auth-error-msg';
        errDiv.style.cssText = 'display:none; color:#e11d48; background:#fff1f2; border:1px solid #fecdd3; border-radius:10px; padding:10px 14px; margin-bottom:16px; font-size:0.85rem; font-family:"Plus Jakarta Sans",sans-serif; text-align:center;';
        loginForm.prepend(errDiv);
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        errDiv.style.display = 'none';

        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const submitBtn = loginForm.querySelector('button[type="submit"]');

        submitBtn.disabled = true;
        const origText = submitBtn.textContent;
        submitBtn.textContent = 'Signing in...';

        try {
            const res = await API.post('/api/auth/login', { email, password });
            window.location.href = res.redirect_url || 'HomePage.html';
        } catch (err) {
            errDiv.textContent = err.message || 'Invalid email or password.';
            errDiv.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = origText;
        }
    });
}

// 2. Customer Registration Form Handler
function initCustomerRegisterForm() {
    const customerForm = document.querySelector('.customer-card-body form');
    if (!customerForm) return;

    let errDiv = document.getElementById('customer-reg-error');
    if (!errDiv) {
        errDiv = document.createElement('div');
        errDiv.id = 'customer-reg-error';
        errDiv.style.cssText = 'display:none; color:#e11d48; background:#fff1f2; border:1px solid #fecdd3; border-radius:10px; padding:10px 14px; margin-bottom:16px; font-size:0.85rem; font-family:"Plus Jakarta Sans",sans-serif; text-align:center;';
        customerForm.prepend(errDiv);
    }

    customerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        errDiv.style.display = 'none';

        const fullName = document.getElementById('full_name').value.trim();
        const email = document.getElementById('email').value.trim();
        const phone = document.getElementById('phone').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm_password').value;
        const submitBtn = customerForm.querySelector('button[type="submit"]');

        if (password !== confirmPassword) {
            errDiv.textContent = 'Passwords do not match.';
            errDiv.style.display = 'block';
            return;
        }

        if (password.length < 6) {
            errDiv.textContent = 'Password must be at least 6 characters.';
            errDiv.style.display = 'block';
            return;
        }

        submitBtn.disabled = true;
        const origText = submitBtn.innerHTML;
        submitBtn.textContent = 'Creating Account...';

        try {
            const res = await API.post('/api/auth/register/customer', {
                full_name: fullName,
                email,
                phone,
                password,
                confirm_password: confirmPassword
            });
            window.location.href = res.redirect_url || 'HomePage.html';
        } catch (err) {
            errDiv.textContent = err.message || 'Registration failed.';
            errDiv.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.innerHTML = origText;
        }
    });
}

// 3. Pharmacy Registration Form Handler
function initPharmacyRegisterForm() {
    const pharmacyForm = document.querySelector('.pharmacy-card-body form');
    if (!pharmacyForm) return;

    let errDiv = document.getElementById('pharmacy-reg-error');
    if (!errDiv) {
        errDiv = document.createElement('div');
        errDiv.id = 'pharmacy-reg-error';
        errDiv.style.cssText = 'display:none; color:#e11d48; background:#fff1f2; border:1px solid #fecdd3; border-radius:10px; padding:10px 14px; margin-bottom:16px; font-size:0.85rem; font-family:"Plus Jakarta Sans",sans-serif; text-align:center;';
        pharmacyForm.prepend(errDiv);
    }

    pharmacyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        errDiv.style.display = 'none';

        const fullName = document.getElementById('full_name').value.trim();
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm_password').value;

        const pharmacyName = document.getElementById('pharmacy_name').value.trim();
        const licenseNumber = document.getElementById('license_number').value.trim();
        const pharmacyPhone = document.getElementById('pharmacy_phone') ? document.getElementById('pharmacy_phone').value.trim() : '';
        const pharmacyEmail = document.getElementById('pharmacy_email') ? document.getElementById('pharmacy_email').value.trim() : '';
        const address = document.getElementById('address').value.trim();
        const city = document.getElementById('city').value.trim();
        const state = document.getElementById('state').value.trim();
        const pincode = document.getElementById('pincode').value.trim();

        const supportsPickup = document.getElementById('supports_pickup') ? document.getElementById('supports_pickup').checked : true;
        const supportsDelivery = document.getElementById('supports_delivery') ? document.getElementById('supports_delivery').checked : false;

        const submitBtn = pharmacyForm.querySelector('button[type="submit"]');

        if (password !== confirmPassword) {
            errDiv.textContent = 'Passwords do not match.';
            errDiv.style.display = 'block';
            return;
        }

        submitBtn.disabled = true;
        const origText = submitBtn.innerHTML;
        submitBtn.textContent = 'Submitting Application...';

        try {
            const res = await API.post('/api/auth/register-pharmacy', {
                full_name: fullName,
                email,
                password,
                confirm_password: confirmPassword,
                pharmacy_name: pharmacyName,
                license_number: licenseNumber,
                pharmacy_phone: pharmacyPhone,
                pharmacy_email: pharmacyEmail,
                address,
                city,
                state,
                pincode,
                supports_pickup: supportsPickup,
                supports_delivery: supportsDelivery
            });

            alert('Pharmacy registration submitted successfully! Your account status is PENDING admin verification.');
            window.location.href = res.redirect_url || 'pharmacy-dashboard.html';
        } catch (err) {
            errDiv.textContent = err.message || 'Registration failed.';
            errDiv.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.innerHTML = origText;
        }
    });
}
