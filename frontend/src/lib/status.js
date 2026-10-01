/**
 * One tap: 未打包 ⇄ 已打包. 不需打包 is set from the row menu, never by
 * tapping; tapping a 不需打包 row brings it back to 未打包.
 */
export function tapStatus(status) {
  return status === 'not_packed' ? 'packed' : 'not_packed'
}
