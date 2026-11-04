/**
 * A few mutually exclusive choices side by side, the current one filled:
 * 未買票 / 無需買票 / 已買票 and 單程 / 來回 in a trip's header. One tap
 * commits, as a select would, without the select's extra tap to open it.
 */

export function Segmented({ value, options, labels, ariaLabel, onChange }) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex overflow-hidden rounded-md border border-border-strong">
      {options.map((option, index) => {
        const chosen = option === value
        return (
          <button
            key={String(option)}
            type="button"
            role="radio"
            aria-checked={chosen}
            onClick={() => {
              if (!chosen) onChange(option)
            }}
            className={`px-3 text-sm ${index > 0 ? 'border-l border-border-strong' : ''} ${
              chosen ? 'bg-brand text-on-brand' : 'bg-transparent text-text-muted'
            }`}
            style={{ minHeight: 32 }}
          >
            {labels[String(option)]}
          </button>
        )
      })}
    </div>
  )
}
