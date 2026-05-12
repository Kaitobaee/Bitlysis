type GatewayEnv = {
  API_CONTAINER?: Fetcher;
  ALLOWED_ORIGIN?: string;
};

function corsHeaders(env: GatewayEnv): HeadersInit {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Request-Id,X-Run-Token",
    "Access-Control-Max-Age": "86400",
  };
}

function withCors(response: Response, env: GatewayEnv): Response {
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(corsHeaders(env))) {
    headers.set(key, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function forwardApiRequest(request: Request, env: GatewayEnv): Promise<Response> {
  if (!env.API_CONTAINER) {
    return Response.json(
      {
        error: "API container binding is not configured yet",
        todo: "Bind API_CONTAINER to the Cloudflare Container service before deployment.",
      },
      { status: 501 },
    );
  }

  const url = new URL(request.url);
  url.pathname = url.pathname.replace(/^\/api/, "") || "/";

  return env.API_CONTAINER.fetch(new Request(url, request));
}

export default {
  async fetch(request, env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }

    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return withCors(Response.json({ status: "ok", service: "bitlysis-worker-gateway" }), env);
    }

    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      const response = await forwardApiRequest(request, env);
      return withCors(response, env);
    }

    return withCors(Response.json({ error: "Not found" }, { status: 404 }), env);
  },
} satisfies ExportedHandler<GatewayEnv>;
