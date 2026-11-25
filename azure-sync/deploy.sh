#!/usr/bin/env bash
# Run in the user's Azure Cloud Shell (Bash). No private study data is downloaded.
set -euo pipefail
set +x
umask 077
TASK_DIR=$(mktemp -d)
trap 'rm -rf "$TASK_DIR"' EXIT
RESOURCE_GROUP=flash-cards-rg
COSMOS_ACCOUNT=flashcards-16436
AUTH_URL=https://glpnosfxkewlqzpqnsep.supabase.co
APP_ORIGIN=https://kmhrt16436-beep.github.io
SOURCE_REF=${FLASH_SOURCE_REF:?FLASH_SOURCE_REF must be the verified Git commit SHA}
if [[ ! "$SOURCE_REF" =~ ^[a-f0-9]{40}$ ]]; then echo 'Invalid source revision.'; exit 1; fi
for program in az curl python3; do command -v "$program" >/dev/null || { echo "Missing command: $program"; exit 1; }; done
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
printf 'Subscription: %s\n' "$SUBSCRIPTION_NAME"
if [[ "$SUBSCRIPTION_NAME" != 'Azure for Students' ]]; then echo 'Select the Azure for Students subscription first. No resources created.'; exit 1; fi
az cosmosdb sql container show -g "$RESOURCE_GROUP" -a "$COSMOS_ACCOUNT" -d flashcards -n user-data --output none
FREE_TIER=$(az cosmosdb show -g "$RESOURCE_GROUP" -n "$COSMOS_ACCOUNT" --query enableFreeTier -o tsv)
if [[ "${FREE_TIER,,}" != 'true' ]]; then echo 'Cosmos DB Free Tier is not enabled. No resources created.'; exit 1; fi
# Register the providers required by the documented Flex Consumption setup.
for namespace in Microsoft.Web Microsoft.App Microsoft.Storage; do
  state=$(az provider show --namespace "$namespace" --query registrationState -o tsv)
  if [[ "$state" != 'Registered' ]]; then
    printf 'Registering %s (this can take several minutes)...\n' "$namespace"
    az provider register --namespace "$namespace" --wait --output none
  fi
done
# Check regional Flex availability before creating any new services.
LOCATION=${FLASH_FUNCTION_LOCATION:-japaneast}
az functionapp list-flexconsumption-locations --output json > "$TASK_DIR/locations.json"
python3 - "$TASK_DIR/locations.json" "$LOCATION" <<'PY'
import json,sys
rows=json.load(open(sys.argv[1]));wanted=sys.argv[2].replace(' ','').lower()
if not any(str(r.get('name',r.get('location',''))).replace(' ','').lower()==wanted for r in rows):
    raise SystemExit('Flex Consumption is not available in the requested region. Stop and share this message.')
PY
# Deterministic names allow a failed deployment to be resumed without duplicate resources.
SUFFIX=$(python3 - "$SUBSCRIPTION_ID" <<'PY'
import hashlib,sys
print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:10])
PY
)
FUNCTION_NAME="flashcards-api-$SUFFIX"
STORAGE_NAME="flashcards$SUFFIX"
printf 'Function: %s\nStorage: %s\n' "$FUNCTION_NAME" "$STORAGE_NAME"
printf 'Supabase Publishable key (public key only): '
read -r -s PUBLIC_KEY
printf '\n'
export PUBLIC_KEY
python3 - <<'PY'
import os,json,base64
key=os.environ['PUBLIC_KEY']
if key.startswith('sb_publishable_') and len(key)>20: pass
elif key.startswith('eyJ'):
    try:
        data=key.split('.')[1];role=json.loads(base64.urlsafe_b64decode(data+'='*(-len(data)%4))).get('role')
    except Exception: raise SystemExit('Invalid public key.')
    if role!='anon': raise SystemExit('Only the anon PUBLIC key is allowed.')
else: raise SystemExit('Use a Supabase Publishable key, never a secret or service_role key.')
PY
# Confirm the key belongs to the expected auth server before provisioning.
python3 - "$AUTH_URL" <<'PY'
import os,sys,urllib.request
r=urllib.request.Request(sys.argv[1]+'/auth/v1/settings',headers={'apikey':os.environ['PUBLIC_KEY']})
try:
    with urllib.request.urlopen(r,timeout=20) as response:
        if response.status!=200: raise RuntimeError()
except Exception: raise SystemExit('The public key could not be verified for the current Supabase project.')
PY
mkdir -p "$TASK_DIR/source/azure-sync/src"
for file in host.json package.json package-lock.json package.py check-health.py src/functions.js src/service.js src/store.js; do
  curl -fsSL --retry 2 --max-time 45 "https://raw.githubusercontent.com/kmhrt16436-beep/vocab-app/$SOURCE_REF/azure-sync/$file" -o "$TASK_DIR/source/azure-sync/$file"
done
if ! az storage account show -g "$RESOURCE_GROUP" -n "$STORAGE_NAME" --output none 2>/dev/null; then
  az storage account create -g "$RESOURCE_GROUP" -n "$STORAGE_NAME" -l "$LOCATION" --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false --min-tls-version TLS1_2 --output none
fi
az storage account update -g "$RESOURCE_GROUP" -n "$STORAGE_NAME" --allow-blob-public-access false --output none
STORAGE_CONNECTION=$(az storage account show-connection-string -g "$RESOURCE_GROUP" -n "$STORAGE_NAME" --query connectionString -o tsv)
export STORAGE_CONNECTION
# Pass credentials via a protected file/environment, never print them or embed them in client HTML.
export AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONNECTION"
az storage container create --name flashcards-private --public-access off --output none
unset AZURE_STORAGE_CONNECTION_STRING
if ! az functionapp show -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --output none 2>/dev/null; then
  az functionapp create -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --storage-account "$STORAGE_NAME" --flexconsumption-location "$LOCATION" --runtime node --runtime-version 22 --instance-memory 2048 --disable-app-insights true --output none
fi
COSMOS_ENDPOINT=$(az cosmosdb show -g "$RESOURCE_GROUP" -n "$COSMOS_ACCOUNT" --query documentEndpoint -o tsv)
COSMOS_KEY=$(az cosmosdb keys list -g "$RESOURCE_GROUP" -n "$COSMOS_ACCOUNT" --query primaryMasterKey -o tsv)
export COSMOS_ENDPOINT COSMOS_KEY AUTH_URL APP_ORIGIN
python3 - "$TASK_DIR/settings.json" <<'PY'
import json,os,sys
settings={
 'COSMOS_ENDPOINT':os.environ['COSMOS_ENDPOINT'],'COSMOS_KEY':os.environ['COSMOS_KEY'],
 'COSMOS_DATABASE':'flashcards','COSMOS_CONTAINER':'user-data',
 'SUPABASE_URL':os.environ['AUTH_URL'],'SUPABASE_PUBLIC_KEY':os.environ['PUBLIC_KEY'],
 'ALLOWED_ORIGINS':os.environ['APP_ORIGIN'],'BOOTSTRAP_FROM_SUPABASE':'true'
}
with open(sys.argv[1],'w') as f: json.dump(settings,f)
PY
az functionapp config appsettings set -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --settings "@$TASK_DIR/settings.json" --output none
unset COSMOS_KEY PUBLIC_KEY STORAGE_CONNECTION
python3 "$TASK_DIR/source/azure-sync/package.py" "$TASK_DIR/source/azure-sync" "$TASK_DIR/deploy.zip"
az functionapp deployment source config-zip -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --src "$TASK_DIR/deploy.zip" --build-remote true --output none
HOSTNAME=$(az resource show -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --resource-type Microsoft.Web/sites --query properties.defaultHostName -o tsv)
python3 "$TASK_DIR/source/azure-sync/check-health.py" "$HOSTNAME"
printf '\nThe live app has NOT switched storage yet. Keep Supabase running.\n'
