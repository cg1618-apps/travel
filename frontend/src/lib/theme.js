/**
 * Light or dark: the rule, with no React in it.
 *
 * The choice is stored as "light" or "dark"; nothing stored means follow the
 * OS. The same rule runs twice - in `index.html` before the first paint, so a
 * dark-mode phone never flashes bone paper, and in `useTheme` after it - and
 * the key and the rule are the media tracker's (`ThemeContext.jsx`).
 */

export const THEME_STORAGE_KEY = 'cg1618:theme'

/** A stored value that is not "light" or "dark" reads as no choice at all. */
export function storedChoice(value) {
  return value === 'light' || value === 'dark' ? value : null
}

/** What is on screen: the stored choice, else the OS preference. */
export function resolveTheme(stored, systemDark) {
  return storedChoice(stored) ?? (systemDark ? 'dark' : 'light')
}

/** The toggle flips what is on screen, whatever made it so. */
export function otherTheme(theme) {
  return theme === 'dark' ? 'light' : 'dark'
}
