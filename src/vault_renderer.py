import os
import re
import asyncio
from datetime import datetime
from vault_manager import get_files_by_status, read_markdown_file, update_markdown_file
import core
from styles import obter_estilo

async def renderizar_video(filepath):
    """
    Lê o roteiro do arquivo e executa a renderização completa.
    """
    metadata, body = read_markdown_file(filepath)
    title = metadata.get("tema")
    nicho = metadata.get("nicho")
    termo_busca = metadata.get("termo_busca")
    
    # Extrair o roteiro do corpo
    roteiro_match = re.search(r'## Roteiro Final\n\n(.*?)\n', body, re.DOTALL)
    if not roteiro_match:
        # Tenta pegar tudo depois do cabeçalho se o regex falhar
        if "## Roteiro Final" in body:
            roteiro_com_tags = body.split("## Roteiro Final")[-1].strip()
        else:
            print(f"❌ Roteiro não encontrado em {filepath}")
            return False
    else:
        roteiro_com_tags = roteiro_match.group(1).strip()

    if not roteiro_com_tags or len(roteiro_com_tags) < 50:
        print(f"❌ Roteiro inválido ou muito curto em {filepath}")
        return False

    print(f"\n🎬 Iniciando renderização: {title}")
    
    # 1. Preparação do Roteiro Limpo
    roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
    roteiro_limpo = re.sub(r'\s{2,}', ' ', roteiro_limpo).strip()

    # 2. Obtenção de Vídeos
    urls_video = core.obter_url_pexels(termo_busca)
    arquivos_video = await core.descarregar_videos(urls_video)

    # 3. Estilo
    estilo = obter_estilo(nicho if nicho else "default")

    # 4. Áudio e Legendas
    print("🎙️ Gerando áudio...")
    await core.gerar_audio(roteiro_limpo, voz=estilo["voz"])
    
    print("✍️ Gerando legendas...")
    segmentos = core.gerar_legendas()

    # 5. Montagem Final
    print("🎞️ Montando vídeo final...")
    arquivo_resultado = core.montar_video(segmentos, arquivos_video, estilo=estilo)

    # 6. Organização
    handle = estilo.get("handle", "@Fatos").replace("@", "")
    pasta_perfil = os.path.join("outputs", handle)
    os.makedirs(pasta_perfil, exist_ok=True)
    novo_nome = os.path.join(pasta_perfil, os.path.basename(arquivo_resultado))
    os.rename(arquivo_resultado, novo_nome)

    # 7. Atualização do Vault
    update_markdown_file(filepath, {
        "status": "rendered",
        "video_path": novo_nome,
        "data_render": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    print(f"✅ Vídeo concluído: {novo_nome}")
    return True

async def run_renderer():
    files = get_files_by_status("script_ready")
    print(f"📂 Encontrados {len(files)} arquivos aguardando renderização...")
    
    for f in files:
        try:
            await renderizar_video(f)
        except Exception as e:
            print(f"💥 Erro ao renderizar {f}: {e}")
            update_markdown_file(f, {"status": "render_failed", "error": str(e)})

if __name__ == "__main__":
    asyncio.run(run_renderer())
