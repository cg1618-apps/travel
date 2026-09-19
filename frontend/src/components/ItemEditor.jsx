/**
 * Everything about an item that the one-thumb row deliberately does not show.
 *
 * The row is for working down a list at speed; this is for the once-per-item
 * business of saying how many, which bag, and when it needs doing. Both exist
 * because doing either job with the other's interface is miserable.
 */

import { useState } from 'react'

import { TIMINGS, TIMING_LABELS } from '../lib/timing'

function Field({ label, children }) {
  return (
    <label className="block text-xs text-text-faint">
      {label}
      {children}
    </label>
  )
}

const inputClass =
  'mt-1 block w-full rounded-md border border-border bg-canvas px-3 py-2 text-base text-text'

export function ItemEditor({ item, categories, bags, onSave, onDelete, onClose }) {
  const [draft, setDraft] = useState({
    name: item.name,
    quantity: item.quantity ?? '',
    unit: item.unit ?? '',
    category: item.category ?? '',
    bag: item.bag ?? '',
    timing: item.timing,
    needs_double_check: item.needs_double_check,
    notes: item.notes ?? '',
  })

  const set = (field) => (event) => setDraft({ ...draft, [field]: event.target.value })

  const submit = (event) => {
    event.preventDefault()
    onSave({
      ...draft,
      // Empty means "not set", which is null rather than an empty string. The
      // API distinguishes clearing a field from leaving it alone, so sending
      // "" would store a blank category that autocomplete then remembers.
      quantity: draft.quantity === '' ? null : Number(draft.quantity),
      unit: draft.unit.trim() || null,
      category: draft.category.trim() || null,
      bag: draft.bag.trim() || null,
      notes: draft.notes.trim() || null,
    })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={'Edit ' + item.name}
    >
      <form
        onSubmit={submit}
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl"
      >
        <Field label="Name">
          <input value={draft.name} onChange={set('name')} className={inputClass} />
        </Field>

        <div className="mt-3 flex gap-3">
          <Field label="How many">
            <input
              type="number"
              min="0"
              inputMode="numeric"
              value={draft.quantity}
              onChange={set('quantity')}
              className={inputClass}
            />
          </Field>
          <Field label="Unit">
            <input
              value={draft.unit}
              onChange={set('unit')}
              placeholder="pairs"
              className={inputClass}
            />
          </Field>
        </div>

        {/* Free text with suggestions, never a closed list: an item may always
            carry a value that is not among the options. */}
        <div className="mt-3 flex gap-3">
          <Field label="Category">
            <input
              value={draft.category}
              onChange={set('category')}
              list="category-options"
              className={inputClass}
            />
          </Field>
          <Field label="Bag">
            <input
              value={draft.bag}
              onChange={set('bag')}
              list="bag-options"
              className={inputClass}
            />
          </Field>
        </div>
        <datalist id="category-options">
          {categories.map((option) => (
            <option key={option.id} value={option.value} />
          ))}
        </datalist>
        <datalist id="bag-options">
          {bags.map((option) => (
            <option key={option.id} value={option.value} />
          ))}
        </datalist>

        <Field label="When">
          <select value={draft.timing} onChange={set('timing')} className={inputClass}>
            {TIMINGS.map((timing) => (
              <option key={timing} value={timing}>
                {TIMING_LABELS[timing]}
              </option>
            ))}
          </select>
        </Field>

        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={draft.needs_double_check}
            onChange={(event) =>
              setDraft({ ...draft, needs_double_check: event.target.checked })
            }
            className="size-5"
          />
          Needs a double check
        </label>

        <Field label="Notes">
          <textarea
            value={draft.notes}
            onChange={set('notes')}
            rows={2}
            className={inputClass}
          />
        </Field>

        <div className="mt-5 flex flex-col gap-2">
          <button
            type="submit"
            className="rounded-md bg-brand px-4 font-medium text-on-brand"
          >
            Save
          </button>
          <button type="button" onClick={onClose} className="px-4 text-text-muted">
            Cancel
          </button>
          <button type="button" onClick={() => onDelete(item)} className="px-4 text-danger">
            Remove from list
          </button>
        </div>
      </form>
    </div>
  )
}
