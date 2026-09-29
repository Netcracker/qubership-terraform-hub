#!/bin/bash

RG="rg-tfstate"
SA="tfstate339411275"   # az storage account list -g rg-tfstate --query "[].name" -o tsv
SA_ID=$(az storage account show -n $SA -g $RG --query id -o tsv)

# себе (для работы через az login)
az role assignment create \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --role "Storage Blob Data Contributor" \
  --scope $SA_ID

# SP (для работы через ARM_* и в CI)
az role assignment create \
  --assignee "1c775366-3d1d-4a05-b610-f4727a9148da" \
  --role "Storage Blob Data Contributor" \
  --scope $SA_ID
