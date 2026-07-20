import asyncio
import sys
import os
import json

# Adiciona src ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import researcher

async def test_case(tema, keywords=None):
    print(f"\n{'='*50}")
    print(f"TESTANDO: {tema}")
    print(f"{'='*50}")
    
    # 1. Pesquisa
    bruto = researcher.pesquisar_dados_brutos(tema, keywords=keywords)
    print(f"\nResultados brutos: {len(bruto)} fragments")
    
    # 2. Extração Local
    fatos = researcher.gerar_resumo_factual(bruto, tema, use_llm=False)
    
    if fatos:
        print("\n✅ FATOS EXTRAÍDOS (LOCAL):")
        for i, f in enumerate(fatos['fatos'], 1):
            print(f"{i}. {f['fato'][:100]}...")
            print(f"   Fontes: {f['confirmado_em']}")
    else:
        print("\n❌ NENHUM FATO CONFIRMADO (LOCAL)")
        
        # 3. Fallback LLM
        print("\nTentando LLM...")
        fatos_llm = researcher.gerar_resumo_factual(bruto, tema, use_llm=True)
        if fatos_llm:
            print("\n✅ FATOS EXTRAÍDOS (LLM):")
            for i, f in enumerate(fatos_llm['fatos'], 1):
                print(f"{i}. {f['fato'][:100]}...")
                print(f"   Fontes: {f['confirmado_em']}")
        else:
            print("\n❌ NENHUM FATO CONFIRMADO (LLM)")

if __name__ == "__main__":
    # Caso 1: Ruído de dicionário / Erro de nome
    asyncio.run(test_case("Mistery of the hidden colossus", 
                        keywords=['hidden colossus', 'mystery', 'Ps2']))
    
    # Caso 2: Fato Real (Wave Race 64)
    # asyncio.run(test_case("Wave Race 64", keywords=['Nintendo', 'physics', 'water']))
