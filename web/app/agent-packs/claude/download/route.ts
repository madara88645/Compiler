import { AGENT_PACK_UPSTREAM_TIMEOUT_MS, proxyBackendRequest } from "@/lib/server/backendProxy";

export const maxDuration = 180;

export async function POST(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/agent-packs/claude/download", {
    retryNetworkErrors: true,
    upstreamTimeoutMs: AGENT_PACK_UPSTREAM_TIMEOUT_MS,
  });
}
