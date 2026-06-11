import { CATEGORIES, PRODUCTS } from './data.js';
import { buildComparisonTable } from './compare.js';
import { debounceFilter, toggleGroup, collapseAll, expandAll, showDifferencesOnly } from './filter.js';
import { syncToURL, readFromURL, onHashChange } from './url.js';

const selectedIds = new Set();

function init() {
  renderCategoryTabs();
  renderProductCards(PRODUCTS);
  wireEvents();

  const state = readFromURL();
  if (state.ids.length >= 2) {
    state.ids.forEach(id => {
      if (PRODUCTS.find(p => p.id === id)) selectedIds.add(id);
    });
    updateCompareBar();
    if (selectedIds.size >= 2) {
      showComparison();
      if (state.filter) {
        document.getElementById('search-input').value = state.filter;
        const table = document.querySelector('.compare-table');
        if (table) debounceFilter(state.filter, table, 0);
      }
    }
  }

  onHashChange(state => {
    selectedIds.clear();
    state.ids.forEach(id => {
      if (PRODUCTS.find(p => p.id === id)) selectedIds.add(id);
    });
    updateSelectionUI();
    updateCompareBar();
    if (selectedIds.size >= 2) {
      showComparison();
    } else {
      hideComparison();
    }
  });
}

function renderCategoryTabs() {
  const container = document.getElementById('category-tabs');
  Object.entries(CATEGORIES).forEach(([catId, cat]) => {
    const btn = document.createElement('button');
    btn.className = 'cat-tab';
    btn.dataset.category = catId;
    btn.textContent = cat.name;
    container.appendChild(btn);
  });
}

function renderProductCards(products) {
  const grid = document.getElementById('product-grid');
  grid.innerHTML = '';
  products.forEach(product => {
    const cat = CATEGORIES[product.category];
    const card = document.createElement('div');
    card.className = 'product-card';
    card.dataset.id = product.id;
    if (selectedIds.has(product.id)) card.classList.add('selected');

    const keySpecs = getKeySpecs(product);
    card.innerHTML = `
      <div class="card-check">${selectedIds.has(product.id) ? '&#10003;' : ''}</div>
      <span class="card-badge">${cat?.name || ''}</span>
      <h3 class="card-title">${product.name}</h3>
      <p class="card-subtitle">${product.subtitle}</p>
      <ul class="card-specs">${keySpecs.map(s => `<li><span class="spec-label">${s.label}</span><span class="spec-value">${s.value}</span></li>`).join('')}</ul>
    `;
    grid.appendChild(card);
  });
}

function getKeySpecs(product) {
  const cat = CATEGORIES[product.category];
  if (!cat) return [];
  const first3 = cat.paramGroups[0]?.params.slice(0, 3) || [];
  return first3.map(p => ({
    label: p.paramName,
    value: formatPreview(product.values[p.paramId], p)
  }));
}

function formatPreview(val, param) {
  if (val === null || val === undefined) return '—';
  if (param.type === 'boolean') return val ? '支持' : '不支持';
  if (param.unit && typeof val === 'number') return val + ' ' + param.unit;
  return String(val);
}

function wireEvents() {
  document.getElementById('product-grid').addEventListener('click', e => {
    const card = e.target.closest('.product-card');
    if (!card) return;
    handleProductSelect(Number(card.dataset.id));
  });

  document.getElementById('category-tabs').addEventListener('click', e => {
    const tab = e.target.closest('.cat-tab');
    if (!tab) return;
    document.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const cat = tab.dataset.category;
    const filtered = cat === 'all' ? PRODUCTS : PRODUCTS.filter(p => p.category === cat);
    renderProductCards(filtered);
  });

  document.getElementById('compare-btn').addEventListener('click', () => {
    if (selectedIds.size >= 2) showComparison();
  });

  document.getElementById('back-btn').addEventListener('click', () => {
    hideComparison();
  });

  document.getElementById('search-input').addEventListener('input', e => {
    const table = document.querySelector('.compare-table');
    if (table) {
      debounceFilter(e.target.value, table);
      syncToURL([...selectedIds], e.target.value);
    }
  });

  document.getElementById('diff-only').addEventListener('change', e => {
    const table = document.querySelector('.compare-table');
    if (table) showDifferencesOnly(e.target.checked, table);
  });

  document.getElementById('collapse-all-btn').addEventListener('click', () => {
    const table = document.querySelector('.compare-table');
    if (table) collapseAll(table);
  });

  document.getElementById('expand-all-btn').addEventListener('click', () => {
    const table = document.querySelector('.compare-table');
    if (table) expandAll(table);
  });
}

function handleProductSelect(productId) {
  if (selectedIds.has(productId)) {
    selectedIds.delete(productId);
  } else if (selectedIds.size < 4) {
    selectedIds.add(productId);
  }
  updateSelectionUI();
  updateCompareBar();
  syncToURL([...selectedIds], '');
}

function updateSelectionUI() {
  document.querySelectorAll('.product-card').forEach(card => {
    const id = Number(card.dataset.id);
    const isSelected = selectedIds.has(id);
    card.classList.toggle('selected', isSelected);
    const check = card.querySelector('.card-check');
    if (check) check.innerHTML = isSelected ? '&#10003;' : '';
  });
}

function updateCompareBar() {
  const count = selectedIds.size;
  document.getElementById('select-count').textContent = count;
  const btn = document.getElementById('compare-btn');
  btn.disabled = count < 2;

  const bar = document.getElementById('compare-bar');
  bar.classList.toggle('has-selection', count > 0);
}

function showComparison() {
  const products = PRODUCTS.filter(p => selectedIds.has(p.id));
  if (products.length < 2) return;

  const wrapper = document.getElementById('compare-table-wrapper');
  wrapper.innerHTML = '';
  const table = buildComparisonTable(products);
  wrapper.appendChild(table);

  table.addEventListener('click', e => {
    const toggle = e.target.closest('.collapse-toggle');
    if (!toggle) return;
    const header = toggle.closest('.group-header');
    if (header) toggleGroup(header.dataset.group, table);
  });

  document.getElementById('compare-area').classList.remove('hidden');
  document.querySelector('.page-header').classList.add('hidden');
  document.getElementById('category-tabs').classList.add('hidden');
  document.getElementById('product-grid').classList.add('hidden');
  document.getElementById('compare-bar').classList.add('hidden');

  document.getElementById('search-input').value = '';
  document.getElementById('diff-only').checked = false;

  syncToURL([...selectedIds], '');
}

function hideComparison() {
  document.getElementById('compare-area').classList.add('hidden');
  document.querySelector('.page-header').classList.remove('hidden');
  document.getElementById('category-tabs').classList.remove('hidden');
  document.getElementById('product-grid').classList.remove('hidden');
  document.getElementById('compare-bar').classList.remove('hidden');
  updateSelectionUI();
}

document.addEventListener('DOMContentLoaded', init);
