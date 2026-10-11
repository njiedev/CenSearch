import { useEffect, useState } from 'react'

// Real headlines about covert filming, shown as clippings over the photo grid.
// Not mounted for now; add <Headlines /> after <PhotoGrid /> in App to bring
// it back.
// Kickers and bylines are only what the source screenshots showed.
type Article = {
  style: 'cbs' | 'business' | 'feature'
  kicker?: string
  headline: string
  byline?: string
  dateline?: string
}

const ARTICLES: Article[] = [
  {
    style: 'cbs',
    kicker: 'CBS Mornings',
    headline:
      'Woman covertly filmed by Meta AI smart glasses raises privacy and consent concerns: "I had no say"',
    byline: 'By Anna Schecter, Michael Sugerman, Isabel Tabs',
    dateline: 'Updated on: August 21, 2026 / 3:15 PM EDT / CBS News',
  },
  {
    style: 'business',
    kicker: 'Business',
    headline: 'Meta glasses captured and shared intimate images without users’ consent, lawsuit claims',
  },
  {
    style: 'feature',
    headline: '‘I was secretly filmed with smart glasses and then trolled online’',
  },
]

// Spots above and below the wordmark, as percentages of the viewport.
const SLOTS = [
  { top: '13%', left: '3%' },
  { top: '15%', right: '4%' },
  { top: '11%', left: '36%' },
  { bottom: '9%', left: '5%' },
  { bottom: '12%', right: '3%' },
  { bottom: '7%', left: '38%' },
]

const SHOW_MS = 7000
const LEAVE_MS = 500
const EVERY_MS = 3500
const MAX_VISIBLE = 2

type Clip = {
  id: number
  article: number
  slot: number
  leaving: boolean
}

function pickFree(count: number, taken: number[]) {
  const all = Array.from({ length: count }, (_, i) => i)
  const free = all.filter((i) => !taken.includes(i))
  const pool = free.length > 0 ? free : all
  return pool[Math.floor(Math.random() * pool.length)]
}

export default function Headlines() {
  const [clips, setClips] = useState<Clip[]>([])
  const [heroVisible, setHeroVisible] = useState(true)

  // Fade the clippings out once the hero scrolls away, so they don't smear
  // white through the blurred sections below it.
  useEffect(() => {
    const hero = document.getElementById('top')
    if (!hero) {
      return
    }
    const observer = new IntersectionObserver(([entry]) => setHeroVisible(entry.isIntersecting), {
      threshold: 0.4,
    })
    observer.observe(hero)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    let current: Clip[] = []
    let nextId = 0
    const timers = new Set<number>()
    const later = (fn: () => void, ms: number) => {
      const id = window.setTimeout(() => {
        timers.delete(id)
        fn()
      }, ms)
      timers.add(id)
    }
    const commit = (next: Clip[]) => {
      current = next
      setClips(next)
    }

    function spawn() {
      if (current.filter((clip) => !clip.leaving).length >= MAX_VISIBLE) {
        return
      }
      const id = nextId++
      commit([
        ...current,
        {
          id,
          article: pickFree(ARTICLES.length, current.map((clip) => clip.article)),
          slot: pickFree(SLOTS.length, current.map((clip) => clip.slot)),
          leaving: false,
        },
      ])
      later(() => {
        commit(current.map((clip) => (clip.id === id ? { ...clip, leaving: true } : clip)))
        later(() => commit(current.filter((clip) => clip.id !== id)), LEAVE_MS)
      }, SHOW_MS)
    }

    later(spawn, 1500)
    const interval = window.setInterval(spawn, EVERY_MS)
    return () => {
      window.clearInterval(interval)
      for (const id of timers) {
        window.clearTimeout(id)
      }
    }
  }, [])

  return (
    <div className={`headlines${heroVisible ? '' : ' hidden'}`} aria-hidden="true">
      {clips.map((clip) => {
        const article = ARTICLES[clip.article]
        return (
          <article
            key={clip.id}
            className={`clipping clipping-${article.style}${clip.leaving ? ' leaving' : ''}`}
            style={SLOTS[clip.slot]}
          >
            {article.kicker && <p className="clipping-kicker">{article.kicker}</p>}
            <h3 className="clipping-headline">{article.headline}</h3>
            {article.byline && <p className="clipping-meta">{article.byline}</p>}
            {article.dateline && <p className="clipping-meta">{article.dateline}</p>}
          </article>
        )
      })}
    </div>
  )
}
