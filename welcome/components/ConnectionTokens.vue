<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const field = ref<HTMLDivElement>()
const canvas = ref<HTMLCanvasElement>()
const width = 560
const height = 420

const tokens = [
  { x: 354, y: 160, radius: 109, angle: 0.35, light: '#e0f5d6', mid: '#a1d49f', edge: '#5b976a', ink: '#225b44' },
  { x: 221, y: 242, radius: 125, angle: -0.36, light: '#fffdf0', mid: '#e0e8c1', edge: '#91a270', ink: '#34674c' },
]
type Token = (typeof tokens)[number]

const accents = [
  { ...tokens[1]!, x: 100, y: 303, radius: 28, angle: -0.31 },
  { ...tokens[0]!, x: 466, y: 236, radius: 36, angle: 0.24 },
]

let cleanup: (() => void) | undefined
let disposed = false

function drawToken(ctx: CanvasRenderingContext2D, token: Token, x: number, y: number, angle: number) {
  const { radius: r } = token
  const ry = r * 0.64
  const depth = r * 0.15
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)

  const side = ctx.createLinearGradient(-r, 0, r, 0)
  side.addColorStop(0, token.mid)
  side.addColorStop(0.5, token.edge)
  side.addColorStop(1, token.ink)
  ctx.fillStyle = side
  for (let layer = depth; layer > 0; layer -= 1) {
    ctx.beginPath()
    ctx.ellipse(0, layer, r, ry, 0, 0, Math.PI * 2)
    ctx.fill()
  }

  const face = ctx.createLinearGradient(-r * 0.45, -ry, r * 0.5, ry)
  face.addColorStop(0, token.light)
  face.addColorStop(0.56, token.light)
  face.addColorStop(1, token.mid)
  ctx.beginPath()
  ctx.ellipse(0, 0, r, ry, 0, 0, Math.PI * 2)
  ctx.fillStyle = face
  ctx.fill()

  ctx.beginPath()
  ctx.ellipse(0, 0, r * 0.91, ry * 0.86, 0, 0, Math.PI * 2)
  ctx.strokeStyle = token.edge
  ctx.globalAlpha = 0.65
  ctx.lineWidth = Math.max(1, r * 0.012)
  ctx.stroke()
  ctx.globalAlpha = 1

  // Two people on one line, drawn from Hallway's connection motif.
  ctx.save()
  ctx.scale(1, 0.64)
  ctx.strokeStyle = token.ink
  ctx.lineWidth = r * 0.075
  ctx.beginPath()
  ctx.moveTo(-r * 0.33, r * 0.14)
  ctx.lineTo(r * 0.33, -r * 0.14)
  ctx.stroke()
  ctx.fillStyle = token.ink
  for (const sign of [-1, 1]) {
    ctx.beginPath()
    ctx.arc(sign * r * 0.33, -sign * r * 0.14, r * 0.17, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()

  ctx.beginPath()
  ctx.ellipse(0, 0, r * 0.985, ry * 0.985, 0, Math.PI * 1.02, Math.PI * 1.66)
  ctx.strokeStyle = '#fffef2'
  ctx.globalAlpha = 0.84
  ctx.lineWidth = Math.max(1, r * 0.023)
  ctx.lineCap = 'round'
  ctx.stroke()
  ctx.restore()
}

onMounted(async () => {
  const surface = field.value
  const output = canvas.value
  const ctx = output?.getContext('2d')
  if (!surface || !output || !ctx) return

  let scale = 1
  let left = 0
  let top = 0
  let pixelRatio = 1
  const positions = tokens.map(token => ({ x: token.x, y: token.y, angle: token.angle }))

  function draw() {
    ctx!.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
    ctx!.clearRect(0, 0, output!.width / pixelRatio, output!.height / pixelRatio)
    ctx!.translate(left, top)
    ctx!.scale(scale, scale)

    ctx!.save()
    ctx!.translate(width / 2, 323)
    ctx!.scale(1, 0.19)
    const shade = ctx!.createRadialGradient(0, 0, 20, 0, 0, 205)
    shade.addColorStop(0, '#0d342c88')
    shade.addColorStop(1, '#0d342c00')
    ctx!.fillStyle = shade
    ctx!.fillRect(-205, -205, 410, 410)
    ctx!.restore()

    for (const token of accents) drawToken(ctx!, token, token.x, token.y, token.angle)
    tokens.forEach((token, index) => {
      const position = positions[index]!
      drawToken(ctx!, token, position.x, position.y, position.angle)
    })
  }

  function resize() {
    const box = surface!.getBoundingClientRect()
    pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
    output!.width = Math.max(1, Math.round(box.width * pixelRatio))
    output!.height = Math.max(1, Math.round(box.height * pixelRatio))
    scale = Math.min(box.width / width, box.height / height)
    left = (box.width - width * scale) / 2
    top = (box.height - height * scale) / 2
    draw()
  }

  const observer = new ResizeObserver(resize)
  observer.observe(surface)
  resize()
  cleanup = () => observer.disconnect()

  let Matter: typeof import('matter-js')
  try {
    ({ default: Matter } = await import('matter-js'))
  } catch {
    // The still composition remains visible if the optional motion chunk cannot load.
    return
  }
  if (disposed) return

  const media = window.matchMedia('(prefers-reduced-motion: reduce)')
  const engine = Matter.Engine.create({ gravity: { scale: 0, x: 0, y: 0 } })
  const bodies = tokens.map(token => Matter.Bodies.circle(token.x, token.y, token.radius * 0.58, {
    angle: token.angle,
    frictionAir: 0.13,
    collisionFilter: { group: -1 },
  }))
  Matter.Composite.add(engine.world, bodies)

  let pointer: { x: number, y: number } | undefined
  let frame: number | undefined
  let previousTime = 0
  let settleUntil = 0

  function animate(time: number) {
    frame = undefined
    if (media.matches) return
    bodies.forEach((body, index) => {
      const rest = tokens[index]!
      let x = rest.x
      let y = rest.y
      let angle = rest.angle
      if (pointer) {
        const dx = body.position.x - pointer.x
        const dy = body.position.y - pointer.y
        const distance = Math.hypot(dx, dy)
        const pressure = Math.max(0, 1 - distance / 176)
        x += pressure * dx * 0.21
        y += pressure * dy * 0.21
        angle += pressure * dx * 0.0018
      }
      Matter.Body.applyForce(body, body.position, {
        x: (x - body.position.x) * body.mass * 0.00013,
        y: (y - body.position.y) * body.mass * 0.00013,
      })
      Matter.Body.setAngularVelocity(body, body.angularVelocity * 0.82 + (angle - body.angle) * 0.075)
    })
    Matter.Engine.update(engine, Math.min(1000 / 60, time - previousTime || 1000 / 60))
    previousTime = time
    bodies.forEach((body, index) => {
      Object.assign(positions[index]!, body.position, { angle: body.angle })
    })
    draw()
    if (pointer || time < settleUntil) frame = requestAnimationFrame(animate)
  }

  function onPointer(event: PointerEvent) {
    if (media.matches || event.pointerType === 'touch' || scale <= 0) return
    const box = surface!.getBoundingClientRect()
    pointer = { x: (event.clientX - box.left - left) / scale, y: (event.clientY - box.top - top) / scale }
    if (frame === undefined) frame = requestAnimationFrame(animate)
  }

  function onLeave() {
    pointer = undefined
    settleUntil = performance.now() + 700
  }

  function onMotionChange() {
    if (!media.matches) return
    onLeave()
    if (frame !== undefined) cancelAnimationFrame(frame)
    frame = undefined
    bodies.forEach((body, index) => {
      const rest = tokens[index]!
      Matter.Body.setPosition(body, rest)
      Matter.Body.setAngle(body, rest.angle)
      Matter.Body.setVelocity(body, { x: 0, y: 0 })
      Matter.Body.setAngularVelocity(body, 0)
      Object.assign(positions[index]!, { x: rest.x, y: rest.y, angle: rest.angle })
    })
    draw()
  }

  surface.addEventListener('pointermove', onPointer, { passive: true })
  surface.addEventListener('pointerleave', onLeave)
  media.addEventListener('change', onMotionChange)
  cleanup = () => {
    observer.disconnect()
    if (frame !== undefined) cancelAnimationFrame(frame)
    surface.removeEventListener('pointermove', onPointer)
    surface.removeEventListener('pointerleave', onLeave)
    media.removeEventListener('change', onMotionChange)
    Matter.Composite.clear(engine.world, false)
    Matter.Engine.clear(engine)
  }
})

onUnmounted(() => {
  disposed = true
  cleanup?.()
})
</script>

<template>
  <div ref="field" class="connection-tokens" aria-hidden="true">
    <canvas ref="canvas" />
  </div>
</template>

<style scoped>
.connection-tokens {
  position: relative;
  width: 100%;
  min-width: 0;
  aspect-ratio: 4 / 3;
}

canvas {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
