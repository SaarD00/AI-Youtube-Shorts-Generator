"""
Gerador de metadados para YouTube Shorts usando Gemini AI.
Cria títulos, descrições e tags otimizados para SEO automaticamente.
"""

import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash"


def _get_client():
    """Retorna o cliente do Gemini configurado com a API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não definida. Adicione ao seu arquivo .env antes de rodar."
        )
    return genai.Client(api_key=api_key)


def _get_model():
    """Retorna o modelo do Gemini a ser utilizado."""
    return os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


def generate_metadata(video_filename, target_lang="auto"):
    """
    Gera metadados (título, descrição, tags) usando Gemini AI
    baseado no nome do arquivo de vídeo e idioma alvo.

    Args:
        video_filename: Nome do arquivo de vídeo.
        target_lang: 'auto', 'en' (Inglês/Global) ou 'pt-BR' (Português/Brasil).

    Returns:
        Dicionário com 'title', 'description', 'tags', 'language' e 'filename'.
    """
    client = _get_client()
    model = _get_model()

    topic_hint = os.path.splitext(video_filename)[0]
    topic_hint = topic_hint.replace("_", " ").replace("-", " ")

    prompt = f"""
    Você é o MELHOR especialista em viralização de YouTube Shorts do mundo.
    Sua missão: criar metadados altamente virais para o algoritmo do YouTube.

    Nome do arquivo do vídeo: "{video_filename}"
    Tópico: "{topic_hint}"
    Idioma desejado: "{target_lang}" (Se 'auto', determine se o título/descrição devem ser em Inglês ou Português com base no contexto).

    ### REGRAS PARA VIRALIZAR:

    1. **Idioma**:
       - Se for em INGLÊS: Título, Descrição e Tags em INGLÊS. Adicione `"language": "en"`.
       - Se for em PORTUGUÊS: Título, Descrição e Tags em PORTUGUÊS. Adicione `"language": "pt-BR"`.

    2. **Título** (máximo 60 caracteres):
       - Use gatilhos mentais (curiosidade, choque, surpresa) e emoji inicial forte (🤯, ⚡, 😱, 🔥, 💀, ❌).

    3. **Descrição**:
       - Cativante, com Call-to-Action e hashtags relevantes incluindo OBRIGATORIAMENTE #Shorts #Viral #FYP #ForYou.

    4. **Tags** (15-20 tags virais):
       - Focadas no idioma e público-alvo (global para Inglês, Brasil para Português).

    ### FORMATO DE SAÍDA (JSON puro, sem markdown):
    {{
        "title": "Título com emoji",
        "description": "Descrição com hashtags",
        "tags": ["tag1", "tag2", ...],
        "language": "en" ou "pt-BR"
    }}

    Responda APENAS com o JSON válido, nada mais.
    """

    print(f"🤖 Gerando metadados para '{video_filename}'...")

    # Tenta até 3 vezes em caso de JSON mal formatado
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            raw_text = response.text.strip()

            # Limpa formatação markdown se presente
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            raw_text = raw_text.strip()
            metadata = json.loads(raw_text)

            # Validação básica
            if not all(k in metadata for k in ('title', 'description', 'tags')):
                print(f"   ⚠️  JSON incompleto (tentativa {attempt + 1}/3)")
                continue

            # Garante que #Shorts está na descrição
            if "#Shorts" not in metadata['description']:
                metadata['description'] += "\n\n#Shorts"

            metadata['filename'] = video_filename
            print(f"   ✅ Título: {metadata['title']}")
            return metadata

        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON inválido (tentativa {attempt + 1}/3): {e}")
            continue
        except Exception as e:
            print(f"   ⚠️  Erro na API (tentativa {attempt + 1}/3): {e}")
            continue

    # Fallback com metadados genéricos
    print("   ⚠️  Usando metadados padrão (fallback)")
    return {
        "title": f"✨ Novo Short: {topic_hint[:50]}",
        "description": f"Assista ao nosso novo Short sobre {topic_hint}!\n\n#Shorts #facts #curiosidades",
        "tags": ["shorts", "facts", "curiosidades", "educação", "viral"],
        "filename": video_filename
    }


def generate_metadata_batch(video_dir):
    """
    Gera metadados para todos os vídeos .mp4 em um diretório.
    Salva os resultados em um arquivo JSON para revisão antes do upload.

    Args:
        video_dir: Caminho para o diretório contendo os vídeos.

    Returns:
        Lista de dicionários com metadados para cada vídeo.
    """
    if not os.path.exists(video_dir):
        print(f"❌ Diretório não encontrado: {video_dir}")
        return []

    videos = sorted([f for f in os.listdir(video_dir) if f.lower().endswith('.mp4')])

    if not videos:
        print(f"⚠️  Nenhum vídeo .mp4 encontrado em {video_dir}")
        return []

    print(f"🔍 Encontrados {len(videos)} vídeos. Iniciando geração de metadados...\n")

    metadata_list = []
    for i, video in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] Processando...")
        meta = generate_metadata(video)
        metadata_list.append(meta)
        print()

    # Salva em JSON para revisão manual antes do upload
    output_file = os.path.join(video_dir, "metadata_review.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=4)

    print(f"💾 Metadados salvos para revisão em: {output_file}")
    print(f"   📋 Você pode editar o arquivo JSON antes de rodar o upload.\n")
    return metadata_list


def load_metadata(meta_file):
    """
    Carrega metadados de um arquivo JSON previamente salvo.

    Args:
        meta_file: Caminho para o arquivo JSON.

    Returns:
        Lista de dicionários com metadados.
    """
    if not os.path.exists(meta_file):
        print(f"❌ Arquivo de metadados não encontrado: {meta_file}")
        return []

    with open(meta_file, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    print(f"📂 Metadados carregados de {meta_file} ({len(metadata_list)} entradas)")
    return metadata_list


# --- TESTE DO MÓDULO ---
if __name__ == "__main__":
    import sys

    test_dir = sys.argv[1] if len(sys.argv) > 1 else "assets/final"
    print(f"🧪 Testando geração de metadados para vídeos em: {test_dir}\n")
    results = generate_metadata_batch(test_dir)

    if results:
        print("\n📊 Resultados:")
        for meta in results:
            print(f"  🎬 {meta['filename']}")
            print(f"     Título: {meta['title']}")
            print(f"     Tags: {', '.join(meta['tags'][:5])}...")
            print()
