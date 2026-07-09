import { proxyBackendRequest } from "@/lib/server/backendProxy";

export async function POST(request: Request): Promise<Response> {
  // A benchmark run makes paid upstream LLM calls. Retrying a failed POST can
  // leave the original work running while starting a duplicate benchmark.
  return proxyBackendRequest(request, "/benchmark/run");
}
