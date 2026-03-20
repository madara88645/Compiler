import { NextResponse } from 'next/server';
import { API_BASE } from '@/config';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const apiKey = process.env.API_KEY || '';

    const res = await fetch(`${API_BASE}/compile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Proxy Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
