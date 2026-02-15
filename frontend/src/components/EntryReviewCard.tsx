import type { EntryReviewData, LoreReference } from '../types'

interface EntryReviewCardProps {
  review: EntryReviewData
  onApprove: () => void
  onEdit: () => void
  onReject: () => void
}

function ReferenceList({ references }: { references: LoreReference[] }) {
  if (references.length === 0) {
    return <p className="text-xs text-gray-400">No suggested references.</p>
  }

  return (
    <ul className="space-y-1 text-xs text-gray-200">
      {references.map((reference, index) => (
        <li key={`${reference.target_slug}-${index}`} className="rounded border border-gray-700 bg-gray-950 px-2 py-1">
          <span className="font-medium">{reference.target_slug}</span>
          <span className="text-gray-400"> ({reference.target_type})</span>
          {reference.relationship ? <span className="text-gray-300"> - {reference.relationship}</span> : null}
        </li>
      ))}
    </ul>
  )
}

function EntryReviewCard({ review, onApprove, onEdit, onReject }: EntryReviewCardProps) {
  return (
    <div className="rounded-lg border border-emerald-700/60 bg-emerald-950/20 p-3 text-gray-100">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-300">Entry Review</p>

      <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div>
          <span className="text-gray-400">Name:</span> {review.name}
        </div>
        <div>
          <span className="text-gray-400">Type:</span> {review.type}
        </div>
        <div>
          <span className="text-gray-400">Category:</span> {review.category}
        </div>
        <div>
          <span className="text-gray-400">Status:</span> {review.status}
        </div>
      </div>

      <p className="mt-3 rounded border border-gray-700 bg-gray-950 px-2 py-2 text-sm text-gray-200">{review.summary}</p>

      <div className="mt-3">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Fields</p>
        <pre className="overflow-x-auto rounded border border-gray-700 bg-gray-950 p-2 text-xs text-gray-200">
          {JSON.stringify(review.fields, null, 2)}
        </pre>
      </div>

      <div className="mt-3">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">References</p>
        <ReferenceList references={review.references} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onApprove}
          className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={onEdit}
          className="rounded border border-yellow-600 px-3 py-1.5 text-xs font-semibold text-yellow-200 hover:bg-yellow-950"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={onReject}
          className="rounded border border-red-700 px-3 py-1.5 text-xs font-semibold text-red-200 hover:bg-red-950"
        >
          Reject
        </button>
      </div>
    </div>
  )
}

export default EntryReviewCard
