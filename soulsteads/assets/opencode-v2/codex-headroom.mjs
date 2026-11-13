// Optional OpenCode v2 native hook. No requests are made by this module.
const ID = "soulstead.codex-headroom.v2";
const UPSTREAM = "https://chatgpt.com/backend-api/codex/responses";
const INVALID_PROXY = "Headroom proxy requires an explicit canonical loopback HTTP /v1/responses URL";

function checkedProxy(value) {
  let url;
  try {
    if (typeof value !== "string") throw new Error();
    url = new URL(value);
  } catch {
    throw new Error(INVALID_PROXY);
  }
  if (value !== url.href || url.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash ||
      url.pathname !== "/v1/responses") {
    throw new Error(INVALID_PROXY);
  }
  return value;
}

export function createCodexHeadroomPlugin({proxyUrl}) {
  proxyUrl = checkedProxy(proxyUrl);
  return {
    id: ID,
    async setup(ctx) {
      await ctx.session.hook("http.request", event => {
        const original = event.request;
        if (original.method !== "POST" || original.url !== UPSTREAM) return;
        const headers = new Headers(original.headers);
        headers.set("x-headroom-base-url", "https://chatgpt.com");
        headers.set("x-headroom-original-path", "/backend-api/codex/responses");
        event.request = new Request(proxyUrl, {
          method: "POST",
          headers,
          body: original.body,
          credentials: original.credentials,
          signal: original.signal,
          redirect: "error",
          duplex: "half",
        });
      });
    },
  };
}

export default {
  id: ID,
  async setup(ctx) {
    return createCodexHeadroomPlugin({
      proxyUrl: process.env.SOULSTEADS_HEADROOM_PROXY_URL,
    }).setup(ctx);
  },
};
