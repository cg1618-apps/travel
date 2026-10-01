/** Enter commits, Escape reverts: the bargain every cell makes. */
export const keysFor = (commit, revert) => (event) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    commit()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    revert()
  }
}
