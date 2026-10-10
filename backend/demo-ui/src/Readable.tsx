function label(key: string) {
  const words = key.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/[_-]+/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function Value({ value }: { value: unknown }) {
  if (value == null) return <span>Not answered</span>
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>
  if (Array.isArray(value)) {
    if (!value.length) return <span>No items</span>
    return <ul className="min-w-0 list-disc space-y-2 pl-4">
      {value.map((item, index) => <li key={index}><Value value={item} /></li>)}
    </ul>
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    if (!entries.length) return <span>No fields</span>
    return <dl className="min-w-0 space-y-2">
      {entries.map(([key, item]) => <div key={key}>
        <dt className="inline font-medium">{label(key)}: </dt>
        <dd className={item !== null && typeof item === 'object' ? 'mt-1 border-l pl-3' : 'inline'}>
          <Value value={item} />
        </dd>
      </div>)}
    </dl>
  }
  return <span className="whitespace-pre-wrap">{String(value)}</span>
}

export function Readable({ value }: { value: unknown }) {
  return <div className="min-w-0 space-y-3 text-sm [overflow-wrap:anywhere]">
    <div data-readable-content><Value value={value} /></div>
    <details>
      <summary className="cursor-pointer text-xs">Show raw data</summary>
      <pre className="mt-2">{JSON.stringify(value, null, 2)}</pre>
    </details>
  </div>
}
