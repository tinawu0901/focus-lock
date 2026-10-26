const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..', 'browser-extension');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
assert.equal(manifest.default_locale, 'en');
const en = JSON.parse(fs.readFileSync(path.join(root, '_locales/en/messages.json'), 'utf8'));
const zh = JSON.parse(fs.readFileSync(path.join(root, '_locales/zh_TW/messages.json'), 'utf8'));
assert.deepEqual(Object.keys(en).sort(), Object.keys(zh).sort());
for (const catalog of [en, zh]) {
  const elements = Object.fromEntries(['heading', 'message'].map(id => [id, {textContent: ''}]));
  vm.runInNewContext(fs.readFileSync(path.join(root, 'blocked.js'), 'utf8'), {
    document: {getElementById: id => elements[id]},
    chrome: {i18n: {getMessage: key => catalog[key].message}},
  });
  assert.equal(elements.message.textContent, catalog.blockedMessage.message);
  assert.ok(elements.heading.textContent);
}
console.log('Extension English / Traditional Chinese messages verified.');
