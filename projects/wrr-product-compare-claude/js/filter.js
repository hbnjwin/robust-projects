let debounceTimer = null;

export function filterParams(searchText, tableElement) {
  const rows = tableElement.querySelectorAll('.param-row');
  const groupHeaders = tableElement.querySelectorAll('.group-header');
  const query = searchText.trim().toLowerCase();

  rows.forEach(row => {
    if (!query) {
      row.classList.remove('filter-hidden');
      return;
    }
    const paramName = row.querySelector('.param-name')?.textContent?.toLowerCase() || '';
    const values = Array.from(row.querySelectorAll('.param-value'))
      .map(el => el.textContent.toLowerCase())
      .join(' ');
    const match = paramName.includes(query) || values.includes(query);
    row.classList.toggle('filter-hidden', !match);
  });

  groupHeaders.forEach(header => {
    const groupId = header.dataset.group;
    const groupRows = tableElement.querySelectorAll(`.param-row[data-group="${groupId}"]`);
    const allHidden = Array.from(groupRows).every(r =>
      r.classList.contains('filter-hidden') || r.classList.contains('diff-hidden')
    );
    header.classList.toggle('filter-hidden', allHidden && !!query);
  });
}

export function debounceFilter(searchText, tableElement, delay = 150) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => filterParams(searchText, tableElement), delay);
}

export function toggleGroup(groupId, tableElement) {
  const header = tableElement.querySelector(`.group-header[data-group="${groupId}"]`);
  if (!header) return;

  const collapsed = header.classList.toggle('collapsed');
  const rows = tableElement.querySelectorAll(`.param-row[data-group="${groupId}"]`);
  rows.forEach(row => row.classList.toggle('group-collapsed', collapsed));
}

export function collapseAll(tableElement) {
  tableElement.querySelectorAll('.group-header').forEach(h => {
    h.classList.add('collapsed');
  });
  tableElement.querySelectorAll('.param-row').forEach(r => {
    r.classList.add('group-collapsed');
  });
}

export function expandAll(tableElement) {
  tableElement.querySelectorAll('.group-header').forEach(h => {
    h.classList.remove('collapsed');
  });
  tableElement.querySelectorAll('.param-row').forEach(r => {
    r.classList.remove('group-collapsed');
  });
}

export function showDifferencesOnly(enabled, tableElement) {
  const rows = tableElement.querySelectorAll('.param-row');
  rows.forEach(row => {
    if (enabled && !row.classList.contains('param-diff')) {
      row.classList.add('diff-hidden');
    } else {
      row.classList.remove('diff-hidden');
    }
  });

  const groupHeaders = tableElement.querySelectorAll('.group-header');
  groupHeaders.forEach(header => {
    const groupId = header.dataset.group;
    const groupRows = tableElement.querySelectorAll(`.param-row[data-group="${groupId}"]`);
    const allHidden = Array.from(groupRows).every(r =>
      r.classList.contains('diff-hidden') || r.classList.contains('filter-hidden')
    );
    header.classList.toggle('diff-hidden', allHidden && enabled);
  });
}
