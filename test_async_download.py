import os
import sys
import asyncio

# Garante que o projeto esteja no PYTHONPATH (adiciona src ao sys.path para imports internos)
project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.chdir(project_root)

import core

async def main():
    try:
        termo = "voyager cinematic"
        print(f"Buscando URLs no Pexels para: {termo} (pode usar fallback se sem chave)")
        urls = core.obter_url_pexels(termo)
        print("URLs retornadas:", urls)

        arquivos = await core.descarregar_videos(urls)
        print("Arquivos baixados:")
        for a in arquivos:
            print(a)
    except Exception as e:
        print(f"Erro no teste: {e}")

if __name__ == '__main__':
    asyncio.run(main())
