export async function onRequest({ request, env }) {
  if (!env.BACKEND_URL) {
    return Response.json(
      { detail: "BACKEND_URL is not configured for this Pages project." },
      { status: 500 },
    );
  }

  const incomingUrl = new URL(request.url);
  const backendUrl = new URL(env.BACKEND_URL);
  const targetUrl = new URL(
    `${incomingUrl.pathname}${incomingUrl.search}`,
    backendUrl,
  );
  const upstreamRequest = new Request(targetUrl, request);
  upstreamRequest.headers.set("X-Forwarded-Host", incomingUrl.host);
  upstreamRequest.headers.set("X-Forwarded-Proto", incomingUrl.protocol.slice(0, -1));
  upstreamRequest.headers.delete("host");

  return fetch(new Request(upstreamRequest, { redirect: "manual" }));
}
