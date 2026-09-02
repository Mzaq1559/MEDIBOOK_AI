/**
 * Lightweight, framework-agnostic helpers for detecting Urdu/Arabic-script text.
 *
 * These let individual chat bubbles and the message input render with the
 * correct direction (RTL) and language, without ever changing the global
 * application direction. This module is presentation-only: it never mutates
 * message text and never touches chat/API behaviour.
 */

/**
 * Unicode blocks that indicate right-to-left Urdu/Arabic script:
 *   - U+0600–U+06FF  Arabic
 *   - U+0750–U+077F  Arabic Supplement
 *
 * A single matching character is enough to treat the string as RTL, which also
 * covers mixed text such as "مجھے Dr. Ahmed سے appointment چاہیے۔".
 */
const RTL_SCRIPT_PATTERN = /[\u0600-\u06FF\u0750-\u077F]/;

/**
 * Returns `true` when the text contains at least one Urdu/Arabic-script
 * character. Empty (or nullish) text is treated as non-RTL.
 */
export function isRTLText(text: string): boolean {
  if (!text) return false;
  return RTL_SCRIPT_PATTERN.test(text);
}

/** Resolves the `dir` attribute value for a piece of text. */
export function getTextDirection(text: string): 'rtl' | 'ltr' {
  return isRTLText(text) ? 'rtl' : 'ltr';
}

/** Resolves the `lang` attribute value for a piece of text. */
export function getTextLanguage(text: string): 'ur' | 'en' {
  return isRTLText(text) ? 'ur' : 'en';
}
