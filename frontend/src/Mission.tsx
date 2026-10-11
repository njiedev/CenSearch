import { useEffect, useRef, useState } from 'react'
import { ARTICLES } from './articles'

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min)
}

// Each headline gets its own offset inside its slot and its own slow drift
// path, so the space never looks like a tidy grid.
function randomFloat() {
  return {
    '--jx': `${randomBetween(-4, 4)}%`,
    '--jy': `${randomBetween(-4, 4)}px`,
    '--dx1': `${randomBetween(-4, 4)}px`,
    '--dy1': `${randomBetween(-4, 4)}px`,
    '--dx2': `${randomBetween(-4, 4)}px`,
    '--dy2': `${randomBetween(-4, 4)}px`,
    '--drift': `${randomBetween(14, 26)}s`,
    '--phase': `${randomBetween(-26, 0)}s`,
  } as React.CSSProperties
}

// The second screen: real headlines drifting on the left, the mission
// statement on the right. The headlines ease down the first time the section
// scrolls into view.
export default function Mission() {
  const sectionRef = useRef<HTMLElement>(null)
  const [seen, setSeen] = useState(false)
  const [floats] = useState(() => ARTICLES.map(randomFloat))

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true)
          observer.disconnect()
        }
      },
      { threshold: 0.2 },
    )
    observer.observe(sectionRef.current!)
    return () => observer.disconnect()
  }, [])

  return (
    <section className={`mission${seen ? ' in' : ''}`} id="mission" ref={sectionRef} aria-labelledby="mission-title">
      <ul className="wall">
        {ARTICLES.map((article, i) => (
          <li
            key={article.url}
            className={`wall-item${article.size ? ` ${article.size}` : ''}`}
            style={{ '--order': i, ...floats[i] } as React.CSSProperties}
          >
            <a className="wall-link" href={article.url} target="_blank" rel="noreferrer">
              <span className="wall-headline">{article.headline}</span>
              <span className="wall-source">
                {article.outlet} · {article.date}
              </span>
            </a>
          </li>
        ))}
      </ul>
      <div className="mission-copy">
        <h2 className="mission-statement" id="mission-title">
          Anyone can <span className="pixel-word">film</span> you now.
          <br />
          Nobody <span className="pixel-word">asks</span>.
        </h2>
        <p className="mission-sub">We find where your face ended up and get it taken down.</p>
      </div>
    </section>
  )
}
