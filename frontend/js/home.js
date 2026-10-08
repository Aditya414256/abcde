// Home page search and autocomplete dropdown

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('home-search-input');
    const searchForm = document.querySelector('.search-bar');
    const searchWrapper = document.querySelector('.search-wrapper');

    if (!searchInput || !searchWrapper) return;

    // Create suggestions container below search-bar
    let dropdown = document.getElementById('search-suggestions');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'search-suggestions';
        dropdown.className = 'search-suggestions';
        searchWrapper.appendChild(dropdown);
    }

    let debounceTimer = null;
    let currentSelectedIndex = -1;
    let suggestionsData = [];

    // Live autocomplete on input
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(debounceTimer);

        if (query.length < 1) {
            closeDropdown();
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const res = await API.get(`/api/medicines/suggestions?q=${encodeURIComponent(query)}`);
                suggestionsData = res.suggestions || [];
                renderSuggestions(suggestionsData);
            } catch (err) {
                console.error('Autocomplete fetch error:', err);
                closeDropdown();
            }
        }, 200);
    });

    // Keyboard navigation in suggestions
    searchInput.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.suggestion-item');
        if (items.length === 0 || dropdown.style.display !== 'block') return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            currentSelectedIndex = (currentSelectedIndex + 1) % items.length;
            updateActiveItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            currentSelectedIndex = (currentSelectedIndex - 1 + items.length) % items.length;
            updateActiveItem(items);
        } else if (e.key === 'Enter') {
            if (currentSelectedIndex >= 0 && currentSelectedIndex < suggestionsData.length) {
                e.preventDefault();
                selectSuggestion(suggestionsData[currentSelectedIndex]);
            }
        } else if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchWrapper.contains(e.target)) {
            closeDropdown();
        }
    });

    // Render suggestions
    function renderSuggestions(list) {
        currentSelectedIndex = -1;
        if (!list || list.length === 0) {
            dropdown.innerHTML = `
                <div style="padding: 14px 18px; color: #64748b; font-size: 0.9rem; font-family: 'Plus Jakarta Sans', sans-serif;">
                    No medicines found. Try another search name.
                </div>
            `;
            dropdown.style.display = 'block';
            return;
        }

        dropdown.innerHTML = list.map((item, idx) => {
            const rxBadge = item.requires_prescription 
                ? '<span class="suggestion-badge rx">Rx Required</span>'
                : '<span class="suggestion-badge">OTC</span>';
            const strengthText = item.strength ? ` (${escapeHtml(item.strength)})` : '';
            return `
                <div class="suggestion-item" data-index="${idx}">
                    <div>
                        <span class="suggestion-name">${escapeHtml(item.name)}${strengthText}</span>
                        <span class="suggestion-generic">• ${escapeHtml(item.generic_name)}</span>
                    </div>
                    <div>${rxBadge}</div>
                </div>
            `;
        }).join('');

        dropdown.style.display = 'block';

        dropdown.querySelectorAll('.suggestion-item').forEach(el => {
            el.addEventListener('click', () => {
                const index = parseInt(el.getAttribute('data-index'), 10);
                selectSuggestion(list[index]);
            });
        });
    }

    function updateActiveItem(items) {
        items.forEach((item, idx) => {
            if (idx === currentSelectedIndex) {
                item.classList.add('active');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('active');
            }
        });
    }

    function selectSuggestion(item) {
        closeDropdown();
        // Redirect to medicine selection flow
        window.location.href = `FindMedi.html?medicine_id=${encodeURIComponent(item.id)}`;
    }

    function closeDropdown() {
        dropdown.style.display = 'none';
        currentSelectedIndex = -1;
    }

    // Form submit handler
    window.goToFindMedicine = async function(event) {
        event.preventDefault();
        const term = searchInput.value.trim();
        if (!term) return;

        // Try exact match or redirect with query
        try {
            const res = await API.get(`/api/medicines/suggestions?q=${encodeURIComponent(term)}`);
            if (res.suggestions && res.suggestions.length > 0) {
                // If top suggestion closely matches, select it
                selectSuggestion(res.suggestions[0]);
            } else {
                window.location.href = `FindMedi.html?q=${encodeURIComponent(term)}`;
            }
        } catch (err) {
            window.location.href = `FindMedi.html?q=${encodeURIComponent(term)}`;
        }
    };
});
