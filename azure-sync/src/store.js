'use strict';
const {createHash, randomUUID} = require('node:crypto');
const {promisify} = require('node:util');
const gzip = promisify(require('node:zlib').gzip), gunzip = promisify(require('node:zlib').gunzip);
const {MAX_BYTES} = require('./service');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const IMAGE_REF = /^azure-image:v1:([a-f0-9]{64})$/;
const conflict = () => Object.assign(new Error('revision conflict'), {conflict: true});
const status = error => Number(error.code || error.statusCode);
function createStore({container, blobs, now = Date.now}) {
  const imageCache = new Map();
  async function metadata(userId) {
    try { return (await container.item('state', userId).read()).resource || null; }
    catch (error) { if (status(error) === 404) return null; throw error; }
  }
  async function ensureImage(userId, value) {
    const digest = hash(value), name = `${userId}/images/${digest}.gz`;
    const cached = imageCache.get(name);
    if (!cached || cached < now()) {
      const bytes = await gzip(Buffer.from(value));
      try { await blobs.getBlockBlobClient(name).uploadData(bytes, {conditions: {ifNoneMatch: '*'}, blobHTTPHeaders: {blobContentType: 'application/gzip'}}); }
      catch (error) { if (![409, 412].includes(status(error))) throw error; }
      if (imageCache.size >= 2000) imageCache.delete(imageCache.keys().next().value);
      imageCache.set(name, now() + 3600000);
    }
    return 'azure-image:v1:' + digest;
  }
  async function save(userId, expected, payload) {
    const previous = await metadata(userId);
    if ((previous?.revision || 0) !== expected) throw conflict();
    const started = now(), next = structuredClone(payload);
    const unique = new Map();
    // Process in sequence to bound memory while preserving exact image bytes and MIME types.
    for (const card of next.cards) {
      const value = card.fields[6];
      if (/^data:image\/(?:png|jpeg|webp);base64,/.test(value)) {
        if (!unique.has(value)) unique.set(value, await ensureImage(userId, value));
        card.fields[6] = unique.get(value);
      }
    }
    const raw = Buffer.from(JSON.stringify(next));
    if (raw.length > MAX_BYTES) throw new Error('snapshot too large');
    const bytes = await gzip(raw), name = `${userId}/snapshots/${randomUUID()}.json.gz`;
    const blob = blobs.getBlockBlobClient(name);
    await blob.uploadData(bytes, {conditions: {ifNoneMatch: '*'}, metadata: {owner: userId}, blobHTTPHeaders: {blobContentType: 'application/gzip'}});
    const record = {id: 'state', userId, revision: expected + 1, blobName: name, sha256: hash(raw), updatedAt: new Date(now()).toISOString()};
    // A blob old enough for garbage collection can never be committed later.
    if (now() - started > 15 * 60000) throw new Error('save timed out');
    try {
      if (previous) await container.item('state', userId).replace(record, {accessCondition: {type: 'IfMatch', condition: previous._etag}});
      else await container.items.create(record);
    } catch (error) {
      if ([409, 412].includes(status(error))) {
        await blob.deleteIfExists().catch(() => {});
        throw conflict();
      }
      // A lost response may mean the commit succeeded. Never delete on ambiguous failure.
      throw error;
    }
    return record.revision;
  }
  async function read(userId) {
    for (let attempt = 0; attempt < 3; attempt++) {
      const meta = await metadata(userId);
      if (!meta) return null;
      if (!meta.blobName.startsWith(userId + '/snapshots/')) throw new Error('invalid owner');
      let raw;
      try { raw = await gunzip(await blobs.getBlockBlobClient(meta.blobName).downloadToBuffer(), {maxOutputLength: MAX_BYTES}); }
      catch (error) { if (status(error) === 404) continue; throw error; }
      if (hash(raw) !== meta.sha256) throw new Error('snapshot checksum mismatch');
      const payload = JSON.parse(raw), images = new Map();
      for (const card of payload.cards) {
        const match = IMAGE_REF.exec(card.fields[6]);
        if (!match) continue;
        if (!images.has(match[1])) {
          const image = await gunzip(await blobs.getBlockBlobClient(`${userId}/images/${match[1]}.gz`).downloadToBuffer(), {maxOutputLength: MAX_BYTES});
          if (hash(image) !== match[1]) throw new Error('image checksum mismatch');
          images.set(match[1], image.toString('utf8'));
        }
        card.fields[6] = images.get(match[1]);
      }
      return {revision: meta.revision, payload};
    }
    throw new Error('snapshot unavailable');
  }
  async function cleanup() {
    let deleted = 0;
    // Old snapshots survive at least 24 hours, allowing in-flight reads to finish or retry.
    // Images are deduplicated and retained; no timer ever deletes a currently referenced image.
    for await (const blob of blobs.listBlobsFlat()) {
      const match = /^([a-f0-9-]{36})\/snapshots\/[a-f0-9-]+\.json\.gz$/i.exec(blob.name);
      if (!match || !blob.properties.lastModified || +blob.properties.lastModified >= now() - 86400000) continue;
      const current = await metadata(match[1]);
      if (current?.blobName === blob.name) continue;
      await blobs.getBlockBlobClient(blob.name).deleteIfExists();
      deleted++;
    }
    return deleted;
  }
  return {metadata, save, read, cleanup};
}
module.exports = {createStore};
