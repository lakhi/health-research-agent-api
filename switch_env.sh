#!/bin/bash

# Environment switcher script
# Usage: ./switch_env.sh [local|azure|build|deploy]

ENV=${1:-local}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if environment files exist
check_env_files() {
    if [ ! -f ".env.local" ]; then
        echo -e "${RED}❌ .env.local not found!${NC}"
        echo -e "${YELLOW}💡 Copy .env.local.template to .env.local and fill in your values${NC}"
        return 1
    fi
    
    if [ ! -f ".env.azure" ]; then
        echo -e "${RED}❌ .env.azure not found!${NC}"
        echo -e "${YELLOW}💡 Copy .env.azure.template to .env.azure and fill in your values${NC}"
        return 1
    fi
    
    return 0
}

# Get image configuration
get_image_config() {
    IMAGE_NAME=$(grep IMAGE_NAME .env | cut -d'=' -f2)
    IMAGE_TAG=$(grep IMAGE_TAG .env | cut -d'=' -f2)
    FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
}

# Build Docker image for Azure deployment
build_azure_image() {
    echo -e "${BLUE}🔨 Building Docker image for Azure deployment...${NC}"
    
    if ! check_env_files; then
        return 1
    fi
    
    # Switch to Azure environment first
    cp .env.azure .env
    get_image_config
    
    echo -e "${YELLOW}📦 Building image: ${FULL_IMAGE}${NC}"
    
    # Build production Docker image
    docker build \
        --platform linux/amd64 \
        --tag ${FULL_IMAGE} \
        --tag ${IMAGE_NAME}:azure \
        --build-arg ENVIRONMENT=production \
        .
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully built Azure Docker image: ${FULL_IMAGE}${NC}"
        echo -e "${GREEN}✅ Also tagged as: ${IMAGE_NAME}:azure${NC}"
        
        echo ""
        echo -e "${BLUE}📊 Image Information:${NC}"
        docker images ${IMAGE_NAME} --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
        
        echo ""
        echo -e "${YELLOW}🚀 Next steps for Azure deployment:${NC}"
        echo "1. Push to container registry: docker push ${FULL_IMAGE}"
        echo "2. Deploy to Azure Container Instances or App Service"
        echo "3. Set environment variables in Azure portal"
        
        return 0
    else
        echo -e "${RED}❌ Failed to build Docker image${NC}"
        return 1
    fi
}

# Deploy locally with Azure environment (for testing)
deploy_azure_local() {
    echo -e "${BLUE}🚀 Deploying Azure-configured container locally...${NC}"
    
    if ! check_env_files; then
        return 1
    fi
    
    # Switch to Azure environment
    cp .env.azure .env
    get_image_config
    
    echo -e "${YELLOW}🔍 Stopping any existing containers...${NC}"
    docker stop azure-health-api 2>/dev/null || true
    docker rm azure-health-api 2>/dev/null || true
    
    echo -e "${YELLOW}🐳 Starting Azure-configured container...${NC}"
    docker run -d \
        --name azure-health-api \
        --platform linux/amd64 \
        -p 8001:8000 \
        --env-file .env \
        -e WAIT_FOR_DB=False \
        -e PRINT_ENV_ON_LOAD=True \
        ${FULL_IMAGE}
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Azure container deployed locally on port 8001${NC}"
        echo -e "${BLUE}🔗 Test URL: http://localhost:8001${NC}"
        
        echo ""
        echo -e "${YELLOW}📋 Container logs (last 20 lines):${NC}"
        sleep 3
        docker logs --tail 20 azure-health-api
        
        echo ""
        echo -e "${BLUE}💡 Management commands:${NC}"
        echo "• View logs: docker logs -f azure-health-api"
        echo "• Stop container: docker stop azure-health-api"
        echo "• Remove container: docker rm azure-health-api"
    else
        echo -e "${RED}❌ Failed to deploy Azure container${NC}"
        return 1
    fi
}

case $ENV in
    "local")
        if ! check_env_files; then
            exit 1
        fi
        echo -e "${BLUE}🏠 Switching to local development environment...${NC}"
        cp .env.local .env
        echo -e "${GREEN}✅ Environment switched to LOCAL${NC}"
        echo "Database: localhost (Docker PostgreSQL)"
        ;;
    "azure")
        if ! check_env_files; then
            exit 1
        fi
        echo -e "${BLUE}☁️ Switching to Azure production environment...${NC}"
        cp .env.azure .env
        echo -e "${GREEN}✅ Environment switched to AZURE${NC}"
        echo "Database: Azure PostgreSQL Flexible Server"
        ;;
    "build")
        build_azure_image
        exit $?
        ;;
    "deploy")
        deploy_azure_local
        exit $?
        ;;
    "setup")
        echo -e "${BLUE}🛠️ Setting up environment files...${NC}"
        
        if [ ! -f ".env.local" ]; then
            cp .env.local.template .env.local
            echo -e "${GREEN}✅ Created .env.local from template${NC}"
        else
            echo -e "${YELLOW}⚠️ .env.local already exists${NC}"
        fi
        
        if [ ! -f ".env.azure" ]; then
            cp .env.azure.template .env.azure
            echo -e "${GREEN}✅ Created .env.azure from template${NC}"
        else
            echo -e "${YELLOW}⚠️ .env.azure already exists${NC}"
        fi
        
        echo ""
        echo -e "${YELLOW}📝 Next steps:${NC}"
        echo "1. Edit .env.local with your local development values"
        echo "2. Edit .env.azure with your Azure production values"
        echo "3. Run: ./switch_env.sh local"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Invalid environment/action.${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  ./switch_env.sh setup     - Create environment files from templates"
        echo "  ./switch_env.sh local     - Switch to local development"
        echo "  ./switch_env.sh azure     - Switch to Azure environment"
        echo "  ./switch_env.sh build     - Build Docker image for Azure"
        echo "  ./switch_env.sh deploy    - Deploy Azure image locally (testing)"
        echo ""
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}Current database configuration:${NC}"
echo "DB_HOST=$(grep DB_HOST .env | cut -d'=' -f2)"
echo "DB_USER=$(grep DB_USER .env | cut -d'=' -f2)"
