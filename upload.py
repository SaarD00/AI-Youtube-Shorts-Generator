#!/usr/bin/env python3
"""
AutoShorts AI — Upload em lote para o YouTube.
Envia vídeos da pasta assets/final/ com metadados gerados por IA.

Uso:
    python upload.py --generate-meta --privacy unlisted
    python upload.py --meta-file assets/final/metadata_review.json
    python upload.py --dry-run --generate-meta
"""

import os
import sys
import json
import time
import argparse

from modules.uploader import authenticate, upload_video
from modules.metadata_generator import generate_metadata_batch, load_metadata


# Arquivo para rastrear vídeos já enviados (evita duplicatas)
HISTORY_FILENAME = "upload_history.json"


def _load_history(history_file):
    """Carrega o histórico de uploads anteriores."""
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_history(history_file, history):
    """Salva o histórico de uploads atualizado."""
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)


def _find_videos(video_dir):
    """Encontra todos os arquivos .mp4 no diretório."""
    if not os.path.exists(video_dir):
        return []
    return sorted([f for f in os.listdir(video_dir) if f.lower().endswith('.mp4')])


def _get_default_metadata(filename):
    """Gera metadados padrão caso não sejam fornecidos."""
    name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
    return {
        "filename": filename,
        "title": f"✨ {name}",
        "description": f"Assista ao nosso novo Short!\n\n#Shorts #facts #curiosidades",
        "tags": ["shorts", "facts", "curiosidades", "educação"]
    }


def _find_meta_for_video(metadata_list, filename):
    """Encontra os metadados correspondentes a um arquivo de vídeo."""
    for meta in metadata_list:
        if meta.get('filename') == filename:
            return meta
    return None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="AutoShorts AI — Upload em lote de YouTube Shorts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Gerar metadados com IA e fazer upload
  python upload.py --generate-meta

  # Simular o que seria enviado (sem enviar de fato)
  python upload.py --dry-run --generate-meta

  # Usar metadados de um arquivo JSON editado manualmente
  python upload.py --meta-file assets/final/metadata_review.json

  # Upload como não listado com delay menor
  python upload.py --generate-meta --privacy unlisted --delay 60

  # Apenas gerar metadados (sem upload)
  python upload.py --generate-meta --meta-only
        """
    )

    parser.add_argument(
        "--dir", default="assets/final/",
        help="Diretório contendo os vídeos .mp4 (padrão: assets/final/)"
    )
    parser.add_argument(
        "--privacy", default="public",
        choices=["public", "unlisted", "private"],
        help="Nível de privacidade dos vídeos (padrão: public)"
    )
    parser.add_argument(
        "--generate-meta", action="store_true",
        help="Gerar título, descrição e tags automaticamente com Gemini AI"
    )
    parser.add_argument(
        "--meta-file",
        help="Caminho para arquivo JSON com metadados pré-gerados"
    )
    parser.add_argument(
        "--meta-only", action="store_true",
        help="Apenas gerar metadados (sem fazer upload)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Mostrar o que seria enviado sem realmente fazer upload"
    )
    parser.add_argument(
        "--delay", type=int, default=300,
        help="Segundos entre uploads para evitar limites de taxa (padrão: 300)"
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Pular confirmação e enviar diretamente"
    )
    parser.add_argument(
        "--reset-history", action="store_true",
        help="Limpar o histórico de uploads (permite reenviar vídeos)"
    )

    return parser.parse_args(argv)


def main():
    args = parse_args()

    print()
    print("═" * 60)
    print("  🎬 AutoShorts AI — YouTube Shorts Uploader")
    print("═" * 60)
    print()

    video_dir = args.dir

    # 1. Verificar diretório de vídeos
    if not os.path.exists(video_dir):
        print(f"❌ Diretório não encontrado: {video_dir}")
        print(f"   💡 Crie a pasta e coloque seus vídeos .mp4 dentro.")
        return 1

    all_videos = _find_videos(video_dir)
    if not all_videos:
        print(f"⚠️  Nenhum vídeo .mp4 encontrado em {video_dir}")
        return 1

    print(f"🔍 Encontrados {len(all_videos)} vídeos em '{video_dir}':")
    for v in all_videos:
        size_mb = os.path.getsize(os.path.join(video_dir, v)) / (1024 * 1024)
        print(f"   • {v} ({size_mb:.1f} MB)")
    print()

    # 2. Gerenciar histórico de uploads
    history_file = os.path.join(video_dir, HISTORY_FILENAME)

    if args.reset_history:
        if os.path.exists(history_file):
            os.remove(history_file)
            print("🗑️  Histórico de uploads limpo!")
        else:
            print("ℹ️  Nenhum histórico para limpar.")

    history = _load_history(history_file)
    uploaded_files = [entry.get('filename', entry) if isinstance(entry, dict) else entry
                      for entry in history]

    videos_to_process = [v for v in all_videos if v not in uploaded_files]

    if not videos_to_process:
        print("✅ Todos os vídeos já foram enviados anteriormente!")
        print(f"   💡 Use --reset-history para limpar o histórico e reenviar.")
        return 0

    if len(videos_to_process) < len(all_videos):
        skipped = len(all_videos) - len(videos_to_process)
        print(f"⏭️  Pulando {skipped} vídeo(s) já enviado(s) anteriormente.")
        print()

    # 3. Gerar ou carregar metadados
    metadata_list = []

    if args.meta_file:
        metadata_list = load_metadata(args.meta_file)
        if not metadata_list:
            print("❌ Nenhum metadado carregado. Verifique o arquivo.")
            return 1
    elif args.generate_meta:
        print("🤖 Gerando metadados com Gemini AI...\n")
        metadata_list = generate_metadata_batch(video_dir)
        if not metadata_list:
            print("❌ Falha ao gerar metadados.")
            return 1

        if args.meta_only:
            print("✅ Metadados gerados! Arquivo salvo para revisão.")
            print(f"   📋 Edite o arquivo e depois rode:")
            print(f"   python upload.py --meta-file {os.path.join(video_dir, 'metadata_review.json')}")
            return 0
    else:
        # Metadados padrão
        print("ℹ️  Usando metadados padrão (use --generate-meta para IA).")
        metadata_list = [_get_default_metadata(v) for v in videos_to_process]

    # 4. Mostrar resumo
    print()
    print("─" * 60)
    print("  📋 RESUMO DO UPLOAD")
    print("─" * 60)
    print(f"  Vídeos a enviar: {len(videos_to_process)}")
    print(f"  Privacidade:     {args.privacy}")
    print(f"  Delay entre:     {args.delay}s")
    print()

    for v in videos_to_process:
        meta = _find_meta_for_video(metadata_list, v) or _get_default_metadata(v)
        print(f"  🎬 {v}")
        print(f"     📝 {meta.get('title', 'Sem título')}")
        tags_preview = ', '.join(meta.get('tags', [])[:5])
        if len(meta.get('tags', [])) > 5:
            tags_preview += "..."
        print(f"     🏷️  {tags_preview}")
        print()

    print("─" * 60)

    # 5. Modo dry-run
    if args.dry_run:
        print("\n🧪 DRY RUN — Nenhum vídeo foi enviado.")
        print("   Remova --dry-run para fazer o upload de verdade.")
        return 0

    # 6. Autenticar com YouTube
    print("\n🔐 Autenticando com a API do YouTube...")
    youtube = authenticate()
    if not youtube:
        print("❌ Falha na autenticação. Saindo.")
        return 1

    # 7. Confirmação
    if not args.yes:
        print()
        confirm = input("🤔 Deseja prosseguir com o upload? (s/N): ").strip().lower()
        if confirm not in ('s', 'sim', 'y', 'yes'):
            print("🛑 Operação cancelada pelo usuário.")
            return 0

    # 8. Upload em lote
    print(f"\n🚀 Iniciando upload de {len(videos_to_process)} vídeo(s)...\n")

    success_count = 0
    failed = []

    for i, video in enumerate(videos_to_process, 1):
        video_path = os.path.join(video_dir, video)
        meta = _find_meta_for_video(metadata_list, video) or _get_default_metadata(video)

        print(f"{'═' * 60}")
        print(f"  📤 UPLOAD {i}/{len(videos_to_process)}: {video}")
        print(f"{'═' * 60}")

        lang_code = meta.get('language') or 'pt-BR'
        try:
            response = upload_video(
                youtube=youtube,
                video_path=video_path,
                title=meta.get('title'),
                description=meta.get('description'),
                tags=meta.get('tags', []),
                privacy=args.privacy,
                default_language=lang_code,
                default_audio_language=lang_code
            )

            if response:
                success_count += 1

                # Salva no histórico imediatamente (em caso de crash)
                history_entry = {
                    "filename": video,
                    "video_id": response.get('id'),
                    "title": meta.get('title'),
                    "url": f"https://youtu.be/{response.get('id')}",
                    "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                history.append(history_entry)
                _save_history(history_file, history)
            else:
                failed.append(video)

        except Exception as e:
            print(f"   ❌ Falha ao enviar {video}: {e}")
            failed.append(video)

        # Delay entre uploads (exceto no último)
        if i < len(videos_to_process):
            print(f"\n⏳ Aguardando {args.delay} segundos antes do próximo envio...")
            print(f"   (Ctrl+C para cancelar)\n")
            try:
                time.sleep(args.delay)
            except KeyboardInterrupt:
                print("\n\n🛑 Upload interrompido pelo usuário.")
                break

    # 9. Resumo final
    print()
    print("═" * 60)
    print("  📊 RESUMO FINAL")
    print("═" * 60)
    print(f"  ✅ Enviados com sucesso: {success_count}/{len(videos_to_process)}")

    if failed:
        print(f"  ❌ Falhas: {len(failed)}")
        for f_name in failed:
            print(f"     • {f_name}")

    # Mostra links dos vídeos enviados
    recent = [e for e in history if isinstance(e, dict) and e.get('url')]
    if recent:
        print()
        print("  🔗 Links dos vídeos enviados:")
        for entry in recent[-len(videos_to_process):]:
            if isinstance(entry, dict):
                print(f"     • {entry.get('title', 'N/A')}")
                print(f"       {entry.get('url', 'N/A')}")

    print()
    print("═" * 60)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
