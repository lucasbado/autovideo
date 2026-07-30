import asyncio
import os
import json
from ideator_new import gerar_tema_factual, gerar_tema_com_base, gerar_tema_da_base_por_nicho
from researcher import pesquisar_dados_brutos, gerar_resumo_factual, validar_densidade
from vault_manager import create_markdown_file, update_markdown_file

async def processar_tema(tema_obj, nicho=None):
    """
    Realiza a pesquisa de um tema e salva no vault.
    """
    title = tema_obj.get("title")
    entity = tema_obj.get("entity", title)
    keywords = tema_obj.get("keywords", [])
    
    print(f"\n🔍 Pesquisando: {title}")
    
    # Cria o arquivo no vault com status 'researching'
    tema_obj["nicho"] = nicho or "default"
    filepath = create_markdown_file(tema_obj, status="researching")
    
    try:
        # Pesquisa dados brutos
        bruto = pesquisar_dados_brutos(entity, keywords=keywords)
        
        if len(bruto) < 3:
            print(f"⚠️ Poucos resultados para {entity}. Abortando.")
            update_markdown_file(filepath, {"status": "research_failed", "error": "Poucos resultados de pesquisa"})
            return None

        # Gerar resumo factual
        fatos_json = gerar_resumo_factual(bruto, entity, use_llm=True)
        
        if fatos_json and validar_densidade(fatos_json):
            # Salva a pesquisa no corpo do markdown
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
    print(f"🚀 Iniciando pesquisa em lote para {n_temas} temas (Nicho: {nicho or 'Aleatório'})...")
    
    for i in range(n_temas):
        print(f"\n--- Tema {i+1}/{n_temas} ---")
        if nicho:
            tema_obj = gerar_tema_da_base_por_nicho(nicho)
            if not tema_obj:
                tema_obj = gerar_tema_factual(nicho_especifico=nicho)
        else:
            tema_obj = gerar_tema_com_base()
            
        if tema_obj:
            await processar_tema(tema_obj, nicho)
        
    print("\n✨ Fim do processamento em lote.")

if __name__ == "__main__":
    import sys
    n = 3
    nicho = None
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    if len(sys.argv) > 2:
        nicho = sys.argv[2]
        
    asyncio.run(run_batch(n, nicho))
