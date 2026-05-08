import { proxyBackendRequest } from "@/lib/server/backendProxy";

export async function POST(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/rag/search", { requireServerApiKey: true });
}
