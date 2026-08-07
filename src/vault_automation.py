import asyncio
import sys
from batch_researcher import run_batch
from script_preparer import run_preparer
from vault_renderer import run_renderer
from knowledge_base_rag import sincronizar_vault
from ideator_new import gerar_tema_relacionado
from agenda_manager import criar_agenda_semanal, executar_agenda

async def menu_vault():
    while True:
        print("\n--- 🗄️ SISTEMA DE VAULT (OBSIDIAN) ---")
        print("1. Gerar Pesquisas em Lote (Batch Research)")
        print("2. Preparar Roteiros das Pesquisas Prontas (Script Prep)")
        print("3. Renderizar Vídeos Turbo (GPU + ASS)")
        print("4. Sincronizar Conhecimento (Indexar vault/knowledge)")
        print("5. Sugerir Tema Baseado no Vault (Intelligent Idea)")
        print("6. Planejar Agenda Semanal (10 temas Seg-Sex)")
        print("7. Executar Agenda Semanal (Produção em Massa)")
        print("8. Abrir Dashboard Visual (Cliente GUI)")
        print("0. Sair")
        
        opcao = input("\nEscolha uma opção: ")
        
        if opcao == "1":
            n = int(input("Quantos temas deseja pesquisar? ") or 3)
            nicho = input("Nicho específico (Enter para aleatório): ") or None
            await run_batch(n, nicho)
        
        elif opcao == "2":
            await run_preparer()
            
        elif opcao == "3":
            await run_renderer()
        
        elif opcao == "4":
            await sincronizar_vault()

        elif opcao == "5":
            tema = await gerar_tema_relacionado()
            print(f"\n💡 Tema Sugerido: {tema['title']}")
            print(f"   Entidade: {tema.get('entity')}")
            input("Pressione Enter para iniciar a pesquisa deste tema...")
            from batch_researcher import processar_tema
            await processar_tema(tema)
            
        elif opcao == "6":
            await criar_agenda_semanal()
            
        elif opcao == "7":
            await executar_agenda()

        elif opcao == "8":
            print("🎨 Abrindo interface visual...")
            import subprocess
            subprocess.Popen([sys.executable, "src/app_gui.py"])
            
        elif opcao == "0":
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    asyncio.run(menu_vault())
