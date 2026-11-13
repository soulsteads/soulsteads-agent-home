// Optional native compatibility hook; only an explicitly selected model set changes.
const ID = "soulstead.qwen-single-system.v2";
const INVALID_SELECTION = "Single-system hook requires an explicit provider and a nonempty bounded list of distinct model IDs";

function validId(value) {
  return typeof value === "string" && value.length > 0 &&
    new TextEncoder().encode(value).length <= 256 && !/[\s\u0000-\u001f\u007f]/u.test(value);
}

export function createSingleSystemPlugin({providerId, modelIds}) {
  if (!validId(providerId) || !Array.isArray(modelIds) || modelIds.length === 0 ||
      modelIds.length > 128 || !modelIds.every(validId) || new Set(modelIds).size !== modelIds.length) {
    throw new Error(INVALID_SELECTION);
  }
  const models = new Set(modelIds);
  return {
    id: ID,
    async setup(ctx) {
      const normalize = event => {
        if (event.model.providerID !== providerId || !models.has(event.model.id)) return;
        if (event.system.length > 1) {
          if (!event.system.every(part => part?.type === "text" && typeof part.text === "string" &&
              Reflect.ownKeys(part).every(key => key === "type" || key === "text"))) {
            throw new Error("Selected model requires text-only system parts");
          }
          const text = event.system.map(part => part.text).join("\n\n");
          event.system.splice(0, event.system.length, {type: "text", text});
        }
      };
      for (const kind of ["context", "compaction", "generate", "title"]) {
        await ctx.session.hook(kind, normalize);
      }
    },
  };
}

export default {
  id: ID,
  async setup(ctx) {
    let modelIds;
    const encoded = process.env.SOULSTEADS_SINGLE_SYSTEM_MODELS;
    try {
      if (typeof encoded !== "string" || encoded.length > 65536) throw new Error();
      modelIds = JSON.parse(encoded);
    } catch {
      throw new Error(INVALID_SELECTION);
    }
    return createSingleSystemPlugin({
      providerId: process.env.SOULSTEADS_SINGLE_SYSTEM_PROVIDER,
      modelIds,
    }).setup(ctx);
  },
};
