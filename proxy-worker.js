/**
 * Cloudflare Worker — Etherscan API Proxy
 *
 * Deploy for FREE on Cloudflare Workers (100,000 req/day)
 * No installation needed, no software to run. Works from China.
 *
 * HOW TO DEPLOY (5 minutes):
 * 1. Go to https://dash.cloudflare.com/ — sign up (free)
 * 2. Click "Workers & Pages" → "Create application" → "Create Worker"
 * 3. Give it a name (e.g. "eth-proxy"), click "Deploy"
 * 4. Click "Edit code", paste this entire file, click "Deploy"
 * 5. Copy your worker URL (looks like: eth-proxy.your-username.workers.dev)
 * 6. Use it as: https://eth-proxy.your-username.workers.dev/?<etherscan params>
 */

export default {
  async fetch(request) {
    const url = new URL(request.url)
    const params = url.searchParams
    const path = params.get('_path') || 'api'

    // Build target URL
    const targetUrl = new URL(`https://api.etherscan.io/${path}`)
    for (const [key, value] of params) {
      if (key !== '_path') {
        targetUrl.searchParams.set(key, value)
      }
    }

    const response = await fetch(targetUrl.toString(), {
      method: request.method,
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
      },
    })

    // Return response with CORS headers so Streamlit can access it
    const modifiedResponse = new Response(response.body, {
      status: response.status,
      headers: {
        ...Object.fromEntries(response.headers),
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Cache-Control': 'public, max-age=5',
      },
    })

    return modifiedResponse
  },
}
