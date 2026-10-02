/**
 * The theme on screen, and a toggle that remembers the choice.
 *
 * The only DOM side effect is `<html data-theme>`, which `index.css` keys
 * every semantic colour off. With nothing stored the page follows the OS,
 * live. Storage can be unavailable (a private window); the choice then lasts
 * for the visit.
 */

import { useEffect, useState } from 'react'

import { THEME_STORAGE_KEY, otherTheme, resolveTheme, storedChoice } from '../lib/theme'

const QUERY = '(prefers-color-scheme: dark)'

function readStored() {
  try {
    return storedChoice(localStorage.getItem(THEME_STORAGE_KEY))
  } catch {
    return null
  }
}

function systemPrefersDark() {
  try {
    return window.matchMedia(QUERY).matches
  } catch {
    return false
  }
}

export function useTheme() {
  const [stored, setStored] = useState(readStored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)
  const theme = resolveTheme(stored, systemDark)

  useEffect(() => {
    let media
    try {
      media = window.matchMedia(QUERY)
    } catch {
      return undefined
    }
    const onChange = (event) => setSystemDark(event.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  const toggle = () => {
    const next = otherTheme(theme)
    setStored(next)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      /* storage unavailable: the choice lasts for this visit */
    }
  }

  return { theme, toggle }
}
