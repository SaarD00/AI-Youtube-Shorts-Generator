#!/usr/bin/env python3
"""
AutoShorts AI — Upload agendado: 2 vídeos por dia.
Envia 2 vídeos, e agenda os próximos para o dia seguinte via cron.

Uso:
    python upload_scheduled.py              # Envia os próximos 2 vídeos
    python upload_scheduled.py --setup-cron  # Configura o cron automático
    python upload_scheduled.py --status      # Mostra o progresso
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime

# Adiciona o diretório do projeto ao path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from modules.uploader import authenticate, upload_video
from modules.metadata_generator import generate_metadata_batch, load_metadata

VIDEO_DIR = os.path.join(PROJECT_DIR, "assets", "final")
HISTORY_FILE = os.path.join(VIDEO_DIR, "upload_history.json")
METADATA_FILE = os.path.join(VIDEO_DIR, "metadata_review.json")
SCHEDULE_LOG = os.path.join(PROJECT_DIR, "upload_schedule.log")
VIDEOS_PER_DAY = 2
DELAY_BETWEEN_UPLOADS = 120  # 2 minutos entre cada vídeo


def log(msg):
    """Loga com timestamp no console e no arquivo de log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(SCHEDULE_LOG, 'a', encoding='utf-8') as f:
        f.write(line + "\n")


def load_history():
    """Carrega histórico de uploads."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_history(history):
    """Salva histórico atualizado."""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)


def get_pending_videos():
    """Retorna lista de vídeos ainda não enviados."""
    if not os.path.exists(VIDEO_DIR):
        return []

    all_videos = sorted([f for f in os.listdir(VIDEO_DIR) if f.lower().endswith('.mp4')])
    history = load_history()
    uploaded = [
        entry.get('filename', entry) if isinstance(entry, dict) else entry
        for entry in history
    ]
    return [v for v in all_videos if v not in uploaded]


def ensure_metadata():
    """Garante que os metadados existem, gerando se necessário."""
    if os.path.exists(METADATA_FILE):
        meta = load_metadata(METADATA_FILE)
        if meta:
            return meta

    log("🤖 Gerando metadados virais com Gemini AI...")
    meta = generate_metadata_batch(VIDEO_DIR)
    return meta


def upload_batch(count=VIDEOS_PER_DAY):
    """Envia os próximos N vídeos."""
    pending = get_pending_videos()

    if not pending:
        log("✅ Todos os vídeos já foram enviados! Nada a fazer.")
        return 0

    batch = pending[:count]
    log(f"📤 Enviando {len(batch)} de {len(pending)} vídeos pendentes...")

    # Carregar/gerar metadados
    metadata_list = ensure_metadata()

    # Autenticar
    log("🔐 Autenticando com YouTube...")
    youtube = authenticate()
    if not youtube:
        log("❌ Falha na autenticação!")
        return 1

    # Upload
    history = load_history()
    success = 0

    for i, video in enumerate(batch, 1):
        video_path = os.path.join(VIDEO_DIR, video)

        # Busca metadados do vídeo
        meta = None
        for m in metadata_list:
            if m.get('filename') == video:
                meta = m
                break

        if not meta:
            meta = {
                "title": f"🔥 {os.path.splitext(video)[0].replace('_', ' ')}",
                "description": "Segue pra mais! 🔔\n\n#Shorts #Viral #FYP #ForYou",
                "tags": ["shorts", "viral", "fyp", "foryou", "trending", "facts"]
            }

        log(f"\n{'═' * 50}")
        log(f"📤 Upload {i}/{len(batch)}: {video}")
        log(f"📝 Título: {meta.get('title')}")
        log(f"🏷️  Tags: {', '.join(meta.get('tags', [])[:8])}...")

        lang_code = meta.get('language') or 'pt-BR'
        try:
            response = upload_video(
                youtube=youtube,
                video_path=video_path,
                title=meta.get('title'),
                description=meta.get('description'),
                tags=meta.get('tags', []),
                privacy='public',
                default_language=lang_code,
                default_audio_language=lang_code
            )

            if response:
                success += 1
                history_entry = {
                    "filename": video,
                    "video_id": response.get('id'),
                    "title": meta.get('title'),
                    "url": f"https://youtu.be/{response.get('id')}",
                    "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                history.append(history_entry)
                save_history(history)
                log(f"🎉 Enviado! https://youtu.be/{response.get('id')}")

        except Exception as e:
            log(f"❌ Falha: {e}")

        # Delay entre uploads
        if i < len(batch):
            log(f"⏳ Aguardando {DELAY_BETWEEN_UPLOADS}s...")
            time.sleep(DELAY_BETWEEN_UPLOADS)

    # Resumo
    remaining = len(pending) - success
    log(f"\n{'═' * 50}")
    log(f"📊 Resultado: {success}/{len(batch)} enviados hoje")
    log(f"📦 Restantes: {remaining} vídeos")

    if remaining > 0:
        days_left = (remaining + VIDEOS_PER_DAY - 1) // VIDEOS_PER_DAY
        log(f"📅 Previsão: mais {days_left} dia(s) para completar")

    return 0 if success == len(batch) else 1


def show_status():
    """Mostra o progresso geral."""
    all_videos = sorted([f for f in os.listdir(VIDEO_DIR) if f.lower().endswith('.mp4')]) if os.path.exists(VIDEO_DIR) else []
    history = load_history()
    pending = get_pending_videos()

    print()
    print("═" * 50)
    print("  📊 STATUS DO UPLOAD AGENDADO")
    print("═" * 50)
    print(f"  Total de vídeos:    {len(all_videos)}")
    print(f"  ✅ Enviados:        {len(history)}")
    print(f"  ⏳ Pendentes:       {len(pending)}")
    print(f"  📅 Ritmo:           {VIDEOS_PER_DAY}/dia")

    if pending:
        days_left = (len(pending) + VIDEOS_PER_DAY - 1) // VIDEOS_PER_DAY
        print(f"  🏁 Conclusão em:    ~{days_left} dia(s)")

    if history:
        print(f"\n  📋 Últimos enviados:")
        for entry in history[-4:]:
            if isinstance(entry, dict):
                print(f"     • {entry.get('title', 'N/A')}")
                print(f"       {entry.get('url', 'N/A')} ({entry.get('uploaded_at', '')})")

    if pending:
        print(f"\n  ⏭️  Próximos na fila:")
        for v in pending[:VIDEOS_PER_DAY]:
            print(f"     • {v}")

    print()
    print("═" * 50)


def setup_cron():
    """Configura cron para rodar 2 vídeos por dia às 10h."""
    cron_cmd = f"0 10 * * * cd {PROJECT_DIR} && /usr/bin/python3 {PROJECT_DIR}/upload_scheduled.py >> {SCHEDULE_LOG} 2>&1"

    # Verifica se já existe
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    if 'upload_scheduled.py' in existing:
        print("⚠️  Cron já configurado! Entrada existente:")
        for line in existing.split('\n'):
            if 'upload_scheduled' in line:
                print(f"   {line}")
        return

    # Adiciona novo cron
    new_crontab = existing.rstrip() + "\n" + cron_cmd + "\n"
    process = subprocess.run(['crontab', '-'], input=new_crontab, capture_output=True, text=True)

    if process.returncode == 0:
        print("✅ Cron configurado com sucesso!")
        print(f"   📅 Rodará todo dia às 10:00")
        print(f"   📤 Enviará {VIDEOS_PER_DAY} vídeos por execução")
        print(f"   📝 Log em: {SCHEDULE_LOG}")
    else:
        print(f"❌ Erro ao configurar cron: {process.stderr}")


def main():
    parser = argparse.ArgumentParser(description="Upload agendado de YouTube Shorts (2/dia)")
    parser.add_argument("--setup-cron", action="store_true", help="Configurar cron automático (todo dia 10h)")
    parser.add_argument("--status", action="store_true", help="Mostrar progresso dos uploads")
    parser.add_argument("--count", type=int, default=VIDEOS_PER_DAY, help=f"Quantos vídeos enviar agora (padrão: {VIDEOS_PER_DAY})")

    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if args.setup_cron:
        setup_cron()
        return 0

    log("\n🎬 AutoShorts AI — Upload Agendado")
    log(f"📅 Meta: {args.count} vídeos por execução\n")
    return upload_batch(args.count)


if __name__ == "__main__":
    sys.exit(main())
