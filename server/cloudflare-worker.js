export default {
  async fetch(request) {
    const url = new URL(request.url);
    const targetUrl = 'https://opencode.ai' + url.pathname + url.search;

    const modifiedHeaders = new Headers(request.headers);
    modifiedHeaders.set('Host', 'opencode.ai');

    const response = await fetch(targetUrl, {
      method: request.method,
      headers: modifiedHeaders,
      body: request.method === 'POST' ? request.body : undefined,
    });

    const responseHeaders = new Headers(response.headers);
    responseHeaders.set('Access-Control-Allow-Origin', '*');

    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  },
};
