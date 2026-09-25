export async function api(path, {
  token,
  body,
  method = 'GET',
  ...options
} = {}) {
  const headers = {
    ...(token ? {
      Authorization: `Bearer ${token}`
    } : {})
  };
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      method,
      headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: options.signal || AbortSignal.timeout(20000)
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Không kết nối được máy chủ. Vui lòng thử lại.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = Array.isArray(data.detail) ? data.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join('; ') : data.detail || 'Không thể thực hiện yêu cầu.';
    if (response.status === 401 && token) window.dispatchEvent(new Event('session-expired'));
    throw new Error(message);
  }
  return data;
}
export async function downloadCV(url, token) {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    signal: AbortSignal.timeout(20000)
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Không tải được CV');
  }
  const link = document.createElement('a');
  const objectUrl = URL.createObjectURL(await response.blob());
  link.href = objectUrl;
  link.download = 'JobApply-CV.pdf';
  link.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
