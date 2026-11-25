'use strict';
const MAX_BYTES = 90 * 1024 * 1024;
class HttpError extends Error {
  constructor(status, message, code) { super(message); this.status = status; this.code = code; }
}
function validatePayload(value) {
  if (!value || ![1, 2, 3, 4].includes(value.version) || !Array.isArray(value.cards) ||
      !value.session || typeof value.session !== 'object' || Array.isArray(value.session) ||
      value.cards.some(c => !c || typeof c.id !== 'string' || !Array.isArray(c.fields) ||
        c.fields.length !== 7 || c.fields.some(f => typeof f !== 'string'))) {
    throw new HttpError(400, '保存データの形式が不正です。');
  }
  // These are internal storage references, never accepted from clients.
  if (value.cards.some(c => c.fields[6].startsWith('azure-image:'))) {
    throw new HttpError(400, '画像を含む完全なデータを送信してください。');
  }
  return value;
}
function createService({ store, authenticate, fetchLegacy, origins, maxBytes = MAX_BYTES }) {
  return async request => {
    const origin = request.headers.get('origin');
    const allowed = !origin || origins.includes(origin);
    const headers = {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff', 'Vary': 'Origin'};
    if (origin && allowed) headers['Access-Control-Allow-Origin'] = origin;
    const reply = (status, value) => ({ status, headers, body: JSON.stringify(value) });
    try {
      if (!allowed) throw new HttpError(403, 'このサイトからは接続できません。');
      if (request.method === 'OPTIONS') {
        headers['Access-Control-Allow-Methods'] = 'GET, PUT, OPTIONS';
        headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type';
        headers['Access-Control-Max-Age'] = '600';
        return { status: 204, headers };
      }
      if (!['GET', 'PUT'].includes(request.method)) throw new HttpError(405, '未対応の操作です。');
      const token = /^Bearer ([^\s]+)$/i.exec(request.headers.get('authorization') || '')?.[1];
      if (!token) throw new HttpError(401, 'ログインしてください。');
      const userId = await authenticate(token);
      if (!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(userId || '')) {
        throw new HttpError(401, 'ログイン情報を確認できません。');
      }
      if (request.method === 'GET') {
        let meta = await store.metadata(userId);
        if (!meta && fetchLegacy) {
          const legacy = await fetchLegacy(token, userId);
          if (legacy) {
            validatePayload(legacy);
            if (Buffer.byteLength(JSON.stringify(legacy)) > maxBytes) throw new HttpError(413, 'データが大きすぎます。');
            try { await store.save(userId, 0, legacy); }
            catch (error) { if (!error.conflict) throw error; }
            meta = await store.metadata(userId);
          }
        }
        if (!meta) return reply(200, null);
        if (new URL(request.url).searchParams.get('metadata') === '1') return reply(200, {revision: meta.revision});
        return reply(200, await store.read(userId));
      }
      if (Number(request.headers.get('content-length')) > maxBytes) throw new HttpError(413, 'データが大きすぎます。');
      const text = await request.text();
      if (Buffer.byteLength(text) > maxBytes) throw new HttpError(413, 'データが大きすぎます。');
      let data;
      try { data = JSON.parse(text); } catch { throw new HttpError(400, 'JSONを読み込めません。'); }
      if (!Number.isSafeInteger(data?.expected_revision) || data.expected_revision < 0 || data.expected_revision >= Number.MAX_SAFE_INTEGER) {
        throw new HttpError(400, '版番号が不正です。');
      }
      validatePayload(data.new_payload);
      const revision = await store.save(userId, data.expected_revision, data.new_payload);
      return reply(200, {revision});
    } catch (error) {
      if (error.conflict) return reply(409, {code: '40001', message: '別の端末が更新しました。読み直して再試行します。'});
      return reply(error.status || 503, {code: error.code || 'sync_error', message: error.status ? error.message : 'Azure保存先へ接続できません。端末のデータは保持されています。'});
    }
  };
}
// Supabase validates the token server-side. The untrusted JWT expiry can only SHORTEN this cache.
function createAuthenticator({url, key, fetchImpl = fetch, now = Date.now}) {
  const cache = new Map();
  return async token => {
    const cached = cache.get(token);
    if (cached && cached.until > now()) return cached.id;
    const response = await fetchImpl(url + '/auth/v1/user', {headers: {apikey: key, Authorization: 'Bearer ' + token}, signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new HttpError(response.status === 401 || response.status === 403 ? 401 : 503, 'ログイン情報を確認できません。');
    const user = await response.json();
    if (!user?.id) throw new HttpError(401, 'ログイン情報が不正です。');
    let until = now() + 60000;
    try { const exp = JSON.parse(Buffer.from(token.split('.')[1], 'base64url')).exp; if (Number.isFinite(exp)) until = Math.min(until, exp * 1000); } catch {}
    if (cache.size >= 1000) cache.delete(cache.keys().next().value);
    cache.set(token, {id: user.id, until});
    return user.id;
  };
}
function createLegacyReader({url, key, fetchImpl = fetch}) {
  return async (token, userId) => {
    const response = await fetchImpl(url + '/rest/v1/word_progress?select=payload&user_id=eq.' + encodeURIComponent(userId), {
      headers: {apikey: key, Authorization: 'Bearer ' + token}, signal: AbortSignal.timeout(60000)
    });
    if (!response.ok) throw new HttpError(503, '旧保存先のデータを確認できません。移行を中止しました。');
    const rows = await response.json();
    if (!Array.isArray(rows) || rows.length > 1) throw new HttpError(503, '旧保存先の応答が不正です。');
    return rows[0]?.payload || null;
  };
}
module.exports = {createService, createAuthenticator, createLegacyReader, HttpError, MAX_BYTES};
