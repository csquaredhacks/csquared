# Hallway welcome

A Nuxt and Vue introduction to Hallway. The Join and Recover links open the
existing Hallway app, where registration and recovery take place.

## Run locally

```sh
cd welcome
npm ci
NUXT_PUBLIC_HALLWAY_URL=http://localhost:5173 npm run dev
```

Open [the welcome page](http://localhost:3000/welcome/). Start the Hallway app
separately to exercise Join or Recover. Use a running Hallway app origin in
`NUXT_PUBLIC_HALLWAY_URL` if you are previewing the welcome page by itself.

Run `npm run build` to generate the static site in `.output/public`. The default
base path is `/welcome/` for serving the page alongside Hallway.

## Publish copy from Sanity

1. Create a Sanity project with a public dataset for the welcome page copy.
2. Import [the welcome document schema](sanity/hallwayWelcome.js) into your
   [Studio schema types](https://www.sanity.io/docs/studio/schema-types).
3. Publish a **Hallway welcome page** document. Fill its hero and closing fields
   and add Before, During, and After chapters in that order. The
   [bundled copy](content/story.ts) is a starting point.
4. Set `NUXT_PUBLIC_SANITY_PROJECT_ID` and `NUXT_PUBLIC_SANITY_DATASET` before
   building. Rebuild after publishing copy for a static deployment.

The site reads published copy through [the Sanity JavaScript client](https://github.com/sanity-io/client).
It uses the bundled copy if Sanity is unconfigured, unavailable, or returns an
incomplete document. The dataset is public, so use it for welcome page copy and
keep attendee and account data in Hallway.

## Deploy the welcome page on Vercel

Import this repository into a Vercel project and set its **Root Directory** to
`welcome`. The [Vercel configuration](vercel.json) selects Nuxt and deploys the
generated static output. Use these environment variables for a separate origin.

| Variable | Value |
| --- | --- |
| `NUXT_APP_BASE_URL` | `/` |
| `NUXT_PUBLIC_HALLWAY_URL` | The existing HTTPS Hallway app origin |
| `NUXT_PUBLIC_SANITY_PROJECT_ID` | Optional public Sanity project ID |
| `NUXT_PUBLIC_SANITY_DATASET` | Optional public Sanity dataset name |

[Nuxt deployment on Vercel](https://vercel.com/docs/frameworks/full-stack/nuxt)
