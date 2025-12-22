#!/bin/bash

# Script para iniciar o backend com docker-compose

set -e

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Iniciando SecondBrain Backend com Docker Compose${NC}"
echo ""

# Verifica se docker-compose está instalado
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não está instalado${NC}"
    exit 1
fi

# Usa docker compose (nova sintaxe) ou docker-compose (antiga)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}❌ docker-compose não encontrado${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Verificando imagens...${NC}"
$DOCKER_COMPOSE build

echo ""
echo -e "${YELLOW}🚀 Iniciando serviços...${NC}"
$DOCKER_COMPOSE up -d

echo ""
echo -e "${GREEN}✅ Backend iniciado!${NC}"
echo ""
echo -e "${BLUE}📊 Status dos serviços:${NC}"
$DOCKER_COMPOSE ps

echo ""
echo -e "${GREEN}🌐 API disponível em:${NC}"
echo -e "   ${BLUE}http://localhost:8000${NC}"
echo -e "   ${BLUE}http://0.0.0.0:8000${NC}"
echo ""
echo -e "${YELLOW}📝 Logs:${NC}"
echo "   Para ver os logs: $DOCKER_COMPOSE logs -f api"
echo ""
echo -e "${YELLOW}🛑 Para parar:${NC}"
echo "   $DOCKER_COMPOSE down"
echo ""

# Aguarda um pouco e verifica saúde
echo -e "${YELLOW}🔍 Verificando saúde da API...${NC}"
sleep 3

if curl -s --connect-timeout 3 --max-time 5 "http://localhost:8000/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API está respondendo!${NC}"
else
    echo -e "${YELLOW}⚠️  API ainda não está respondendo (pode levar alguns segundos)${NC}"
    echo -e "${YELLOW}   Verifique os logs: $DOCKER_COMPOSE logs -f api${NC}"
fi

