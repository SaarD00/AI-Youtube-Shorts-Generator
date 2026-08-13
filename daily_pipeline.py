#!/usr/bin/env python3
"""
AutoShorts AI — Pipeline Diário de Automação Total.
1. Gerar novos vídeos com IA (IA escolhe tópicos em alta e cria roteiro, narração e edição)
2. Criar metadados virais (título, descrição e 20 tags virais com Gemini)
3. Fazer upload automático para o YouTube Shorts

Uso:
    python daily_pipeline.py --count 2          # Gerar e publicar 2 vídeos agora
    python daily_pipeline.py --generate-only    # Apenas gerar sem subir
    python daily_pipeline.py --upload-only      # Apenas subir pendentes
"""

import os
import sys
import argparse
import asyncio
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from main import main_async, parse_args as parse_main_args
from upload_scheduled import upload_batch, show_status, log


async def run_daily_pipeline(count=2, generate_only=False, upload_only=False, lang="pt-BR"):
    log("\n" + "═" * 60)
    log(f"🚀 INICIANDO PIPELINE DIÁRIO AUTÔNOMO [{lang}] — AUTOSHORTS AI")
    log("═" * 60)

    # 1. GERAÇÃO DE VÍDEOS COM IA
    if not upload_only:
        log(f"\n🎬 [ETAPA 1/3] Gerando {count} novo(s) vídeo(s) [{lang}] com IA...")
        log("   • IA selecionando tópicos em alta")
        log("   • Gerando roteiro edutainment (Gemini 3.5 Flash)")
        log(f"   • Gerando narração em {lang} (Edge-TTS)")
        log("   • Coletando vídeos HD no Pexels")
        log("   • Renderizando vídeo final com transições e avatar (FFmpeg)...")

        main_args = parse_main_args(["--runs", str(count), "--lang", lang])
        try:
            exit_code = await main_async(main_args)
            if exit_code == 0:
                log("✅ [ETAPA 1/3] Geração de vídeos concluída com sucesso!")
            else:
                log("⚠️ [ETAPA 1/3] Alguns vídeos podem não ter sido gerados completamente.")
        except Exception as e:
            log(f"❌ [ETAPA 1/3] Erro durante a geração de vídeos: {e}")
            if generate_only:
                return 1

    if generate_only:
        log("✨ Etapa de geração concluída (--generate-only ativo).")
        return 0

    # 2. UPLOAD E METADADOS VIRAIS
    log(f"\n📤 [ETAPA 2/3 & 3/3] Gerando metadados virais e enviando para o YouTube Shorts...")
    res = upload_batch(count=count)

    log("\n" + "═" * 60)
    log("🎉 PIPELINE DIÁRIO CONCLUÍDO!")
    log("═" * 60 + "\n")
    return res


def main():
    parser = argparse.ArgumentParser(description="Pipeline Diário Autônomo (Geração + Upload)")
    parser.add_argument("--count", type=int, default=2, help="Quantidade de vídeos a gerar e publicar por dia (padrão: 2)")
    parser.add_argument("--lang", choices=["pt-BR", "en"], default="pt-BR", help="Idioma dos vídeos gerados (padrão: pt-BR)")
    parser.add_argument("--generate-only", action="store_true", help="Apenas gerar vídeos, sem fazer upload")
    parser.add_argument("--upload-only", action="store_true", help="Apenas fazer upload dos vídeos pendentes")
    parser.add_argument("--status", action="store_true", help="Ver status dos vídeos e histórico")

    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    return asyncio.run(run_daily_pipeline(
        count=args.count,
        generate_only=args.generate_only,
        upload_only=args.upload_only,
        lang=args.lang
    ))


if __name__ == "__main__":
    sys.exit(main())
