export function syncToURL(selectedIds, filterText) {
  let hash = '';
  if (selectedIds.length > 0) {
    hash = 'ids=' + selectedIds.join(',');
    if (filterText) {
      hash += '&q=' + encodeURIComponent(filterText);
    }
  }
  const newHash = hash ? '#' + hash : '';
  if (window.location.hash !== newHash) {
    history.replaceState(null, '', newHash || window.location.pathname);
  }
}

export function parseHash(hash) {
  if (!hash) return { ids: [], filter: '' };

  const params = {};
  hash.split('&').forEach(part => {
    const [key, val] = part.split('=');
    if (key && val !== undefined) {
      params[key] = decodeURIComponent(val);
    }
  });

  const ids = params.ids
    ? params.ids.split(',').map(Number).filter(n => !isNaN(n) && n > 0)
    : [];

  return { ids, filter: params.q || '' };
}

export function readFromURL() {
  return parseHash(window.location.hash.slice(1));
}

export function onHashChange(callback) {
  window.addEventListener('hashchange', () => {
    callback(readFromURL());
  });
}
