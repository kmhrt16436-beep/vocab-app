#!/usr/bin/env bash
# Repair code packaging on the existing Function app. Never changes credentials or resources.
set -euo pipefail
set +x
umask 077
SOURCE_REF=${FLASH_SOURCE_REF:?Set FLASH_SOURCE_REF to the verified Git commit SHA}
if [[ ! "$SOURCE_REF" =~ ^[a-f0-9]{40}$ ]]; then echo 'Invalid source revision.'; exit 1; fi
RESOURCE_GROUP=flash-cards-rg
FUNCTION_NAME=flashcards-api-97c87b4b3a
TASK_DIR=$(mktemp -d)
trap 'rm -rf "$TASK_DIR"' EXIT
az resource show -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --resource-type Microsoft.Web/sites --output none
mkdir -p "$TASK_DIR/source/src"
for file in host.json package.json package-lock.json package.py check-health.py src/functions.js src/service.js src/store.js; do
  curl -fsSL --retry 2 --max-time 45 "https://raw.githubusercontent.com/kmhrt16436-beep/vocab-app/$SOURCE_REF/azure-sync/$file" -o "$TASK_DIR/source/$file"
done
python3 "$TASK_DIR/source/package.py" "$TASK_DIR/source" "$TASK_DIR/deploy.zip"
az functionapp cors add -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --allowed-origins https://kmhrt16436-beep.github.io --output none
az functionapp deployment source config-zip -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --src "$TASK_DIR/deploy.zip" --build-remote true --output none
HOSTNAME=$(az resource show -g "$RESOURCE_GROUP" -n "$FUNCTION_NAME" --resource-type Microsoft.Web/sites --query properties.defaultHostName -o tsv)
python3 "$TASK_DIR/source/check-health.py" "$HOSTNAME"
printf '\nCode repaired. The live app has NOT switched storage yet. Keep Supabase running.\n'
