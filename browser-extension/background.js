importScripts('rules.js');
let port = null;
let policy = {active: false, urls: [], expires_at: 0};
let appliedRevision = '';
let applied = false;
let error = '';
let processing = Promise.resolve();
let tabSnapshot = null;
const browserName = navigator.userAgent.includes('Edg/') ? 'edge' : 'chrome';

async function informTabs() {
  const tabs = await chrome.tabs.query({});
  await Promise.all(tabs.map(async tab => {
    if (!/^https?:\/\//.test(tab.url || '')) return;
    try {
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['rules.js', 'content.js']});
      await chrome.tabs.sendMessage(tab.id, {type: 'POLICY', policy});
    } catch (_) { /* Protected browser pages cannot be injected. */ }
  }));
}

async function applyPolicy(next) {
  const enabled = next.active === true && next.expires_at * 1000 > Date.now();
  const revision = next.revision || '';
  const changed = revision !== appliedRevision || enabled !== policy.active;
  policy = {...next, active: enabled};
  tabSnapshot = next.request_tabs ? (await chrome.tabs.query({})).filter(tab => !tab.incognito && /^https?:\/\//.test(tab.url || '')).slice(0, 100)
    .map(tab => ({title: (tab.title || '').slice(0, 160), url: tab.url.slice(0, 2048)})) : null;
  if (changed || !applied) {
    const previous = await chrome.declarativeNetRequest.getSessionRules();
    await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: previous.map(rule => rule.id),
      addRules: enabled ? FocusLockRules.makeRules(next.urls) : []});
    appliedRevision = revision;
    applied = true;
  }
  error = '';
  await chrome.storage.local.set({policy, error, connected: Boolean(port)});
  await chrome.action.setBadgeText({text: enabled ? 'ON' : ''});
  if (changed) await informTabs();
}

function ping() {
  if (port) {
    try { port.postMessage({browser: browserName, revision: appliedRevision, applied, error, protocol: 3, tabs: tabSnapshot}); }
    catch (_) { port = null; }
  }
}

function connect() {
  if (port) return;
  try {
    const connection = chrome.runtime.connectNative('com.focuslock.bridge');
    port = connection;
    connection.onMessage.addListener(next => {
      processing = processing.then(() => applyPolicy(next)).catch(async exc => {
        applied = false; error = String(exc);
        await chrome.storage.local.set({error, connected: true});
      });
    });
    connection.onDisconnect.addListener(() => {
      error = chrome.runtime.lastError?.message || 'Local bridge disconnected';
      if (port === connection) port = null;
      applied = false;
      processing = processing.then(() => applyPolicy({active: false, urls: [], revision: 'disconnected', expires_at: 0}));
      chrome.storage.local.set({connected: false, error});
    });
    ping();
  } catch (exc) { error = String(exc); }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message.type === 'GET_POLICY') {
    respond({...policy, active: policy.active && policy.expires_at * 1000 > Date.now()});
  }
  if (message.type === 'CONNECT') { connect(); ping(); respond({ok: true}); }
});
chrome.tabs.onActivated.addListener(() => informTabs());
chrome.tabs.onUpdated.addListener((id, change) => { if (change.url || change.status === 'complete') informTabs(); });
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.alarms.create('reconnect', {periodInMinutes: 0.5});
chrome.alarms.onAlarm.addListener(() => { connect(); ping(); });
setInterval(() => {
  if (policy.active && policy.expires_at * 1000 <= Date.now()) {
    processing = processing.then(() => applyPolicy({active: false, urls: [], revision: 'expired', expires_at: 0}));
  }
  connect(); ping();
}, 1000);
connect();
