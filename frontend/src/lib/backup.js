/**
 * The 備份 section's words: how many rows a backup wrote, and what a refusal
 * says. Pure, so every status is tested without rendering anything.
 *
 * The refusal is this app's own sentence rather than the API's `detail`, which
 * is English by contract — the same rule `ErrorState` follows. Each status the
 * backup can refuse with has its own, because they ask for different things:
 * wait (409), fix the Sheets setup (503), or notice the database is empty (422).
 */

export function backupRowTotal(rows) {
  return Object.values(rows ?? {}).reduce((sum, count) => sum + count, 0)
}

const REFUSALS = {
  409: '已有備份正在進行，請稍後再試。',
  422: '資料庫是空的，沒有可以備份的資料。',
  503: '無法使用 Google Sheets：連不上，或尚未設定。',
}

export function backupErrorMessage(error) {
  if (!error?.status) return '無法連線，請稍後再試。'
  return REFUSALS[error.status] ?? '備份失敗。'
}
