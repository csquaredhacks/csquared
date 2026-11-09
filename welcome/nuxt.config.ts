export default defineNuxtConfig({
  compatibilityDate: '2025-03-20',
  devtools: { enabled: false },
  app: {
    baseURL: '/welcome/',
    head: {
      title: 'Hallway | Find your people',
      meta: [{ name: 'description', content: 'Find people to meet and a group to arrive with before the conference.' }],
    },
  },
  css: ['~/assets/welcome.css'],
  nitro: { prerender: { crawlLinks: false, routes: ['/'] } },
  runtimeConfig: {
    public: {
      hallwayUrl: '/',
      sanityProjectId: '',
      sanityDataset: '',
    },
  },
});
