'use strict';
const {app} = require('@azure/functions');
const {CosmosClient} = require('@azure/cosmos');
const {BlobServiceClient} = require('@azure/storage-blob');
const {createStore} = require('./store');
const {createService, createAuthenticator, createLegacyReader} = require('./service');
let instance;
function services() {
  if (instance) return instance;
  const env = process.env;
  for (const name of ['COSMOS_ENDPOINT', 'COSMOS_KEY', 'SUPABASE_URL', 'SUPABASE_PUBLIC_KEY', 'AzureWebJobsStorage', 'ALLOWED_ORIGINS']) {
    if (!env[name]) throw new Error('Missing server configuration: ' + name);
  }
  const url = env.SUPABASE_URL.replace(/\/$/, '');
  if (!/^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(url)) throw new Error('Invalid auth server');
  const cosmos = new CosmosClient({endpoint: env.COSMOS_ENDPOINT, key: env.COSMOS_KEY});
  const container = cosmos.database(env.COSMOS_DATABASE || 'flashcards').container(env.COSMOS_CONTAINER || 'user-data');
  const blobs = BlobServiceClient.fromConnectionString(env.AzureWebJobsStorage).getContainerClient('flashcards-private');
  const store = createStore({container, blobs});
  const authConfig = {url, key: env.SUPABASE_PUBLIC_KEY};
  const handler = createService({store, authenticate: createAuthenticator(authConfig),
    fetchLegacy: env.BOOTSTRAP_FROM_SUPABASE === 'true' ? createLegacyReader(authConfig) : null,
    origins: env.ALLOWED_ORIGINS.split(',').map(s => s.trim()).filter(Boolean)});
  instance = {store, blobs, container, handler};
  return instance;
}
app.http('state', {route: 'state', methods: ['GET', 'PUT', 'OPTIONS'], authLevel: 'anonymous', handler: async request => {
  try { return await services().handler(request); }
  catch { return {status: 503, jsonBody: {message: 'Azureの接続設定を確認してください。'}, headers: {'Cache-Control': 'no-store'}}; }
}});
app.http('health', {route: 'health', methods: ['GET'], authLevel: 'anonymous', handler: async () => {
  try {
    const {blobs} = services();
    await blobs.getProperties();
    // Check the container itself; a missing container must not look like an empty account.
    await services().container.read();
    return {status: 200, jsonBody: {service: 'flash-cards-sync', version: 1, ready: true}, headers: {'Cache-Control': 'no-store'}};
  } catch { return {status: 503, jsonBody: {ready: false}, headers: {'Cache-Control': 'no-store'}}; }
}});
app.timer('cleanupSnapshots', {schedule: '0 17 3 * * *', handler: async (_timer, context) => {
  const deleted = await services().store.cleanup();
  context.log('Removed old snapshot count:', deleted);
}});
