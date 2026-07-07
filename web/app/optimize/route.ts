import { NextResponse } from "next/server";

import { proxyBackendRequest } from "@/lib/server/backendProxy";

export async function GET(request: Request): Promise<Response> {
  return NextResponse.redirect(new URL("/optimizer", request.url), 307);
}

export async function POST(request: Request): Promise<Response> {
  return proxyBackendRequest(request, "/optimize", {
    retryNetworkErrors: true,
  });
}
