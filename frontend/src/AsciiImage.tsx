import { useEffect, useRef } from 'react'

const RAMP = ' .:-=+*#%@'
const FRAME_MS = 1000 / 12

type Props = {
  src: string
  kind?: 'image' | 'video'
  focusX?: number
  focusY?: number
  zoom?: number
}

// Both sources use the same small sampling canvas. Only video needs a loop.
export default function AsciiImage({ src, kind = 'image', focusX = 0.5, focusY = 0.5, zoom = 1 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current!
    const context = canvas.getContext('2d')
    const sample = document.createElement('canvas')
    const pixels = sample.getContext('2d', { willReadFrequently: true })
    if (!context || !pixels) {
      return
    }

    const video = kind === 'video' ? document.createElement('video') : null
    const source = video ?? new Image()
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let disposed = false
    let ready = false
    let onScreen = false
    let frame = 0
    let resizeTimer = 0
    let lastFrame = 0

    function draw() {
      if (!ready || disposed || !context || !pixels) {
        return
      }
      const width = canvas.clientWidth
      const height = canvas.clientHeight
      if (!width || !height) {
        return
      }
      const dpr = window.devicePixelRatio || 1
      const pixelWidth = Math.round(width * dpr)
      const pixelHeight = Math.round(height * dpr)
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth
        canvas.height = pixelHeight
      }
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
      context.fillStyle = '#000'
      context.fillRect(0, 0, width, height)

      const cellWidth = width < 600 ? 2 : 3
      const cellHeight = cellWidth * 2
      const columns = Math.ceil(width / cellWidth)
      const rows = Math.ceil(height / cellHeight)
      sample.width = columns
      sample.height = rows
      const sourceWidth = video ? video.videoWidth : (source as HTMLImageElement).naturalWidth
      const sourceHeight = video ? video.videoHeight : (source as HTMLImageElement).naturalHeight
      if (!sourceWidth || !sourceHeight) {
        return
      }
      // Cover the band without stretching the image or its future video source.
      const scale = Math.max(width / sourceWidth, height / sourceHeight) * Math.max(1, zoom)
      const cropWidth = width / scale
      const cropHeight = height / scale
      pixels.drawImage(source, (sourceWidth - cropWidth) * Math.max(0, Math.min(1, focusX)),
        (sourceHeight - cropHeight) * Math.max(0, Math.min(1, focusY)),
        cropWidth, cropHeight, 0, 0, columns, rows)
      const data = pixels.getImageData(0, 0, columns, rows).data
      context.font = `${cellHeight}px "Geist Mono", monospace`
      context.textBaseline = 'top'
      const buckets: { character: string; x: number; y: number }[][] = Array.from({ length: 8 }, () => [])
      for (let row = 0; row < rows; row++) {
        for (let column = 0; column < columns; column++) {
          const offset = (row * columns + column) * 4
          const luminance = (data[offset] * 0.2126 + data[offset + 1] * 0.7152 + data[offset + 2] * 0.0722) / 255
          const contrast = Math.max(0, Math.min(1, (luminance - 0.08) * 1.15))
          const character = RAMP[Math.round(contrast * (RAMP.length - 1))]
          if (character !== ' ') {
            const bucket = Math.round(contrast * (buckets.length - 1))
            buckets[bucket].push({ character, x: column * cellWidth, y: row * cellHeight })
          }
        }
      }
      // At most eight paint changes per frame, rather than one per glyph.
      buckets.forEach((glyphs, level) => {
        context.fillStyle = `rgba(160, 160, 168, ${0.08 + (level / (buckets.length - 1)) * 0.62})`
        for (const { character, x, y } of glyphs) {
          context.fillText(character, x, y)
        }
      })
    }

    function tick(now: number) {
      if (now - lastFrame >= FRAME_MS) {
        draw()
        lastFrame = now
      }
      frame = requestAnimationFrame(tick)
    }

    function syncPlayback() {
      if (!video || disposed) {
        return
      }
      cancelAnimationFrame(frame)
      if (ready && onScreen && !document.hidden && !motion.matches) {
        void video.play().catch(() => {
          // If autoplay is unavailable, the loaded frame remains visible.
        })
        frame = requestAnimationFrame(tick)
      } else {
        video.pause()
      }
    }

    function onReady() {
      if (disposed) {
        return
      }
      ready = true
      draw()
      syncPlayback()
    }

    function onResize() {
      window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(draw, 150)
    }

    const observer = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting
      syncPlayback()
    })
    observer.observe(canvas)
    const resize = new ResizeObserver(onResize)
    resize.observe(canvas)
    window.addEventListener('resize', onResize)
    motion.addEventListener('change', syncPlayback)
    document.addEventListener('visibilitychange', syncPlayback)
    const readyEvent = video ? 'loadeddata' : 'load'
    source.addEventListener(readyEvent, onReady)
    if (video) {
      video.muted = true
      video.loop = true
      video.playsInline = true
      video.preload = 'auto'
    }
    source.src = src
    void document.fonts.load('8px "Geist Mono"').then(() => {
      if (!disposed) {
        draw()
      }
    })

    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      window.clearTimeout(resizeTimer)
      observer.disconnect()
      resize.disconnect()
      window.removeEventListener('resize', onResize)
      motion.removeEventListener('change', syncPlayback)
      document.removeEventListener('visibilitychange', syncPlayback)
      source.removeEventListener(readyEvent, onReady)
      if (video) {
        video.pause()
        video.removeAttribute('src')
        video.load()
      }
    }
  }, [src, kind, focusX, focusY, zoom])

  return <canvas ref={canvasRef} className="ascii-art" aria-hidden="true" />
}
