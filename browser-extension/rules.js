/* Shared rule semantics for the service worker, content guard and Node tests. */
(function(root) {
  function normalizeRule(value) {
    const url = new URL(value.includes('://') ? value : 'https://' + value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Invalid website URL');
    url.hash = '';
    return url;
  }
  function allowed(value, entries) {
    try {
      const url = new URL(value);
      return entries.some(entry => {
        const rule = normalizeRule(entry);
        const path = rule.pathname.replace(/\/$/, '') || '/';
        if (rule.search) return url.origin === rule.origin && url.pathname === rule.pathname && rule.search === url.search;
        const matchesPath = path === '/' || url.pathname === path || url.pathname.startsWith(path.endsWith('/') ? path : path + '/');
        return url.origin === rule.origin && matchesPath;
      });
    } catch (_) { return false; }
  }
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function regexFor(entry) {
    const url = normalizeRule(entry);
    if (url.search) return '^' + escape(url.origin + url.pathname + url.search) + '(?:#.*)?$';
    if (url.pathname === '/') return '^' + escape(url.origin) + '(?:/|$)';
    const path = url.pathname.endsWith('/') ? url.pathname.slice(0, -1) : url.pathname;
    return '^' + escape(url.origin + path) + '(?:/|[?#]|$)';
  }
  function makeRules(entries) {
    if (!Array.isArray(entries) || !entries.length || entries.length > 200) throw new Error('Allow 1–200 website rules');
    return [{id: 1, priority: 1, action: {type: 'redirect', redirect: {extensionPath: '/blocked.html'}},
      condition: {regexFilter: '^https?://', resourceTypes: ['main_frame']}},
      ...entries.map((entry, index) => ({id: index + 2, priority: 10, action: {type: 'allowAllRequests'},
        condition: {regexFilter: regexFor(entry), isUrlFilterCaseSensitive: true, resourceTypes: ['main_frame']}}))];
  }
  const api = {allowed, regexFor, makeRules};
  root.FocusLockRules = api;
  if (typeof module !== 'undefined') module.exports = api;
})(globalThis);
