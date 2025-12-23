#!/bin/bash
# ===========================================
# Stripe CLI Webhook Forwarder
# ===========================================
# Este script configura o Stripe CLI para encaminhar
# webhooks para o backend local durante desenvolvimento.
#
# Uso:
#   ./stripe-webhooks.sh           # Inicia o listener
#   ./stripe-webhooks.sh login     # Faz login no Stripe
#   ./stripe-webhooks.sh trigger   # Testa um evento de checkout

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
STRIPE_CLI="${HOME}/bin/stripe"
WEBHOOK_ENDPOINT="http://localhost:8000/api/webhooks/stripe"

# Verifica se Stripe CLI está instalado
check_stripe_cli() {
    if [ ! -f "$STRIPE_CLI" ]; then
        echo -e "${RED}❌ Stripe CLI não encontrado em $STRIPE_CLI${NC}"
        echo ""
        echo "Instale executando:"
        echo "  cd /tmp"
        echo "  curl -L https://github.com/stripe/stripe-cli/releases/download/v1.21.0/stripe_1.21.0_mac-os_arm64.tar.gz -o stripe.tar.gz"
        echo "  tar -xzf stripe.tar.gz"
        echo "  mkdir -p ~/bin && mv stripe ~/bin/"
        exit 1
    fi
}

# Login no Stripe
do_login() {
    echo -e "${BLUE}🔑 Fazendo login no Stripe...${NC}"
    echo ""
    echo -e "${YELLOW}Uma página será aberta no navegador para autenticação.${NC}"
    echo ""
    $STRIPE_CLI login
}

# Inicia o listener de webhooks
start_listener() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  🎧 Stripe Webhook Listener${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "Encaminhando webhooks para: ${BLUE}${WEBHOOK_ENDPOINT}${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANTE: Copie o 'webhook signing secret' (whsec_...)${NC}"
    echo -e "${YELLOW}    e adicione ao seu .env como STRIPE_WEBHOOK_SECRET${NC}"
    echo ""
    echo -e "${GREEN}Eventos monitorados:${NC}"
    echo "  • checkout.session.completed"
    echo "  • checkout.session.expired"
    echo ""
    echo -e "${YELLOW}Pressione Ctrl+C para parar${NC}"
    echo ""
    
    $STRIPE_CLI listen \
        --forward-to "$WEBHOOK_ENDPOINT" \
        --events checkout.session.completed,checkout.session.expired
}

# Trigger de teste para checkout
trigger_test() {
    echo -e "${BLUE}🧪 Disparando evento de teste...${NC}"
    echo ""
    
    # Checkout session completed é o mais relevante para nosso caso
    $STRIPE_CLI trigger checkout.session.completed
    
    echo ""
    echo -e "${GREEN}✅ Evento disparado! Verifique os logs do backend.${NC}"
}

# Exibe ajuda
show_help() {
    echo "Stripe CLI Webhook Forwarder para SecondBrain"
    echo ""
    echo "Uso: ./stripe-webhooks.sh [comando]"
    echo ""
    echo "Comandos:"
    echo "  (sem argumento)   Inicia o listener de webhooks"
    echo "  login             Faz login no Stripe CLI"
    echo "  trigger           Dispara um evento de teste (checkout.session.completed)"
    echo "  help              Exibe esta ajuda"
    echo ""
    echo "Fluxo recomendado:"
    echo "  1. ./stripe-webhooks.sh login    # Primeira vez"
    echo "  2. ./stripe-webhooks.sh          # Inicia listener"
    echo "  3. Copie whsec_... para .env"
    echo "  4. Reinicie o docker-compose"
    echo ""
}

# Main
check_stripe_cli

case "${1:-}" in
    login)
        do_login
        ;;
    trigger)
        trigger_test
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        start_listener
        ;;
esac

