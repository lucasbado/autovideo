import os
import sys
import asyncio

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import researcher

def main():
    tema = "Secrets behind the design of Pokémon characters"
    keywords = ["pokemon character design", "pokemon creator", "satoshi tajiri pokemon design"]
    print(f"Testando pesquisa para: {tema} with keywords={keywords}")
    bruto = researcher.pesquisar_dados_brutos(tema, keywords=keywords)
    print(f"Resultados brutos: {len(bruto)} fragments" if isinstance(bruto, list) else f"Raw text len: {len(str(bruto))}")
    fatos = researcher.gerar_resumo_factual(bruto, tema, use_llm=False)
    print("Fatos extraidos (local):")
    print(fatos)

if __name__ == '__main__':
    main()
