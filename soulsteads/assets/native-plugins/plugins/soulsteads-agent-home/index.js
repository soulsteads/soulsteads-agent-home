import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const id = "soulsteads-home-status";
const source = new URL(`./skills/${id}/SKILL.md`, import.meta.url);

export default {
  id: "soulsteads.agent-home",
  async setup(ctx) {
    // Read only the public, versioned skill bundled with this plugin.
    const markdown = await readFile(source, "utf8");
    const delimiter = "\n---\n";
    const boundary = markdown.indexOf(delimiter);
    if (!markdown.startsWith("---\n") || boundary === -1) {
      throw new Error("Invalid bundled Soulsteads skill");
    }
    const info = {
      id,
      name: id,
      description: "Check an explicitly selected Soulsteads Agent Home without changing it.",
      path: fileURLToPath(source),
      content: markdown.slice(boundary + delimiter.length).trim(),
      autoinvoke: false,
    };
    const registration = await ctx.skill.transform((editor) => {
      if (!editor.get(id)) editor.add({ ...info });
    });
    return () => registration.dispose();
  },
};
