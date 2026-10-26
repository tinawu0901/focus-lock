const assert = require('node:assert/strict');
const {allowed, regexFor, makeRules} = require('../browser-extension/rules.js');
const entries = ['https://chatgpt.com/', 'https://docs.ros.org/en', 'https://example.com/watch?v=learning'];
for (const [url, expected] of [
  ['https://chatgpt.com/c/abc', true], ['https://chatgpt.com.evil.example/', false],
  ['https://sub.chatgpt.com/', false], ['http://chatgpt.com/', false],
  ['https://docs.ros.org/en/humble/', true], ['https://docs.ros.org/english', false],
  ['https://facebook.com/', false], ['https://example.com/watch?v=learning', true],
  ['https://example.com/watch?v=gaming', false]
]) {
  assert.equal(allowed(url, entries), expected, url);
  assert.equal(entries.some(entry => new RegExp(regexFor(entry)).test(url)), expected, 'DNR: ' + url);
}
assert.equal(makeRules(entries)[0].action.type, 'redirect');
assert.equal(makeRules(entries)[1].action.type, 'allowAllRequests');
assert.throws(() => makeRules([]));
assert.equal(allowed('https://docs.ros.org/en', ['https://docs.ros.org/en/']), true);
assert.equal(allowed('https://example.com/watch/child?v=learning', entries), false);
console.log('Extension URL and DNR rule tests passed (9 cases + rule validation).');
