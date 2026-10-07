/**
 * 備份到 Google Sheets: one button that copies every table to the Travel
 * sheet. No confirmation — a backup cannot lose data; it refuses rather than
 * blank a tab, and refuses outright when every table is empty.
 *
 * Restoring is deliberately not here. It replaces every table, so it is a
 * command (`scripts/restore_sheet.py`), not a tap.
 */

import { useEffect } from 'react'

import { endpoints } from '../api/endpoints'
import { send, useApiMutation } from '../hooks/useApiQuery'
import { backupErrorMessage, backupRowTotal } from '../lib/backup'
import { formatTaipei } from '../lib/trips'

export default function BackupSection() {
  const backup = useApiMutation({
    mutationFn: () => send(endpoints.backup(), 'POST'),
  })

  useEffect(() => {
    if (backup.error) console.error(backup.error)
  }, [backup.error])

  return (
    <section className="mx-4 mt-10 border-t border-border pt-6">
      <h2 className="m-0 text-base font-semibold">備份到 Google Sheets</h2>
      <p className="mt-1 mb-3 text-sm text-text-faint">
        把所有資料複製到 Travel 試算表。還原要在命令列執行
        <code className="mx-1">scripts/restore_sheet.py</code>。
      </p>

      <button
        type="button"
        onClick={() => backup.mutate()}
        disabled={backup.isPending}
        className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand disabled:opacity-50"
      >
        {backup.isPending ? '備份中…' : '立即備份'}
      </button>

      {backup.isSuccess && (
        <p className="mt-3 rounded-md bg-brand-soft px-3 py-2 text-sm text-brand" role="status">
          已備份 {formatTaipei(backup.data.backed_up_at)}，共{' '}
          {backupRowTotal(backup.data.rows)} 筆資料。
        </p>
      )}

      {backup.isError && (
        <div
          className="mt-3 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-text"
          role="alert"
        >
          {backupErrorMessage(backup.error)}
          {backup.error?.status && (
            <span className="text-text-faint">（{backup.error.status}）</span>
          )}
        </div>
      )}
    </section>
  )
}
