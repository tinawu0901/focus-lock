const msg = key => chrome.i18n.getMessage(key);
document.getElementById('title').textContent = msg('title');
document.getElementById('connect').textContent = msg('reconnect');
async function show() {
  const value = await chrome.storage.local.get(['policy', 'connected', 'error']);
  const active = value.policy?.active && value.policy.expires_at * 1000 > Date.now();
  document.getElementById('status').textContent = (value.connected ? msg('connected') : msg('disconnected')) +
    '\n' + msg('restriction') + (active ? msg('enabled') : msg('disabled')) + '\n' + (active ? value.policy.urls.join('\n') : '') +
    (value.error ? '\n' + value.error : '');
}
document.getElementById('connect').onclick = () => chrome.runtime.sendMessage({type: 'CONNECT'}, show);
setInterval(show, 1000); show();
