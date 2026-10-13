"""
Módulo de upload para o YouTube usando a API Data v3.
Suporta autenticação OAuth2, upload retomável e lógica de retentativa com backoff exponencial.
"""

import os
import time
import random
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# Escopos necessários para upload no YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Caminhos padrão para os arquivos de credenciais
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client_secrets.json')
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'token.pickle')

# Configurações de retry
MAX_RETRIES = 10
RETRYABLE_STATUS_CODES = [500, 502, 503, 504]
CHUNK_SIZE = 1024 * 1024  # 1MB - deve ser múltiplo de 256KB


def authenticate():
    """
    Autentica o usuário usando OAuth2 (fluxo para aplicações desktop).
    Salva o token em 'token.pickle' para reutilização.
    Retorna o cliente da API do YouTube ou None em caso de falha.
    """
    creds = None

    # Tenta carregar token salvo anteriormente
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
            print("🔐 Token carregado do cache.")
        except Exception as e:
            print(f"⚠️  Erro ao carregar token salvo: {e}")
            creds = None

    # Se não houver credenciais válidas, o usuário precisa autenticar
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Atualizando token de acesso expirado...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  Falha ao atualizar token: {e}")
                print("🔑 Será necessário autenticar novamente.")
                creds = None

        if not creds or not creds.valid:
            # Verifica se o arquivo de credenciais existe
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print("❌ Erro: Arquivo 'client_secrets.json' não encontrado!")
                print()
                print("📋 Para configurar a autenticação:")
                print("   1. Acesse https://console.cloud.google.com/")
                print("   2. Crie um novo projeto (ou use um existente)")
                print("   3. Ative a 'YouTube Data API v3'")
                print("   4. Vá em 'Credenciais' → 'Criar credenciais' → 'ID do cliente OAuth'")
                print("   5. Tipo de aplicativo: 'App para computador'")
                print("   6. Baixe o JSON e salve como 'client_secrets.json' na raiz do projeto")
                print(f"   7. Caminho esperado: {CLIENT_SECRETS_FILE}")
                return None

            print("🔑 Iniciando fluxo de autenticação OAuth2...")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            print()
            print("   📋 Acesse esta URL no navegador do seu celular/PC:")
            print(f"   {auth_url}")
            print()
            code = input("   🔑 Cole o código de autorização aqui: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials



        # Salva as credenciais para execuções futuras
        try:
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            print("✅ Token salvo com sucesso em 'token.pickle'!")
        except Exception as e:
            print(f"⚠️  Aviso: Não foi possível salvar o token: {e}")

    youtube = build('youtube', 'v3', credentials=creds)
    print("✅ Autenticado com sucesso na API do YouTube!")
    return youtube


def _resumable_upload(request, video_path):
    """
    Executa o upload retomável com backoff exponencial.
    Retenta automaticamente em caso de erros de servidor (5xx) ou rede.
    """
    response = None
    retry = 0
    filename = os.path.basename(video_path)

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"   📈 Progresso: {progress}%")
        except HttpError as e:
            status_code = e.resp.status

            if status_code in RETRYABLE_STATUS_CODES:
                retry += 1
                if retry > MAX_RETRIES:
                    print(f"   ❌ Máximo de tentativas ({MAX_RETRIES}) alcançado.")
                    raise

                sleep_time = (2 ** retry) + random.uniform(0, 1)
                print(f"   ⚠️  Erro do servidor ({status_code}). Tentando novamente em {sleep_time:.1f}s...")
                time.sleep(sleep_time)

            elif status_code == 403:
                error_reason = ""
                try:
                    import json
                    error_detail = json.loads(e.content.decode('utf-8'))
                    error_reason = error_detail.get('error', {}).get('errors', [{}])[0].get('reason', '')
                except Exception:
                    pass

                if error_reason in ('quotaExceeded', 'dailyLimitExceeded'):
                    print(f"   ❌ Cota da API excedida! ({error_reason})")
                    print("   ⏳ A cota diária reseta à meia-noite no horário do Pacífico (PST).")
                    print("   💡 Dica: Você pode solicitar aumento de cota no Google Cloud Console.")
                else:
                    print(f"   ❌ Erro de permissão (403): {e}")
                raise

            elif status_code == 404:
                print("   ⚠️  Sessão de upload expirada. Recriando...")
                # Recria o upload - o chamador deve tratar isso
                raise

            else:
                print(f"   ❌ Erro HTTP não recuperável ({status_code}): {e}")
                raise

        except (OSError, ConnectionError, ConnectionResetError) as e:
            retry += 1
            if retry > MAX_RETRIES:
                print(f"   ❌ Máximo de tentativas alcançado por falha de conexão.")
                raise

            sleep_time = (2 ** retry) + random.uniform(0, 1)
            print(f"   ⚠️  Erro de rede ({type(e).__name__}). Tentando novamente em {sleep_time:.1f}s...")
            time.sleep(sleep_time)

    return response


def upload_video(youtube, video_path, title, description, tags,
                 category_id=27, privacy='public',
                 default_language=None, default_audio_language=None):
    """
    Faz o upload de um único vídeo para o YouTube.

    Args:
        youtube: Cliente autenticado da API do YouTube.
        video_path: Caminho completo para o arquivo de vídeo.
        title: Título do vídeo.
        description: Descrição do vídeo.
        tags: Lista de tags (palavras-chave).
        category_id: ID da categoria (27 = Educação).
        privacy: 'public', 'unlisted' ou 'private'.
        default_language: Código do idioma padrão dos metadados (ex: 'en', 'pt-BR').
        default_audio_language: Código do idioma padrão do áudio (ex: 'en', 'pt-BR').

    Returns:
        Resposta da API com os dados do vídeo enviado, ou None em caso de falha.
    """
    if not os.path.exists(video_path):
        print(f"   ❌ Arquivo não encontrado: {video_path}")
        return None

    # Garante que #Shorts está na descrição para classificação como Short
    if "#Shorts" not in description:
        description = f"{description.strip()}\n\n#Shorts"

    # Tamanho do arquivo para referência
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"   📁 Arquivo: {os.path.basename(video_path)} ({file_size_mb:.1f} MB)")
    print(f"   📝 Título: {title}")
    print(f"   🔒 Privacidade: {privacy}")
    if default_language or default_audio_language:
        print(f"   🌐 Idioma direcionado: {default_language or default_audio_language}")

    snippet = {
        'title': title,
        'description': description,
        'tags': tags,
        'categoryId': str(category_id)
    }

    if default_language:
        snippet['defaultLanguage'] = default_language
    if default_audio_language:
        snippet['defaultAudioLanguage'] = default_audio_language

    body = {
        'snippet': snippet,
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(
        video_path,
        chunksize=CHUNK_SIZE,
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    print(f"   🚀 Iniciando upload...")

    try:
        response = _resumable_upload(request, video_path)
    except HttpError as e:
        if e.resp.status == 404:
            # Sessão expirou, tenta do zero
            print("   🔄 Recriando sessão de upload...")
            media = MediaFileUpload(video_path, chunksize=CHUNK_SIZE, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = _resumable_upload(request, video_path)
        else:
            raise

    if response:
        video_id = response.get('id')
        print(f"   🎉 Upload concluído! ID: {video_id}")
        print(f"   🔗 Link: https://youtu.be/{video_id}")
        return response

    return None


# --- TESTE DO MÓDULO ---
if __name__ == "__main__":
    print("🧪 Testando autenticação...")
    yt = authenticate()
    if yt:
        print("✅ Autenticação OK! Pronto para uploads.")
    else:
        print("❌ Falha na autenticação.")
