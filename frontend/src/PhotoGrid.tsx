import { useEffect, useRef } from 'react'
import { DustLayer } from './dust'

const PHOTO_COUNT = 160 // files in public/photos, named 01.jpg … 160.jpg
const CELL_TARGET = 130 // preferred cell edge in CSS pixels
const DIM = 0.45 // photo brightness; shared with CSS through --dim
const MAX_BUSY = 8 // cells animating at once
const HIT_MS = 1500 // must match the `hit` keyframes in index.css
const FADE_MS = 400

type Effect = 'dust' | 'match' | 'flag'

type Cell = {
  el: HTMLDivElement
  img: HTMLImageElement
  photo: number
  busy: boolean
}

function photoUrl(photo: number) {
  return `/photos/${String(photo).padStart(2, '0')}.jpg`
}

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function pickEffect(): Effect {
  const roll = Math.random()
  if (roll < 0.5) {
    return 'dust'
  }
  return roll < 0.75 ? 'match' : 'flag'
}

// Builds the grid inside `container` and keeps it animating. Returns a
// function that stops everything and empties the container.
function startGrid(container: HTMLDivElement, dust: DustLayer) {
  let alive = true
  const timers = new Set<number>()

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      const id = window.setTimeout(() => {
        timers.delete(id)
        resolve()
      }, ms)
      timers.add(id)
    })

  const columns = Math.max(4, Math.ceil(window.innerWidth / CELL_TARGET))
  const cellSize = window.innerWidth / columns
  const rows = Math.ceil(window.innerHeight / cellSize)
  container.style.setProperty('--columns', String(columns))
  container.style.setProperty('--dim', String(DIM))

  const cells: Cell[] = []
  for (let i = 0; i < columns * rows; i++) {
    const el = document.createElement('div')
    el.className = 'cell empty'
    const img = document.createElement('img')
    img.alt = ''
    img.draggable = false
    el.append(img)
    container.append(el)
    cells.push({ el, img, photo: 0, busy: false })
  }

  // Prefers a photo nobody is showing; repeats only when the grid has more
  // cells than there are photos.
  function pickPhoto() {
    const shown = new Set(cells.map((cell) => cell.photo))
    const free: number[] = []
    for (let photo = 1; photo <= PHOTO_COUNT; photo++) {
      if (!shown.has(photo)) {
        free.push(photo)
      }
    }
    if (free.length === 0) {
      return 1 + Math.floor(Math.random() * PHOTO_COUNT)
    }
    return free[Math.floor(Math.random() * free.length)]
  }

  async function showNewPhoto(cell: Cell) {
    cell.photo = pickPhoto()
    cell.img.src = photoUrl(cell.photo)
    try {
      await cell.img.decode()
    } catch {
      // A photo that fails to load just leaves the cell dark until its next turn.
    }
    if (!alive) {
      return
    }
    cell.el.classList.remove('snap')
    void cell.el.offsetWidth // commit the hidden state so the fade-in runs
    cell.el.classList.remove('empty')
  }

  async function dissolve(cell: Cell) {
    await dust.disintegrate(cell.img, () => {
      cell.el.classList.add('snap', 'empty')
    })
  }

  async function highlight(cell: Cell, effect: 'match' | 'flag') {
    cell.el.classList.add('hit', effect)
    await sleep(HIT_MS)
    cell.el.classList.add('out')
    await sleep(FADE_MS)
    cell.el.classList.add('snap', 'empty')
    cell.el.classList.remove('hit', effect, 'out')
  }

  async function animate(cell: Cell) {
    cell.busy = true
    const effect = pickEffect()
    if (effect === 'dust') {
      await dissolve(cell)
    } else {
      await highlight(cell, effect)
    }
    await sleep(randomBetween(200, 500))
    if (!alive) {
      return
    }
    await showNewPhoto(cell)
    await sleep(FADE_MS)
    cell.busy = false
  }

  async function run() {
    await sleep(1200)
    while (alive) {
      const idle = cells.filter((cell) => !cell.busy)
      const busyCount = cells.length - idle.length
      if (idle.length > 0 && busyCount < MAX_BUSY) {
        void animate(idle[Math.floor(Math.random() * idle.length)])
      }
      await sleep(randomBetween(250, 700))
    }
  }

  for (const cell of cells) {
    void showNewPhoto(cell)
  }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!reducedMotion) {
    void run()
  }

  return () => {
    alive = false
    for (const id of timers) {
      window.clearTimeout(id)
    }
    dust.clear()
    container.replaceChildren()
  }
}

export default function PhotoGrid() {
  const gridRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const container = gridRef.current!
    const dust = new DustLayer(canvasRef.current!, DIM)
    let stop = startGrid(container, dust)

    let resizeTimer = 0
    function onResize() {
      window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => {
        stop()
        dust.resize()
        stop = startGrid(container, dust)
      }, 200)
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      window.clearTimeout(resizeTimer)
      stop()
    }
  }, [])

  return (
    <div className="backdrop" aria-hidden="true">
      <div className="grid" ref={gridRef} />
      <canvas className="dust" ref={canvasRef} />
      <div className="vignette" />
    </div>
  )
}
