import { NextRequest, NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const limit = searchParams.get('limit')
    const hasAction = searchParams.get('has_action')

    const queryParams = new URLSearchParams()
    if (limit) queryParams.append('limit', limit)
    if (hasAction) queryParams.append('has_action', hasAction)

    const query = queryParams.toString()
    const response = await fetch(
      `${BACKEND_API_URL}/api/v1/transactions${query ? `?${query}` : ''}`
    )

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching transactions from backend:', error)

    return NextResponse.json(
      { error: 'Failed to load transactions from backend' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const response = await fetch(`${BACKEND_API_URL}/api/v1/transactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error creating transaction in backend:', error)

    return NextResponse.json(
      { error: 'Failed to create transaction in backend' },
      { status: 500 }
    )
  }
}
