import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET(request: Request) {
  try {
    // Extract query parameters from the request URL
    const { searchParams } = new URL(request.url)
    const queryString = searchParams.toString()

    // Forward to backend with query parameters
    const url = `${BACKEND_API_URL}/api/v1/extraction/rules${queryString ? `?${queryString}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend rules error:', response.status, errorText)
      throw new Error(`Backend API failed: ${response.statusText} - ${errorText}`)
    }

    const rules = await response.json()
    return NextResponse.json(rules)
  } catch (error) {
    console.error('Error fetching rules:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch rules' },
      { status: 500 }
    )
  }
}
