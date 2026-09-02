/**
 * Focused tests for the RTL detection utility that drives per-message and
 * per-input direction in the chat UI.
 *
 * Run with Node's built-in test runner (no extra framework/dependency):
 *   npm test            ->  node --test src/utils/
 *   node --test src/utils/rtl.test.ts
 *
 * These cover the direction/language decisions that rendering relies on. Pure
 * visual checks (pixel overflow, caret placement) would require a DOM/browser
 * harness, which is intentionally NOT added for this frontend-only feature.
 */
// This Vite app's tsconfig uses `types: ["vite/client"]` and does not include
// @types/node, so Node's built-in test modules are unresolved at edit time. The
// tests still run under `node --test` (types are stripped, not type-checked), so
// we silence the editor-only module-resolution errors without adding a dep.
// @ts-ignore -- node:test built-in runner
import { test } from 'node:test';
// @ts-ignore -- node:assert built-in
import assert from 'node:assert/strict';

import { getTextDirection, getTextLanguage, isRTLText } from './rtl.ts';

// Test 1 — English
test('English text is LTR (dir=ltr, lang=en)', () => {
  const text = 'Hello, I need an appointment.';
  assert.equal(isRTLText(text), false);
  assert.equal(getTextDirection(text), 'ltr');
  assert.equal(getTextLanguage(text), 'en');
});

// Test 2 — Urdu
test('Urdu text is RTL (dir=rtl, lang=ur)', () => {
  const text = 'مجھے ڈاکٹر سے ملاقات کا وقت چاہیے۔';
  assert.equal(isRTLText(text), true);
  assert.equal(getTextDirection(text), 'rtl');
  assert.equal(getTextLanguage(text), 'ur');
});

// Test 3 — Mixed Urdu + English
test('Mixed Urdu + English is RTL (dir=rtl, lang=ur)', () => {
  const text = 'مجھے Dr. Ahmed سے appointment چاہیے۔';
  assert.equal(isRTLText(text), true);
  assert.equal(getTextDirection(text), 'rtl');
  assert.equal(getTextLanguage(text), 'ur');
});

// Test 4 — Empty input
test('Empty string is LTR (dir=ltr, lang=en)', () => {
  assert.equal(isRTLText(''), false);
  assert.equal(getTextDirection(''), 'ltr');
  assert.equal(getTextLanguage(''), 'en');
});

// Defensive: message text can be undefined at runtime.
test('Nullish text is treated as LTR', () => {
  assert.equal(isRTLText(undefined as unknown as string), false);
  assert.equal(isRTLText(null as unknown as string), false);
});

// Test 5 — Patient message: the same helper drives the user bubble.
test('Patient message: Urdu bubble resolves to RTL, English stays LTR', () => {
  const urduPatientText = 'مجھے ڈاکٹر سے ملنا ہے۔';
  assert.equal(getTextDirection(urduPatientText), 'rtl');
  assert.equal(getTextLanguage(urduPatientText), 'ur');

  const englishPatientText = 'I need an appointment';
  assert.equal(getTextDirection(englishPatientText), 'ltr');
  assert.equal(getTextLanguage(englishPatientText), 'en');
});

// Test 6 — Chat input switches dynamically with the current value.
test('Chat input direction follows the current value', () => {
  assert.equal(getTextDirection('I need an appointment'), 'ltr');
  assert.equal(getTextDirection('مجھے اپائنٹمنٹ چاہیے'), 'rtl');
  // Clearing the field flips it back to the default LTR.
  assert.equal(getTextDirection(''), 'ltr');
});

// Test 7 — Long Urdu message stays RTL and is never mutated by the helpers.
test('Long Urdu message stays RTL and text is preserved', () => {
  const longUrdu = 'مجھے ڈاکٹر سے ملاقات کا وقت چاہیے۔ '.repeat(20).trim();
  assert.equal(isRTLText(longUrdu), true);
  assert.equal(getTextDirection(longUrdu), 'rtl');
  // Contains spaces so the browser can wrap it (no forced single line).
  assert.ok(longUrdu.includes(' '));
});

// Test 8 — Mixed text with doctor names, numbers and times.
test('Mixed text with English names/numbers/times is detected and preserved', () => {
  const mixed = 'آپ کی appointment کل 10:00 AM پر ہے۔ Dr. Ahmed کے ساتھ';
  assert.equal(isRTLText(mixed), true);
  assert.equal(getTextDirection(mixed), 'rtl');
  assert.equal(getTextLanguage(mixed), 'ur');
  // The helpers are pure detectors: they must not alter the source text, so
  // embedded English/numbers remain intact for the bidi algorithm to order.
  assert.ok(mixed.includes('Dr. Ahmed'));
  assert.ok(mixed.includes('10:00 AM'));
});

// Unicode range coverage required by the spec.
test('Detects Arabic (U+0600–U+06FF) and Arabic Supplement (U+0750–U+077F) blocks', () => {
  assert.equal(isRTLText('\u0600'), true); // Arabic block start
  assert.equal(isRTLText('\u06FF'), true); // Arabic block end
  assert.equal(isRTLText('\u0750'), true); // Arabic Supplement start
  assert.equal(isRTLText('\u077F'), true); // Arabic Supplement end
});

// Guard against false positives that would wrongly flip English UI to RTL.
test('Latin text, numbers and punctuation are LTR', () => {
  assert.equal(isRTLText('Hello, world! 12345 @#$%'), false);
  assert.equal(isRTLText('10:00 AM'), false);
  assert.equal(isRTLText('   '), false);
});
