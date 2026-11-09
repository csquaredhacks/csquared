const text = (name, title, type = "string") => ({
  name,
  title,
  type,
  validation: (rule) => rule.required(),
});

export default {
  name: "hallwayWelcome",
  title: "Hallway welcome page",
  type: "document",
  fields: [
    {
      name: "hero",
      title: "Hero",
      type: "object",
      validation: (rule) => rule.required(),
      fields: [
        text("eyebrow", "Intro label"),
        text("title", "Title"),
        text("description", "Description", "text"),
        text("primaryLabel", "Join button label"),
        text("secondaryLabel", "Story link label"),
      ],
    },
    {
      name: "chapters",
      title: "Chapters",
      type: "array",
      validation: (rule) => rule.required().length(3).custom((chapters) =>
        !chapters || chapters.map(({ id }) => id).join(",") === "before,during,after"
          ? true
          : "Use one chapter for each stage in this order: Before, During, After.",
      ),
      of: [{
        name: "chapter",
        title: "Chapter",
        type: "object",
        fields: [
          {
            ...text("id", "Stage"),
            options: {
              list: [
                { title: "Before", value: "before" },
                { title: "During", value: "during" },
                { title: "After", value: "after" },
              ],
            },
          },
          text("title", "Title"),
          text("description", "Description", "text"),
        ],
      }],
    },
    {
      name: "closing",
      title: "Closing",
      type: "object",
      validation: (rule) => rule.required(),
      fields: [
        text("title", "Title"),
        text("description", "Description", "text"),
        text("actionLabel", "Join button label"),
      ],
    },
  ],
  preview: {
    select: { title: "hero.title" },
  },
};
