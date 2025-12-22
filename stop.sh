#!/bin/bash

# Script para parar o backend

set -e

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Parando SecondBrain Backend...${NC}"

# Usa docker compose (nova sintaxe) ou docker-compose (antiga)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}❌ docker-compose não encontrado${NC}"
    exit 1
fi

$DOCKER_COMPOSE down

echo -e "${GREEN}✅ Backend parado${NC}"

