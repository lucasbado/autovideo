import asyncio
import sys
from batch_researcher import run_batch
from script_preparer import run_preparer
from vault_renderer import run_renderer

async def menu_vault():
    while True:
        print("\n--- 🗄️ SISTEMA DE VAULT (OBSIDIAN) ---")
        print("1. Gerar Pesquisas em Lote (Batch Research)")
        print("2. Preparar Roteiros das Pesquisas Prontas (Script Prep)")
        print("3. Renderizar Vídeos dos Roteiros Prontos (Render Batch)")
        print("4. Executar Fluxo Completo (Apenas 1 tema para teste)")
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
            print("\n🚀 Executando fluxo completo para 1 tema...")
            await run_batch(1)
            await run_preparer()
            await run_renderer()
            
        elif opcao == "0":
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    asyncio.run(menu_vault())
