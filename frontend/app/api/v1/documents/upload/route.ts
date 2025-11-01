import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function POST(request: Request) {
  try {
    const formData = await request.formData()

    // Forward multipart form data to backend
    const response = await fetch(`${BACKEND_API_URL}/api/v1/documents/upload`, {
      method: 'POST',
      body: formData, // FormData is sent as-is with proper headers
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend document upload error:', response.status, errorText)

      let errorDetail = 'Document upload failed'
      try {
        const errorJson = JSON.parse(errorText)
        errorDetail = errorJson.detail || errorDetail
      } catch {
        errorDetail = errorText || errorDetail
      }

      return NextResponse.json(
        { error: errorDetail },
        { status: response.status }
      )
    }

    const result = await response.json()
    return NextResponse.json(result)
  } catch (error) {
    console.error('Error in document upload:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to upload document' },
      { status: 500 }
    )
  }
}
