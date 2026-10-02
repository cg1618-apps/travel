/**
 * 一般 · 範本 · 保存 · 自動保存, as browser tabs over one panel.
 *
 * The tab lives in `?tab=` so Back and a reload come back to it; 一般 is the
 * bare URL. Shared by /lists and /trips, which differ only in the panel.
 */

import { useSearchParams } from 'react-router-dom'

import { TABS, tabFromSearch } from '../lib/kinds'

export function IndexTabs({ counts, children }) {
  const [params, setParams] = useSearchParams()
  const active = tabFromSearch(params.get('tab'))
  const select = (key) => setParams(key === 'free' ? {} : { tab: key }, { replace: true })

  return (
    <div className="mt-6">
      {/* The scroller and the baseline are two boxes. `overflow-x-auto` also
          sets overflow-y, so a tab's -mb-px reaching past a scroller that drew
          the baseline itself showed a vertical scrollbar; inside this inner
          row it only overlaps the row's own border, which is what joins the
          active tab to the panel. */}
      <div className="overflow-x-auto">
        <div role="tablist" className="flex min-w-max gap-1 border-b border-border px-4">
          {TABS.map((tab) => {
            const selected = tab.key === active
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => select(tab.key)}
                className={`-mb-px shrink-0 rounded-t-md border px-3 py-1.5 text-sm ${
                  selected
                    ? 'border-border border-b-surface bg-surface font-semibold text-text'
                    : 'border-transparent text-text-muted hover:text-text'
                }`}
              >
                {tab.label}
                <span className="ml-1 text-xs font-normal tabular-nums text-text-faint">
                  {counts[tab.key]}
                </span>
              </button>
            )
          })}
        </div>
      </div>
      <div role="tabpanel" className="bg-surface">
        {children(active)}
      </div>
    </div>
  )
}
