#!/bin/bash

export LOCATION="swedencentral"            # или westeurope / northeurope
export RG="rg-tfstate"
export SA="tfstate$RANDOM$RANDOM"          # глобально уникальное имя, 3–24 символа, только a-z0-9
export CONTAINER="tfstate"

az group create -n $RG -l $LOCATION

az storage account create \
  -n $SA -g $RG -l $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

# версионирование и soft delete — защита от случайной порчи state
az storage account blob-service-properties update \
  --account-name $SA -g $RG \
  --enable-versioning true \
  --enable-delete-retention true --delete-retention-days 7

az storage container create -n $CONTAINER --account-name $SA --auth-mode login

echo "Storage account: $SA"
