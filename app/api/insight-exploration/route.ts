import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: Request) {
  try {
    const { query } = await request.json();

    const response = await fetch(`${BACKEND_URL}/api/insight-exploration/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: query ?? '' }),
    });

    if (!response.ok || !response.body) {
      const text = await response.text();
      return NextResponse.json(
        { error: text || 'Backend request failed' },
        { status: response.status }
      );
    }

    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': 'application/x-ndjson',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    console.error('Error proxying insight exploration to backend:', error);
    return NextResponse.json(
      { error: 'Failed to connect to backend' },
      { status: 500 }
    );
  }
}
