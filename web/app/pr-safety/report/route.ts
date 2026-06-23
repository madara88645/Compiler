import { proxyBackendRequest } from "@/lib/server/backendProxy";

export async function POST(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/pr-safety/report", {
    retryNetworkErrors: true,
  });
}
