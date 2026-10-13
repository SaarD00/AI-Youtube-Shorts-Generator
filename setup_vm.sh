#!/bin/bash
# AutoShorts AI — Script de Instalação Automática para VM (Linode / VPS Linux)

set -e

echo "════════════════════════════════════════════════════════════"
echo "🚀 Instalando AutoShorts AI na sua VM Linux..."
echo "════════════════════════════════════════════════════════════"

# 1. Instalar dependências do sistema (FFmpeg, Python, Cron)
echo "📦 1. Instalando pacotes do sistema (FFmpeg, Python, Cron)..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg cron git

# 2. Criar e ativar ambiente virtual
echo "🐍 2. Configurando ambiente virtual Python..."
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependências do Python
echo "📚 3. Instalando dependências (google-genai, edge-tts, youtube-api)..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Verificar FFmpeg
echo "🎬 4. Testando FFmpeg..."
ffmpeg -version | head -n 1

# 5. Configurar Cron Job (24/7 rodando às 10:00 AM)
echo "⏰ 5. Configurando Agendador 24/7 (Cron) para rodar todo dia às 10:00 AM..."
SCRIPT_DIR="$(pwd)"
CRON_CMD="0 10 * * * cd $SCRIPT_DIR && $SCRIPT_DIR/venv/bin/python daily_pipeline.py >> $SCRIPT_DIR/daily.log 2>&1"

# Adicionar ao crontab sem duplicar
(crontab -l 2>/dev/null | grep -v "daily_pipeline.py" ; echo "$CRON_CMD") | crontab -

# Ativar serviço do cron se não estiver rodando
sudo systemctl enable cron 2>/dev/null || true
sudo systemctl start cron 2>/dev/null || true

echo "════════════════════════════════════════════════════════════"
echo "✅ INSTALAÇÃO CONCLUÍDA COM SUCESSO!"
echo "════════════════════════════════════════════════════════════"
echo "   • Diretorio: $SCRIPT_DIR"
echo "   • Cron 24/7: Rodará diariamente às 10:00 AM"
echo "   • Log de Execução: $SCRIPT_DIR/daily.log"
echo ""
echo "   💡 Dica: Certifique-se de copiar os arquivos de credenciais:"
echo "      - .env"
echo "      - client_secrets.json"
echo "      - token.pickle"
echo "════════════════════════════════════════════════════════════"
