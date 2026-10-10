// Particle disintegration for grid photos. Every dissolving photo is drawn on
// one shared full-screen canvas, so the grid itself stays plain DOM.

const BLOCK = 4 // CSS pixels of photo covered by one particle
const SWEEP_MS = 700 // time for the dissolve to cross the photo, left to right
const MAX_DPR = 2

type Particle = {
  x: number
  y: number
  shade: string
  delay: number
  life: number
  vx: number
  vy: number
  phase: number
}

type Job = {
  particles: Particle[]
  startedAt: number | null
  length: number
  onStart: () => void
  resolve: () => void
}

export class DustLayer {
  private readonly canvas: HTMLCanvasElement
  private readonly ctx: CanvasRenderingContext2D
  private readonly sampler = document.createElement('canvas')
  private readonly dim: number
  private jobs: Job[] = []
  private frame = 0

  constructor(canvas: HTMLCanvasElement, dim: number) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')!
    this.dim = dim
    this.resize()
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR)
    this.canvas.width = Math.round(window.innerWidth * dpr)
    this.canvas.height = Math.round(window.innerHeight * dpr)
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  // Turns the photo into particles and blows them away. `onStart` runs on the
  // frame the particles first appear, so the caller can hide the real image
  // without a gap. Resolves when the last particle has faded.
  disintegrate(img: HTMLImageElement, onStart: () => void): Promise<void> {
    const rect = img.getBoundingClientRect()
    const particles = this.sample(img, rect)
    if (particles.length === 0) {
      onStart()
      return Promise.resolve()
    }
    let length = 0
    for (const p of particles) {
      length = Math.max(length, p.delay + p.life)
    }
    return new Promise((resolve) => {
      this.jobs.push({ particles, startedAt: null, length, onStart, resolve })
      if (this.frame === 0) {
        this.frame = requestAnimationFrame(this.tick)
      }
    })
  }

  // Drops every running dissolve. Their promises resolve so callers unwind.
  clear() {
    cancelAnimationFrame(this.frame)
    this.frame = 0
    for (const job of this.jobs) {
      job.resolve()
    }
    this.jobs = []
    this.ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
  }

  private sample(img: HTMLImageElement, rect: DOMRect): Particle[] {
    if (!img.complete || img.naturalWidth === 0) {
      return []
    }
    const cols = Math.max(1, Math.round(rect.width / BLOCK))
    const rows = Math.max(1, Math.round(rect.height / BLOCK))
    this.sampler.width = cols
    this.sampler.height = rows
    const sctx = this.sampler.getContext('2d', { willReadFrequently: true })!
    sctx.drawImage(img, 0, 0, cols, rows)
    const pixels = sctx.getImageData(0, 0, cols, rows).data

    const stepX = rect.width / cols
    const stepY = rect.height / rows
    const particles: Particle[] = []
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const i = (row * cols + col) * 4
        // Same luminance weights and dimming as the CSS filter on the photos.
        const luminance = 0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2]
        const grey = Math.round(luminance * this.dim)
        particles.push({
          x: rect.left + col * stepX,
          y: rect.top + row * stepY,
          shade: `rgb(${grey},${grey},${grey})`,
          delay: (col / cols) * SWEEP_MS + Math.random() * 300,
          life: 700 + Math.random() * 600,
          vx: 0.02 + Math.random() * 0.07,
          vy: -0.01 - Math.random() * 0.05,
          phase: Math.random() * Math.PI * 2,
        })
      }
    }
    return particles
  }

  private tick = (now: number) => {
    const ctx = this.ctx
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)

    const running: Job[] = []
    for (const job of this.jobs) {
      if (job.startedAt === null) {
        job.startedAt = now
        job.onStart()
      }
      const elapsed = now - job.startedAt
      if (elapsed >= job.length) {
        job.resolve()
        continue
      }
      this.draw(job, elapsed)
      running.push(job)
    }
    ctx.globalAlpha = 1

    this.jobs = running
    this.frame = running.length > 0 ? requestAnimationFrame(this.tick) : 0
  }

  private draw(job: Job, elapsed: number) {
    const ctx = this.ctx
    for (const p of job.particles) {
      const local = elapsed - p.delay
      if (local <= 0) {
        // Not reached by the sweep yet: sit still and stand in for the photo.
        ctx.globalAlpha = 1
        ctx.fillStyle = p.shade
        ctx.fillRect(p.x, p.y, BLOCK + 0.5, BLOCK + 0.5)
        continue
      }
      const progress = local / p.life
      if (progress >= 1) {
        continue
      }
      const size = BLOCK * (1 - 0.6 * progress)
      const wobble = Math.sin(local * 0.006 + p.phase) * 6 * progress
      ctx.globalAlpha = (1 - progress) ** 1.5
      ctx.fillStyle = p.shade
      ctx.fillRect(p.x + p.vx * local + wobble, p.y + p.vy * local, size, size)
    }
  }
}
