// TextileERP - Main JavaScript

// ─── Date Display ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const dateEl = document.getElementById('currentDate');
  if (dateEl) {
    const now = new Date();
    dateEl.textContent = now.toLocaleDateString('en-IN', {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
    });
  }

  // Auto-dismiss toasts after 4 seconds
  document.querySelectorAll('.toast-msg').forEach((t, i) => {
    setTimeout(() => t.remove(), 4000 + i * 500);
  });

  // Sidebar toggle
  const toggle = document.getElementById('sidebarToggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      document.body.classList.toggle('sidebar-collapsed');
      // Mobile
      document.getElementById('sidebar')?.classList.toggle('open');
    });
  }

  // Quick search
  const qs = document.getElementById('quickSearch');
  const sr = document.getElementById('searchResults');
  if (qs && sr) {
    let debounceTimer;
    qs.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      const q = this.value.trim();
      if (q.length < 2) { sr.classList.remove('show'); return; }
      debounceTimer = setTimeout(() => searchProducts(q), 300);
    });
    document.addEventListener('click', function (e) {
      if (!qs.contains(e.target) && !sr.contains(e.target)) {
        sr.classList.remove('show');
      }
    });
  }
});

function searchProducts(q) {
  const sr = document.getElementById('searchResults');
  fetch(`/api/product/search?q=${encodeURIComponent(q)}`)
    .then(r => r.json())
    .then(data => {
      if (!data.length) { sr.classList.remove('show'); return; }
      sr.innerHTML = data.map(p => `
        <div class="search-item" onclick="window.location='/products'">
          <div>
            <div class="search-item-name">${p.name}</div>
            <div style="font-size:11px;color:#8896a4">${p.category} · Stock: ${p.quantity}</div>
          </div>
          <div class="search-item-price">₹${p.price}</div>
        </div>`).join('');
      sr.classList.add('show');
    })
    .catch(() => {});
}

// ─── Show Toast ────────────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const icon = type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-circle' : 'info-circle';
  const toast = document.createElement('div');
  toast.className = `toast-msg toast-${type}`;
  toast.innerHTML = `<i class="fas fa-${icon} me-2"></i>${message}<button class="toast-close" onclick="this.parentElement.remove()">×</button>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ─── Loading Spinner ───────────────────────────────────────────────────────────
function showSpinner() {
  let el = document.getElementById('spinnerOverlay');
  if (!el) {
    el = document.createElement('div');
    el.id = 'spinnerOverlay';
    el.className = 'spinner-overlay show';
    el.innerHTML = '<div class="spinner-ring"></div>';
    document.body.appendChild(el);
  }
  el.classList.add('show');
}
function hideSpinner() {
  const el = document.getElementById('spinnerOverlay');
  if (el) el.classList.remove('show');
}

// ─── Confirm Delete ────────────────────────────────────────────────────────────
function confirmDelete(formId, message) {
  if (confirm(message || 'Are you sure you want to delete this item?')) {
    document.getElementById(formId).submit();
  }
}

// ─── Chart Defaults ────────────────────────────────────────────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
  Chart.defaults.color = '#8896a4';
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.padding = 16;
}

// ─── Geofence helpers ──────────────────────────────────────────────────────────
function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180;
  const dp = (lat2 - lat1) * Math.PI / 180;
  const dl = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dp/2)**2 + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Auto-hide pending leave badge from sidebar
document.addEventListener('DOMContentLoaded', function() {
  const badge = document.getElementById('pendingLeaveBadge');
  if (badge) {
    fetch('/leaves').then(r => {
      // badge count injected server-side — show if non-zero data attr
      const count = badge.dataset.count;
      if (count && parseInt(count) > 0) {
        badge.textContent = count;
        badge.style.display = 'inline-block';
      }
    }).catch(() => {});
  }
});
