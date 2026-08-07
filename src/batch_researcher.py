import asyncio
import os
import json
from ideator_new import gerar_tema_factual, gerar_tema_com_base, gerar_tema_da_base_por_nicho, expandir_nicho
from researcher import pesquisar_dados_brutos, gerar_resumo_factual, validar_densidade, traduzir_fatos_json
from vault_manager import create_markdown_file, update_markdown_file, save_knowledge_card

async def processar_tema(tema_obj, nicho=None):
    """
    Realiza a pesquisa de um tema e salva no vault.
    """
    title = tema_obj.get("title")
    entity = tema_obj.get("entity", title)
    keywords = tema_obj.get("keywords", [])
    
    print(f"\n🔍 Pesquisando: {title}")
    
    # Cria o arquivo no vault com status 'researching'
    tema_obj["nicho"] = nicho or tema_obj.get("nicho", "default")
    filepath = create_markdown_file(tema_obj, status="researching")
    
    try:
        # Pesquisa dados brutos (AGORA COM BLINDAGEM DE NICHO)
        bruto = await pesquisar_dados_brutos(entity, keywords=keywords, nicho=nicho)
        
        if len(bruto) < 3:
            print(f"⚠️ Poucos resultados para {entity}. Abortando.")
            update_markdown_file(filepath, {"status": "research_failed", "error": "Poucos resultados de pesquisa"})
            return None

        # Gerar resumo factual (AGORA EM INGLÊS)
        fatos_json = await gerar_resumo_factual(bruto, entity, use_llm=True)
        
        # --- PESQUISA PROFUNDA (DYNAMIC RECURSION) ---
        # Se achamos poucos fatos, ou se os fatos citam entidades novas, fazemos um segundo round
        if fatos_json and len(fatos_json.get("fatos", [])) < 4:
            print("   🔍 Poucos fatos encontrados. Iniciando Round 2 de pesquisa profunda...")
            novas_queries = [f"{entity} history details", f"{entity} technical analysis", f"{entity} secrets facts"]
            for q in novas_queries:
                bruto_extra = await pesquisar_dados_brutos(q)
                bruto.extend(bruto_extra)
            
            # Tenta extrair novamente com mais dados
            fatos_json = await gerar_resumo_factual(bruto, entity, use_llm=True)

        if fatos_json and validar_densidade(fatos_json):
            # TRADUZ PARA PORTUGUÊS (Pós-Validação)
            fatos_json = await traduzir_fatos_json(fatos_json)
            
            # SALVA CARD DE CONHECIMENTO (Memória Permanente)
            try:
                save_knowledge_card(fatos_json)
                print(f"🧠 Conhecimento arquivado em cards.")
                # EXPANDE O CONHECIMENTO (DESCOBERTA RECURSIVA)
                await expandir_nicho(entity, fatos_json)
            except Exception as e:
                print(f"⚠️ Erro ao arquivar conhecimento: {e}")

            # Salva a pesquisa no corpo do markdown de produção
            fatos_str = json.dumps(fatos_json, indent=4, ensure_ascii=False)
            body = f"# {title}\n\n## Pesquisa Factual\n```json\n{fatos_str}\n```\n\n## Roteiro Final\n(Aguardando roteiro...)\n"
            
            update_markdown_file(filepath, {"status": "research_completed"}, body)
            print(f"✅ Pesquisa concluída e salva em: {filepath}")
            return filepath
        else:
            print(f"❌ Falha na densidade factual para {entity}.")
            update_markdown_file(filepath, {"status": "research_failed", "error": "Baixa densidade factual"})
            return None
            
    except Exception as e:
        print(f"💥 Erro ao processar {entity}: {e}")
        update_markdown_file(filepath, {"status": "error", "error": str(e)})
        return None

async def run_batch(n_temas=3, nicho=None):
    print(f"🚀 Iniciando Turbo Research para {n_temas} temas (Nicho: {nicho or 'Aleatório'})...")
    
    semaphore = asyncio.Semaphore(2) # Processa 2 temas por vez para não estourar VRAM

    async def task_wrapper(i):
        async with semaphore:
            print(f"\n--- Iniciando Tema {i+1}/{n_temas} ---")
            if nicho:
                # Função síncrona
                tema_obj = gerar_tema_da_base_por_nicho(nicho)
                if not tema_obj:
                    # Função assíncrona
                    tema_obj = await gerar_tema_factual(nicho_especifico=nicho)
            else:
                # Função assíncrona
                tema_obj = await gerar_tema_com_base()
                
            if tema_obj:
                await processar_tema(tema_obj, nicho)

    tasks = [task_wrapper(i) for i in range(n_temas)]
    await asyncio.gather(*tasks)
    
    print("\n✨ Fim do processamento em lote paralelo.")

if __name__ == "__main__":
    import sys
    n = 3
    nicho = None
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    if len(sys.argv) > 2:
        nicho = sys.argv[2]
        
    asyncio.run(run_batch(n, nicho))
