/**
 * One line on a packing list, as it looks standing over an open suitcase.
 *
 * The whole row is the status control. Tapping cycles not_packed -> packed ->
 * no_need, so working down a list is one thumb and no aiming; the secondary
 * controls are separate targets that stop the tap propagating.
 */

const NEXT_STATUS = {
  not_packed: 'packed',
  packed: 'no_need',
  no_need: 'not_packed',
}

const STATUS_MARK = {
  not_packed: '○',
  packed: '●',
  no_need: '—',
}

const STATUS_LABEL = {
  not_packed: 'Not packed',
  packed: 'Packed',
  no_need: 'No need',
}

function Quantity({ item }) {
  if (item.quantity === null || item.quantity === undefined) return null
  const short = item.quantity_packed < item.quantity
  return (
    <span className={short ? 'text-warning' : 'text-text-faint'}>
      {item.quantity_packed} / {item.quantity}
      {item.unit ? ` ${item.unit}` : ''}
    </span>
  )
}

export function ItemRow({ item, onCycleStatus, onToggleDoubleCheck, onEdit }) {
  const resolved = item.status !== 'not_packed'
  // Packed and still unverified is the state the second field exists for, so
  // it has to be visible ON a packed row rather than instead of one.
  const outstanding = item.needs_double_check && !item.double_checked

  return (
    <li className="border-b border-border last:border-b-0">
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={() => onCycleStatus(item, NEXT_STATUS[item.status])}
          aria-label={`${item.name}: ${STATUS_LABEL[item.status]}. Tap to change.`}
          className="flex flex-1 items-center gap-3 px-4 py-3 text-left"
        >
          <span
            aria-hidden="true"
            className={`w-5 shrink-0 text-center text-lg ${
              item.status === 'packed' ? 'text-brand' : 'text-text-faint'
            }`}
          >
            {STATUS_MARK[item.status]}
          </span>

          <span className="min-w-0 flex-1">
            <span
              className={`block truncate ${
                item.status === 'no_need' ? 'text-text-faint line-through' : ''
              } ${resolved && item.status === 'packed' ? 'text-text-muted' : ''}`}
            >
              {item.name}
            </span>
            <span className="mt-0.5 flex flex-wrap gap-x-2 text-xs">
              <Quantity item={item} />
              {item.bag && <span className="text-text-faint">{item.bag}</span>}
              {item.notes && <span className="truncate text-text-faint">{item.notes}</span>}
            </span>
          </span>
        </button>

        {item.needs_double_check && (
          <button
            type="button"
            onClick={() => onToggleDoubleCheck(item)}
            aria-label={
              outstanding
                ? `${item.name}: still needs a double check`
                : `${item.name}: double checked`
            }
            className={`px-3 text-sm ${
              outstanding ? 'text-warning' : 'text-success'
            }`}
          >
            {outstanding ? '! check' : '✓ checked'}
          </button>
        )}

        <button
          type="button"
          onClick={() => onEdit(item)}
          aria-label={`Edit ${item.name}`}
          className="px-3 text-text-faint"
        >
          ⋯
        </button>
      </div>
    </li>
  )
}

export { NEXT_STATUS, STATUS_LABEL }
