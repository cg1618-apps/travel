/**
 * Shared by every cell that cannot be blank: an emptied cell keeps its value.
 *
 * `TextCell` commits a blanked cell as null; wrapping its `onCommit` in this
 * refuses that client-side instead of sending a null the API would 422.
 */
export const required = (commit) => (value) => {
  if (value) commit(value)
}
