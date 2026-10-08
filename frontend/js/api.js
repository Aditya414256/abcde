// MediFind Frontend API Client

const API = {
    async request(url, options = {}) {
        options.credentials = 'same-origin';
        if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
            options.headers = Object.assign({}, options.headers, {
                'Content-Type': 'application/json'
            });
            options.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, options);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const errorMsg = data.error || `Request failed with status ${response.status}`;
                const error = new Error(errorMsg);
                error.status = response.status;
                error.data = data;
                throw error;
            }

            return data;
        } catch (err) {
            console.error(`API Error [${url}]:`, err);
            throw err;
        }
    },

    get(url) {
        return this.request(url, { method: 'GET' });
    },

    post(url, body) {
        return this.request(url, { method: 'POST', body });
    },

    put(url, body) {
        return this.request(url, { method: 'PUT', body });
    },

    patch(url, body) {
        return this.request(url, { method: 'PATCH', body });
    },

    delete(url) {
        return this.request(url, { method: 'DELETE' });
    },

    // Auth helpers
    getCurrentUser() {
        return this.get('/api/auth/current-user');
    },

    logout() {
        return this.post('/api/auth/logout', {});
    }
};

window.API = API;
