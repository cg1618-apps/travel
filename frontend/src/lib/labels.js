/**
 * Every display string for a stored value, in the owner's sheet's own words.
 *
 * Stored values stay English enum text; this is the one place they become
 * what the screen says. A value missing here is a blank on screen, which is
 * why labels.test.js walks every vocabulary.
 */

export const STATUS_LABELS = { not_packed: '未打包', packed: '已打包', no_need: '不需打包' }

export const TIMING_LABELS = {
  whenever: '隨時',
  night_before: '出發前晚',
  day_of: '出發當天',
  just_before: '出發前',
}

export const NEEDS = ['need', 'bring', 'buy']
export const NEED_LABELS = { need: '需要', bring: '需帶', buy: '需買' }

/** Double Check is two fields; on screen it is one of three states. */
export const CHECK_STATES = ['off', 'needed', 'done']
export const CHECK_LABELS = { off: '不需確認', needed: '未確認', done: '確認' }
export const CHECK_FIELDS = {
  off: { needs_double_check: false, double_checked: false },
  needed: { needs_double_check: true, double_checked: false },
  done: { needs_double_check: true, double_checked: true },
}
export function checkState(item) {
  if (!item.needs_double_check) return 'off'
  return item.double_checked ? 'done' : 'needed'
}

export const DAY_TYPE_LABELS = { weekday: '平日', holiday: '假日' }
export const BUCKET_LABELS = { morning: '早', midday: '中', afternoon: '下午', evening: '晚' }
export const LEG_LABELS = { outbound: '去程', return: '回程' }
export const LABEL_KIND_LABELS = {
  category: '類別', bag: '包包', location: '取得地點', ticket_type: '車票類型',
}
export const BOOKING_LABELS = { booked: '已訂票', paid: '付款', collected: '取票' }
export const ADVANCE_TICKET_LABELS = { true: '需要', false: '不需要' }

/** Which shelf a list or trip is on. 自動保存 is free + past, not a stored kind. */
export const KIND_LABELS = { template: '範本', saved: '保存', free: '一般' }
export const AUTO_SAVED_LABEL = '自動保存'

export const USAGES = ['in_use', 'upcoming', 'unused', 'past']
export const USAGE_LABELS = {
  in_use: '使用中',
  upcoming: '未來使用',
  unused: '未使用',
  past: '過去使用',
}
