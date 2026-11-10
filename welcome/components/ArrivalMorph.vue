<script setup lang="ts">
import type { Rive } from '@rive-app/canvas'

const props = withDefaults(defineProps<{ progress?: number }>(), { progress: 0.72 })
const canvas = ref<HTMLCanvasElement | null>(null)
const ready = ref(false)
const base = useRuntimeConfig().app.baseURL
const duration = 2

let animation: Rive | undefined
let observer: ResizeObserver | undefined
let motionPreference: MediaQueryList | undefined
let mounted = false

function showProgress() {
  if (ready.value) {
    animation?.scrub('Gather', Math.min(1, Math.max(0, props.progress)) * duration)
  }
}

async function mountAnimation() {
  if (!mounted || !canvas.value || motionPreference?.matches || animation) return
  try {
    const [{ Fit, Layout, Rive, RuntimeLoader }, { default: wasmUrl }] = await Promise.all([
      import('@rive-app/canvas'),
      import('@rive-app/canvas/rive.wasm?url'),
    ])
    if (!mounted || !canvas.value || motionPreference?.matches || animation) return

    RuntimeLoader.setWasmUrl(wasmUrl)
    animation = new Rive({
      src: `${base.replace(/\/$/, '')}/arrival.riv`,
      canvas: canvas.value,
      animations: 'Gather',
      autoplay: false,
      layout: new Layout({ fit: Fit.Contain }),
      onLoad: () => {
        animation?.resizeDrawingSurfaceToCanvas()
        ready.value = true
        showProgress()
      },
      onLoadError: () => {
        ready.value = false
      },
    })
    observer = new ResizeObserver(() => {
      animation?.resizeDrawingSurfaceToCanvas()
      showProgress()
    })
    observer.observe(canvas.value)
  } catch {
    // The diagram still works as a static SVG if the runtime fails to load.
  }
}

function stopAnimation() {
  ready.value = false
  observer?.disconnect()
  observer = undefined
  animation?.cleanup()
  animation = undefined
}

function syncMotionPreference() {
  if (motionPreference?.matches) stopAnimation()
  else void mountAnimation()
}

watch(() => props.progress, showProgress)

onMounted(() => {
  mounted = true
  motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionPreference.addEventListener('change', syncMotionPreference)
  syncMotionPreference()
})

onBeforeUnmount(() => {
  mounted = false
  motionPreference?.removeEventListener('change', syncMotionPreference)
  stopAnimation()
})
</script>

<template>
  <div class="arrival-morph" aria-hidden="true">
    <svg class="arrival-morph__frame" :class="{ 'arrival-morph__frame--hidden': ready }" viewBox="0 0 620 420" focusable="false">
      <path d="M235 205h150" stroke="#96d69a" stroke-linecap="round" stroke-width="4" />
      <g transform="translate(155 205)">
        <rect x="-119" y="-72" width="238" height="144" rx="24" fill="#e9f7dd" stroke="#b4deaf" stroke-width="2" />
        <circle cx="-75" cy="-21" r="17" fill="#497e55" />
        <rect x="-45.5" y="-30.5" width="69" height="7" rx="3.5" fill="#23482e" />
        <rect x="-46" y="-12.5" width="100" height="5" rx="2.5" fill="#82ae7d" />
        <rect x="-93" y="14.5" width="138" height="31" rx="15" fill="#bfdfb2" />
        <circle cx="-68" cy="30" r="5" fill="#386644" />
        <rect x="-50.5" y="27.5" width="61" height="5" rx="2.5" fill="#497e55" />
      </g>
      <g transform="translate(465 205)">
        <rect x="-119" y="-72" width="238" height="144" rx="24" fill="#2a6348" stroke="#6fa982" stroke-width="2" />
        <circle cx="-75" cy="-21" r="17" fill="#d1edbd" />
        <rect x="-45.5" y="-30.5" width="69" height="7" rx="3.5" fill="#f0f9e6" />
        <rect x="-46" y="-12.5" width="100" height="5" rx="2.5" fill="#90c099" />
        <rect x="-93" y="14.5" width="138" height="31" rx="15" fill="#42815d" />
        <circle cx="-68" cy="30" r="5" fill="#d1edbd" />
        <rect x="-50.5" y="27.5" width="61" height="5" rx="2.5" fill="#d1edbd" />
      </g>
      <circle cx="310" cy="205" r="25.5" fill="#bde79f" stroke="#e7f5d9" stroke-width="2" />
      <path d="M303 205h14" stroke="#23482e" stroke-width="3" />
      <circle cx="303" cy="205" r="4.5" fill="#23482e" />
      <circle cx="317" cy="205" r="4.5" fill="#23482e" />
    </svg>
    <canvas
      ref="canvas"
      class="arrival-morph__canvas"
      :class="{ 'arrival-morph__canvas--visible': ready }"
      width="620"
      height="420"
    />
  </div>
</template>

<style scoped>
.arrival-morph {
  position: relative;
  width: 100%;
  aspect-ratio: 620 / 420;
  pointer-events: none;
}

.arrival-morph__frame,
.arrival-morph__canvas {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
}

.arrival-morph__frame--hidden,
.arrival-morph__canvas {
  visibility: hidden;
}

.arrival-morph__canvas--visible {
  visibility: visible;
}
</style>
