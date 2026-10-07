import { backupErrorMessage, backupRowTotal } from './backup'

describe('backupRowTotal', () => {
  it('sums every table', () => {
    expect(backupRowTotal({ packing_lists: 2, packing_items: 40, trips: 1 })).toBe(43)
  })

  it('is zero with no tables', () => {
    expect(backupRowTotal({})).toBe(0)
    expect(backupRowTotal(undefined)).toBe(0)
  })
})

describe('backupErrorMessage', () => {
  it('has its own sentence for each refusal the backup makes', () => {
    expect(backupErrorMessage({ status: 409 })).toBe('已有備份正在進行，請稍後再試。')
    expect(backupErrorMessage({ status: 422 })).toBe('資料庫是空的，沒有可以備份的資料。')
    expect(backupErrorMessage({ status: 503 })).toBe('無法使用 Google Sheets：連不上，或尚未設定。')
  })

  it('falls back for any other status, and for no response at all', () => {
    expect(backupErrorMessage({ status: 500 })).toBe('備份失敗。')
    expect(backupErrorMessage(new TypeError('Failed to fetch'))).toBe('無法連線，請稍後再試。')
  })
})
