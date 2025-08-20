#!/bin/bash

############################################################################
# Script to build the Docker image for Azure Container Registry (ACR)
#
# Instructions:
# 1. Ensure you're logged into Azure CLI: az login
# 2. Ensure Docker is running
# 3. Run this script to build and push to ACR
############################################################################

# Exit immediately if a command exits with a non-zero status.
set -e

CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(dirname ${CURR_DIR})"
DOCKER_FILE="Dockerfile.azure"
# Updated for Azure Container Registry
ACR_NAME="hrndev"
IMAGE_NAME="${ACR_NAME}.azurecr.io/health-research-api"
IMAGE_TAG="latest"

echo "Logging into Azure Container Registry..."
az acr login --name $ACR_NAME

echo "Building image for Azure Container Apps..."
echo "Running: docker build --platform=linux/amd64 -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKER_FILE $WS_ROOT"
docker build --platform=linux/amd64 -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKER_FILE $WS_ROOT

echo "Pushing to Azure Container Registry..."
echo "Running: docker push $IMAGE_NAME:$IMAGE_TAG"
docker push $IMAGE_NAME:$IMAGE_TAG

echo "✅ Image successfully pushed to ACR: $IMAGE_NAME:$IMAGE_TAG"