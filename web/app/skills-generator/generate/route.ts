import { proxyBackendRequest } from "@/lib/server/backendProxy";

const GENERATOR_UPSTREAM_TIMEOUT_MS = 40_000;

export async function POST(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/skills-generator/generate", {
    upstreamTimeoutMs: GENERATOR_UPSTREAM_TIMEOUT_MS,
  });
}
