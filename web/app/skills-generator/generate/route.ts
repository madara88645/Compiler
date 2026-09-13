import { GENERATOR_UPSTREAM_TIMEOUT_MS, proxyBackendRequest } from "@/lib/server/backendProxy";

export const maxDuration = 180;

export async function POST(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/skills-generator/generate", {
    upstreamTimeoutMs: GENERATOR_UPSTREAM_TIMEOUT_MS,
  });
}
