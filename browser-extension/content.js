if (!globalThis.__focusLockGuard) {
  globalThis.__focusLockGuard = true;
  let policy = {active: false, urls: [], expires_at: 0};
  let overlay = null;
  function guarded() {
    return policy.active && policy.expires_at * 1000 > Date.now() && !FocusLockRules.allowed(location.href, policy.urls || []);
  }
  function render() {
    if (!guarded()) { overlay?.remove(); overlay = null; return; }
    if (!document.documentElement) return;
    if (!overlay || !overlay.isConnected) {
      overlay = document.createElement('div');
      overlay.style.cssText = 'all:initial!important;position:fixed!important;inset:0!important;z-index:2147483647!important;display:flex!important;align-items:center!important;justify-content:center!important;background:#171c29!important;pointer-events:auto!important;';
      const shadow = overlay.attachShadow({mode: 'closed'});
      const message = document.createElement('div');
      message.style.cssText = 'color:#ecf0ff;font:20px system-ui;text-align:center;line-height:1.8;padding:30px';
      message.textContent = chrome.i18n.getMessage('blockedMessage');
      shadow.append(message); document.documentElement.append(overlay);
      document.activeElement?.blur?.();
    }
  }
  chrome.runtime.onMessage.addListener(message => { if (message.type === 'POLICY') { policy = message.policy; render(); } });
  function refresh() {
    try {
      chrome.runtime.sendMessage({type: 'GET_POLICY'}, next => {
        if (!chrome.runtime.lastError && next) policy = next;
        render();
      });
    } catch (_) { render(); }
    render();
  }
  for (const type of ['keydown', 'keypress', 'keyup', 'pointerdown', 'click', 'wheel', 'touchstart']) {
    window.addEventListener(type, event => {
      if (guarded()) { event.preventDefault(); event.stopImmediatePropagation(); render(); }
    }, {capture: true, passive: false});
  }
  setInterval(refresh, 1000);
  window.addEventListener('popstate', refresh);
  window.addEventListener('hashchange', refresh);
  refresh();
}
