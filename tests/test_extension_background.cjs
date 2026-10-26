const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const callbacks = {};
const sent = [];
const values = {};
let sessionRules = [];
let openTabs = [];
let tick;
const event = name => ({addListener(callback) { callbacks[name] = callback; }});
const port = {onMessage: event('nativeMessage'), onDisconnect: event('disconnect'), postMessage(message) { sent.push(message); }};
const chrome = {
  runtime: {connectNative: () => port, onMessage: event('message'), onStartup: event('startup'), onInstalled: event('installed')},
  tabs: {query: async () => openTabs, onActivated: event('activated'), onUpdated: event('updated'), sendMessage: async () => {}},
  scripting: {executeScript: async () => {}},
  declarativeNetRequest: {getSessionRules: async () => sessionRules,
    updateSessionRules: async update => { sessionRules = update.addRules; }},
  storage: {local: {set: async update => Object.assign(values, update)}},
  action: {setBadgeText: async () => {}},
  alarms: {create: () => {}, onAlarm: event('alarm')}
};
const context = vm.createContext({chrome, navigator: {userAgent: 'Chrome'}, URL, Date, console,
  setInterval: callback => { tick = callback; }});
context.importScripts = name => vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../browser-extension', name), 'utf8'), context);
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../browser-extension/background.js'), 'utf8'), context);
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(resolve => setImmediate(resolve)); };
(async () => {
  assert.equal(sent[0].applied, false);
  callbacks.nativeMessage({active: true, revision: 'session1', urls: ['https://example.com/'], expires_at: Date.now() / 1000 + 60});
  await flush(); tick();
  assert.equal(sessionRules.length, 2);
  assert.equal(sent.at(-1).revision, 'session1');
  assert.equal(sent.at(-1).applied, true);
  callbacks.nativeMessage({active: false, revision: 'paused', urls: [], expires_at: Date.now() / 1000 + 60});
  await flush();
  assert.equal(sessionRules.length, 0);
  assert.equal(values.policy.active, false);
  openTabs = [{id: 1, title: 'Work', url: 'https://example.com/a'}, {id: 2, title: 'Private', url: 'https://private.example/', incognito: true},
    {id: 3, title: 'Settings', url: 'chrome://settings/'}];
  callbacks.nativeMessage({active: false, revision: 'list-tabs', urls: [], request_tabs: true, expires_at: Date.now()/1000 + 60});
  await flush(); tick();
  assert.equal(sent.at(-1).protocol, 3);
  assert.equal(sent.at(-1).tabs.length, 1);
  assert.equal(sent.at(-1).tabs[0].title, 'Work');
  callbacks.nativeMessage({active: false, revision: 'stop-tabs', urls: [], request_tabs: false, expires_at: Date.now()/1000 + 60});
  await flush(); tick(); assert.equal(sent.at(-1).tabs, null);
  callbacks.nativeMessage({active: true, revision: 'expired', urls: ['https://example.com/'], expires_at: 1});
  await flush();
  assert.equal(sessionRules.length, 0);
  callbacks.nativeMessage({active: true, revision: 'session2', urls: ['https://example.com/'], expires_at: Date.now() / 1000 + 60});
  await flush(); callbacks.disconnect(); await flush();
  assert.equal(sessionRules.length, 0);
  console.log('Extension worker lifecycle verified: apply acknowledgment, pause, expiry and disconnect cleanup.');
})().catch(error => { console.error(error); process.exitCode = 1; });
