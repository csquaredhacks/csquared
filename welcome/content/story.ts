import { createClient } from "@sanity/client";

const chapterIds = ["before", "during", "after"] as const;
type ChapterId = typeof chapterIds[number];

type Chapter = {
  id: ChapterId;
  title: string;
  description: string;
};

export type Story = {
  hero: {
    eyebrow: string;
    title: string;
    description: string;
    primaryLabel: string;
    secondaryLabel: string;
  };
  chapters: Chapter[];
  closing: {
    title: string;
    description: string;
    actionLabel: string;
  };
};

export const defaultStory: Story = {
  hero: {
    eyebrow: "A warmer way to walk in",
    title: "Find your people before the conference.",
    description: "Tell Hallway what you need and what you can offer. Meet people with something in common and make a plan to arrive together.",
    primaryLabel: "Join Hallway",
    secondaryLabel: "See how it works",
  },
  chapters: [
    {
      id: "before",
      title: "Walk in with a plan.",
      description: "Share what you need and what you can offer. Find people to meet and agree on a place and time to arrive together.",
    },
    {
      id: "during",
      title: "Make the introduction.",
      description: "Share your Hallway code when you meet someone. Choose whether your connections appear on the public graph.",
    },
    {
      id: "after",
      title: "Keep the conversation going.",
      description: "Use your recap to remember who you met, revisit your goals, and decide who to follow up with.",
    },
  ],
  closing: {
    title: "Make your first plan.",
    description: "Create a Hallway profile without a password. Use your recovery code if you come back on another device.",
    actionLabel: "Join Hallway",
  },
};

const storyQuery = `*[_type == "hallwayWelcome"] | order(_updatedAt desc)[0] {
  hero { eyebrow, title, description, primaryLabel, secondaryLabel },
  chapters[] { id, title, description },
  closing { title, description, actionLabel }
}`;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasTextFields(value: unknown, fields: string[]): boolean {
  return isRecord(value) && fields.every((field) => {
    const text = value[field];
    return typeof text === "string" && text.trim().length > 0;
  });
}

function isStory(value: unknown): value is Story {
  if (!isRecord(value) || !Array.isArray(value.chapters)) return false;

  return hasTextFields(value.hero, ["eyebrow", "title", "description", "primaryLabel", "secondaryLabel"])
    && hasTextFields(value.closing, ["title", "description", "actionLabel"])
    && value.chapters.length === chapterIds.length
    && value.chapters.every((chapter, index) =>
      isRecord(chapter) && chapter.id === chapterIds[index] && hasTextFields(chapter, ["title", "description"]),
    );
}

export async function loadStory(projectId?: string, dataset?: string): Promise<Story> {
  if (!projectId || !dataset) return defaultStory;

  try {
    const client = createClient({
      projectId,
      dataset,
      apiVersion: "2025-02-19",
      perspective: "published",
      useCdn: true,
    });
    const story = await client.fetch<unknown>(storyQuery, {}, { signal: AbortSignal.timeout(2500) });
    return isStory(story) ? story : defaultStory;
  } catch {
    return defaultStory;
  }
}
