import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
afterEach(() => vi.unstubAllGlobals());
describe('API client', () => {
  it('keeps browser URLs on the gateway and passes the signed token', async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'saved'
      })
    });
    vi.stubGlobal('fetch', fetch);
    expect(await api('/application/applications', {
      method: 'POST',
      token: 'signed',
      body: {
        cv_id: 'cv'
      }
    })).toEqual({
      id: 'saved'
    });
    expect(fetch).toHaveBeenCalledWith('/api/application/applications', expect.objectContaining({
      method: 'POST',
      headers: {
        Authorization: 'Bearer signed',
        'Content-Type': 'application/json'
      }
    }));
  });
  it('surfaces validation errors without reporting success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{
          loc: ['body', 'email'],
          msg: 'Email không hợp lệ'
        }]
      })
    }));
    await expect(api('/account/auth/register')).rejects.toThrow('email: Email không hợp lệ');
  });
  it('expires the session when a protected request is unauthorized', async () => {
    const listener = vi.fn();
    window.addEventListener('session-expired', listener, {
      once: true
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({
        detail: 'Hết hạn'
      })
    }));
    await expect(api('/account/me', {
      token: 'expired'
    })).rejects.toThrow('Hết hạn');
    expect(listener).toHaveBeenCalledOnce();
  });
  it('gives a controlled connection error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(api('/job/jobs')).rejects.toThrow('Không kết nối được máy chủ');
  });
});
