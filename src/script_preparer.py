import os
import json
import re
import asyncio
from vault_manager import get_files_by_status, read_markdown_file, update_markdown_file
from core import gerar_roteiro_factual
from veracity_check import verificar_veracidade_roteiro

async def preparar_roteiro(filepath):
    """
    Lê a pesquisa do arquivo, gera o roteiro, audita e salva.
    """
    metadata, body = read_markdown_file(filepath)
    title = metadata.get("tema")
    nicho = metadata.get("nicho")
    
    # Extrair fatos do JSON no corpo do markdown
    json_match = re.search(r'```json\n(.*?)\n```', body, re.DOTALL)
    if not json_match:
        print(f"❌ Não encontrei JSON de pesquisa em {filepath}")
        update_markdown_file(filepath, {"status": "error", "error": "JSON de pesquisa não encontrado no corpo"})
        return False
        
    try:
        fatos_json = json.loads(json_match.group(1))
    except Exception as e:
        print(f"❌ Erro ao decodificar JSON em {filepath}: {e}")
        update_markdown_file(filepath, {"status": "error", "error": f"Erro no JSON: {e}"})
        return False

    print(f"\n🎬 Gerando roteiro para: {title}")
    
    # Geração Inicial
    roteiro_com_tags, termo_busca = gerar_roteiro_factual(fatos_json, nicho=nicho)
    
    if not roteiro_com_tags:
        update_markdown_file(filepath, {"status": "script_failed", "error": "Falha na geração do roteiro"})
        return False

    # Limpeza para auditoria
    roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
    roteiro_limpo = re.sub(r'\s{2,}', ' ', roteiro_limpo).strip()
    
    # Auditoria
    aprovado, auditoria = verificar_veracidade_roteiro(roteiro_limpo, fatos_json)
    
    if not aprovado:
        print(f"⚠️ Alucinações detectadas. Tentando reparo...")
        roteiro_com_tags, termo_busca = gerar_roteiro_factual(
            fatos_json, 
            nicho=nicho,
            alucinacoes_anteriores=auditoria.get('alucinacoes')
        )
        
        if not roteiro_com_tags:
            update_markdown_file(filepath, {"status": "script_failed", "error": "Falha no reparo do roteiro"})
            return False

        roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
        aprovado, auditoria = verificar_veracidade_roteiro(roteiro_limpo, fatos_json)
        
        if not aprovado:
            print(f"❌ Falha persistente na auditoria para {title}")
            update_markdown_file(filepath, {"status": "script_failed", "error": "Alucinações persistentes", "auditoria": auditoria})
            return False

    # Sucesso! Atualiza o arquivo
    metadados_update = {
        "status": "script_ready",
        "termo_busca": termo_busca,
        "auditoria_score": auditoria.get("score_fidelidade", 1.0)
    }
    
    # Injeta o roteiro no corpo do markdown, preservando a pesquisa
    novo_corpo = body.split("## Roteiro Final")[0] + f"## Roteiro Final\n\n{roteiro_com_tags}\n"
    
    update_markdown_file(filepath, metadados_update, novo_corpo)
    print(f"✅ Roteiro pronto e salvo em: {filepath}")
    return True

async def run_preparer():
    files = get_files_by_status("research_completed")
    print(f"📂 Encontrados {len(files)} arquivos aguardando roteiro...")
    
    for f in files:
        await preparar_roteiro(f)
    
    print("\n✨ Fim da preparação de roteiros.")

if __name__ == "__main__":
    asyncio.run(run_preparer())
