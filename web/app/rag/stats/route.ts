import { proxyBackendRequest } from "@/lib/server/backendProxy";

export async function GET(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/rag/stats");
}
