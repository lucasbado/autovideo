import os
import json
import re
import asyncio
from vault_manager import get_files_by_status, read_markdown_file, update_markdown_file, save_successful_script
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
    try:
        roteiro_com_tags, termo_busca = await gerar_roteiro_factual(fatos_json, nicho=nicho)
    except Exception as e:
        print(f"💥 Erro fatal ao chamar gerar_roteiro_factual: {e}")
        update_markdown_file(filepath, {"status": "script_failed", "error": f"Erro na função de roteiro: {e}"})
        return False
    
    if not roteiro_com_tags or not termo_busca:
        print(f"❌ Gerador retornou roteiro nulo para {title}")
        update_markdown_file(filepath, {"status": "script_failed", "error": "Falha na geração do roteiro (retorno nulo)"})
        return False

    # Limpeza para auditoria
    roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
    roteiro_limpo = re.sub(r'\s{2,}', ' ', roteiro_limpo).strip()
    
    # Auditoria
    aprovado, auditoria = await verificar_veracidade_roteiro(roteiro_limpo, fatos_json)
    
    if not aprovado:
        print(f"⚠️ Alucinações detectadas em {title}. Tentando reparo Turbo (Modo Relaxado)...")
        try:
            roteiro_com_tags, termo_busca = await gerar_roteiro_factual(
                fatos_json, 
                nicho=nicho,
                alucinacoes_anteriores=auditoria.get('alucinacoes')
            )
        except Exception as e:
            print(f"💥 Erro fatal no reparo: {e}")
            update_markdown_file(filepath, {"status": "script_failed", "error": f"Erro no reparo: {e}"})
            return False
            
        if not roteiro_com_tags or not termo_busca:
            print(f"❌ Falha no reparo do roteiro para {title}")
            update_markdown_file(filepath, {"status": "script_failed", "error": "Falha no reparo do roteiro (retorno nulo)"})
            return False

        roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
        # SEGUNDA AUDITORIA EM MODO RELAXADO
        aprovado, auditoria = await verificar_veracidade_roteiro(roteiro_limpo, fatos_json, modo_relaxado=True)
        
        if not aprovado:
            print(f"❌ Falha persistente na auditoria para {title}")
            update_markdown_file(filepath, {"status": "script_failed", "error": "Alucinações persistentes", "auditoria": auditoria})
            return False
        else:
            print(f"✅ Reparo aprovado em modo relaxado para {title}.")

    # Sucesso! Atualiza o arquivo
    metadados_update = {
        "status": "script_ready",
        "visual_search_terms": termo_busca,
        "auditoria_score": auditoria.get("score_fidelidade", 1.0)
    }
    
    # SALVA ROTEIRO COMO EXEMPLO (Memória de Estilo)
    try:
        save_successful_script(metadados_update | {"tema": title, "nicho": nicho}, roteiro_com_tags)
        print(f"🧠 Roteiro arquivado como exemplo de estilo.")
    except Exception as e:
        print(f"⚠️ Erro ao arquivar roteiro: {e}")

    # Injeta o roteiro no corpo do markdown, preservando a pesquisa
    novo_corpo = body.split("## Roteiro Final")[0] + f"## Roteiro Final\n\n{roteiro_com_tags}\n"
    
    update_markdown_file(filepath, metadados_update, novo_corpo)
    print(f"✅ Roteiro pronto e salvo em: {filepath}")
    return True

async def run_preparer():
    # Agora buscamos tanto os concluídos na pesquisa quanto os que falharam no roteiro anteriormente (para retry)
    files = get_files_by_status("research_completed") + get_files_by_status("script_failed")
    
    if not files:
        print("ℹ️ Nenhum arquivo aguardando roteiro.")
        return

    print(f"🚀 Iniciando Turbo Script Prep para {len(files)} arquivos...")
    
    semaphore = asyncio.Semaphore(2)

    async def task_wrapper(f):
        async with semaphore:
            await preparar_roteiro(f)

    tasks = [task_wrapper(f) for f in files]
    await asyncio.gather(*tasks)
    
    print("\n✨ Fim da preparação de roteiros paralela.")

if __name__ == "__main__":
    asyncio.run(run_preparer())
