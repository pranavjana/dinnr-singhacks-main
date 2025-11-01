"use client"

export default function TestApiPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">API Configuration Test</h1>
      <div className="space-y-2">
        <p><strong>NEXT_PUBLIC_API_URL:</strong> {apiUrl}</p>
        <p><strong>Full test URL:</strong> {apiUrl}/api/v1/extraction/rules</p>
        <button
          className="px-4 py-2 bg-blue-500 text-white rounded"
          onClick={async () => {
            try {
              const response = await fetch(`${apiUrl}/api/v1/extraction/rules?active_only=true&limit=100`)
              const data = await response.json()
              console.log('Success!', data)
              alert('Success! Check console')
            } catch (error) {
              console.error('Error:', error)
              alert(`Error: ${error}`)
            }
          }}
        >
          Test API Call
        </button>
      </div>
    </div>
  )
}
