<script setup lang="ts">
import { defaultStory, loadStory } from './content/story'

const config = useRuntimeConfig()
const { data: story } = await useAsyncData('hallway-welcome', () =>
  loadStory(config.public.sanityProjectId, config.public.sanityDataset),
  { default: () => defaultStory },
)
const appRoot = config.public.hallwayUrl.replace(/\/+$/, '')
const joinUrl = `${appRoot}/`
const recoverUrl = `${appRoot}/recover`
const root = ref<HTMLElement | null>(null)
const storySection = ref<HTMLElement | null>(null)
const active = ref(0)
const progress = ref(0)
const chapter = computed(() => story.value!.chapters[active.value] ?? defaultStory.chapters[0]!)
const screenText = [
  { label: 'Your profile', title: 'What are you working on?', rows: ['I need a reviewer', 'I can help with Kubernetes'] },
  { label: 'Your arrival plan', title: 'Walk in together', rows: ['Meet at the entrance', 'Agree on a place and time'] },
  { label: 'Your recap', title: 'Keep in touch', rows: ['People you met', 'Goals you want to follow up on'] },
]
const screen = computed(() => screenText[active.value] ?? screenText[0]!)
let stopMotion: (() => void) | undefined
let disposed = false

onMounted(async () => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const [{ default: Lenis }, { gsap }, { ScrollTrigger }] = await Promise.all([
    import('lenis'), import('gsap'), import('gsap/ScrollTrigger'),
  ])
  if (disposed || !root.value || !storySection.value) return
  gsap.registerPlugin(ScrollTrigger)
  const lenis = new Lenis({ smoothWheel: true })
  lenis.on('scroll', ScrollTrigger.update)
  const tick = (time: number) => lenis.raf(time * 1000)
  gsap.ticker.add(tick)
  const context = gsap.context(() => {
    gsap.from('.hero-copy', { y: 22, opacity: 0, duration: 0.65, ease: 'power2.out' })
    gsap.from('.story-screen', {
      y: 35, opacity: 0, duration: 0.55,
      scrollTrigger: { trigger: storySection.value, start: 'top 82%', once: true },
    })
    ScrollTrigger.create({
      trigger: storySection.value,
      start: 'top 82%',
      end: 'bottom 22%',
      onUpdate: (state) => { progress.value = state.progress },
    })
  }, root.value)
  stopMotion = () => {
    context.revert()
    gsap.ticker.remove(tick)
    lenis.destroy()
  }
})

onBeforeUnmount(() => {
  disposed = true
  stopMotion?.()
})
</script>

<template>
  <div ref="root" class="welcome">
    <a class="skip-link" href="#main">Skip to content</a>
    <header class="site-header wrap">
      <a class="wordmark" href="#main" aria-label="Hallway welcome">
        <span class="mark" aria-hidden="true"><i /><i /></span> Hallway
      </a>
      <nav aria-label="Welcome">
        <a class="pill pill-outline" :href="recoverUrl">Recover</a>
        <a class="pill pill-light" :href="joinUrl">Join Hallway</a>
      </nav>
    </header>

    <main id="main">
      <section class="hero wrap" aria-labelledby="hero-title">
        <div class="hero-copy">
          <p class="hero-label">{{ story!.hero.eyebrow }}</p>
          <h1 id="hero-title">{{ story!.hero.title }}</h1>
          <p class="hero-description">{{ story!.hero.description }}</p>
          <div class="hero-actions">
            <a class="pill pill-light" :href="joinUrl">{{ story!.hero.primaryLabel }}</a>
            <a class="pill pill-outline" href="#how">{{ story!.hero.secondaryLabel }}</a>
          </div>
        </div>
        <div class="hero-art">
          <ConnectionTokens />
        </div>
        <a class="scroll-link" href="#how">Scroll to explore <span aria-hidden="true">↓</span></a>
      </section>

      <section id="how" ref="storySection" class="story" aria-labelledby="story-title">
        <div class="wrap story-inner">
          <div class="story-intro">
            <h2 id="story-title">Good conferences start before you arrive.</h2>
            <p>See how a profile turns into a plan, and how to keep those connections after the event.</p>
          </div>
          <div class="story-layout">
            <div class="chapter-list" aria-label="Conference stages">
              <button v-for="(item, index) in story!.chapters" :key="item.id" type="button"
                class="chapter" :aria-pressed="active === index" aria-controls="story-screen"
                @click="active = index">
                <span class="chapter-number" aria-hidden="true">0{{ index + 1 }}</span>
                <span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span>
              </button>
            </div>
            <div id="story-screen" class="story-screen" aria-live="polite" :aria-label="chapter.title">
              <div class="screen-copy">
                <p>{{ screen.label }}</p>
                <h3>{{ screen.title }}</h3>
                <ul><li v-for="row in screen.rows" :key="row">{{ row }}</li></ul>
              </div>
              <div class="screen-art"><ArrivalMorph :progress="progress" /></div>
            </div>
          </div>
        </div>
      </section>

      <section class="closing wrap" aria-labelledby="closing-title">
        <span class="mark closing-mark" aria-hidden="true"><i /><i /></span>
        <h2 id="closing-title">{{ story!.closing.title }}</h2>
        <p>{{ story!.closing.description }}</p>
        <a class="pill pill-light" :href="joinUrl">{{ story!.closing.actionLabel }}</a>
      </section>
    </main>
    <footer class="wrap site-footer">
      <a class="wordmark" href="#main">Hallway</a>
      <a :href="recoverUrl">Use a recovery code</a>
    </footer>
  </div>
</template>
