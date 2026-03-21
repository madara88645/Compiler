import { NextResponse } from 'next/server';
import { API_BASE } from '@/config';

const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX_REQUESTS = 30;
const clientRateLimits = new Map<string, number[]>();

function getClientIp(request: Request): string {
  const forwardedFor = request.headers.get('x-forwarded-for');
  if (forwardedFor) {
    return forwardedFor.split(',')[0]?.trim() || 'unknown';
  }

  return request.headers.get('x-real-ip')?.trim() || 'unknown';
}

function isRateLimited(clientIp: string): boolean {
  const now = Date.now();
  const history = (clientRateLimits.get(clientIp) || []).filter(
    (timestamp) => timestamp > now - RATE_LIMIT_WINDOW_MS
  );

  if (history.length >= RATE_LIMIT_MAX_REQUESTS) {
    clientRateLimits.set(clientIp, history);
    return true;
  }

  history.push(now);
  clientRateLimits.set(clientIp, history);
  return false;
}

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch (error) {
    console.error('Invalid JSON body:', error);
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const apiKey = process.env.API_KEY?.trim();
  if (!apiKey) {
    return NextResponse.json(
      { error: 'Compile proxy is not configured on the server' },
      { status: 503 }
    );
  }

  const clientIp = getClientIp(request);
  if (isRateLimited(clientIp)) {
    return NextResponse.json({ error: 'Rate limit exceeded' }, { status: 429 });
  }

  try {
    const res = await fetch(`${API_BASE}/compile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
      },
      body: JSON.stringify(body),
    });

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json') || contentType.includes('+json')) {
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        'content-type': contentType || 'text/plain; charset=utf-8',
      },
    });
  } catch (error) {
    console.error('Proxy Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
