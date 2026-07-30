import asyncio
import os
import sys

import re
# Adiciona o diretório atual ao path para importações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ideator_new as ideator
import researcher
import core
from veracity_check import verificar_veracidade_roteiro


async def executar_pipeline_factual(nicho_escolhido=None):
    """
    Orquestra o novo pipeline factual com suporte a nicho específico.
    """
    max_tentativas = 5
    tentativa = 0
    fatos_validados = None
    tema_titulo_final = ""

    print("🚀 Iniciando Pipeline Factual...")

    while tentativa < max_tentativas:
        tentativa += 1
        print(f"\n--- Tentativa {tentativa}/{max_tentativas} ---")

        # 1. Ideação (Usa Banco de Dados de Entidades Reais para garantir qualidade)
        if nicho_escolhido:
            # Se o usuário escolheu um nicho, tentamos pegar uma entidade real desse nicho
            # Esta função agora é a principal e mais confiável.
            tema_obj = ideator.gerar_tema_da_base_por_nicho(nicho_escolhido)
            if not tema_obj:
                tema_obj = ideator.gerar_tema_factual(nicho_especifico=nicho_escolhido)
        else:
            tema_obj = ideator.gerar_tema_com_base()

        # Validação extra: se a IA retornar um título muito curto ou genérico, descarte imediatamente
        if not tema_obj or len(tema_obj.get("title", "")) < 15:
            print("⚠️ Ideator retornou tema inválido. Tentando novamente...")
            continue

        if isinstance(tema_obj, dict):
            # O 'title' é o título clickbait para o vídeo final.
            # A 'entity' ou o primeiro keyword é o termo limpo para pesquisa.
            tema_titulo_final = tema_obj.get("title")
            tema_pesquisa = tema_obj.get("entity", tema_titulo_final) # Usa 'entity' se existir, senão fallback para o título
            tema_keywords = tema_obj.get("keywords", [])
        else:
            tema_titulo_final = str(tema_obj)
            tema_pesquisa = str(tema_obj)
            tema_keywords = []

        # 2. Pesquisa
        texto_bruto = researcher.pesquisar_dados_brutos(
            tema_pesquisa, keywords=tema_keywords
        )

        # VALIDAÇÃO DE TEMA: Se a pesquisa com o título falhar, tenta apenas com a entidade
        if len(texto_bruto) < 3 and isinstance(tema_obj, dict) and tema_obj.get("entity"):
            print(f"⚠️ Tema '{tema_titulo_final}' falhou. Tentando pesquisa simplificada com a entidade: '{tema_obj.get('entity')}'")
            tema_pesquisa = tema_obj.get("entity")
            texto_bruto = researcher.pesquisar_dados_brutos(tema_pesquisa)

        if len(texto_bruto) < 3:
            print(f"⚠️ Tema '{tema_pesquisa}' não retornou resultados suficientes. Descartando...")
            continue

        # 3. Resumo e Validação
        # Preferir extração local (mais rápida) e só cair no LLM se necessário
        fatos_json = researcher.gerar_resumo_factual(
            texto_bruto, tema_pesquisa, use_llm=False
        )
        if not fatos_json:
            print("ℹ️ Extração local insuficiente. Tentando LLM para resumo factual...")
            fatos_json = researcher.gerar_resumo_factual(
                texto_bruto, tema_pesquisa, use_llm=True
            )

        if researcher.validar_densidade(fatos_json):
            fatos_validados = fatos_json
            break
        else:
            print(f"⚠️ Tema '{tema_pesquisa}' descartado por falta de dados reais.")

    if not fatos_validados:
        print(
            "❌ Falha crítica: Não foi possível encontrar um tema factual válido após várias tentativas."
        )
        return

    # 4. Geração de Roteiro Grounded (Passando o nicho para o Agente Especialista)
    roteiro_com_tags, termo_busca = core.gerar_roteiro_factual(fatos_validados, nicho=nicho_escolhido)

    if not roteiro_com_tags or len(roteiro_com_tags) < 50:
        print("❌ Falha ao gerar roteiro factual ou roteiro muito curto.")
        return

    # Limpa as tags [SCENE:...] para a narração e arquivos de texto, mantendo o original para debug.
    roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
    roteiro_limpo = re.sub(r'\s{2,}', ' ', roteiro_limpo).strip()

    # 4.5 AUDITORIA DE VERACIDADE (PASSO CRÍTICO ANTI-ALUCINAÇÃO)
    # Limpa as tags [SCENE:...] do roteiro ANTES de enviar para auditoria para evitar falsos positivos.
    roteiro_para_auditoria = roteiro_limpo
    aprovado, auditoria = verificar_veracidade_roteiro(roteiro_para_auditoria, fatos_validados)
    if not aprovado:
        print("\n" + "!"*50)
        print("🚨 AUDITORIA DETECTOU ALUCINAÇÕES. INICIANDO LOOP DE REPARO...")
        print(f"   Alucinações: {auditoria.get('alucinacoes')}")
        
        # TENTATIVA DE REPARO (SELF-HEALING)
        roteiro_com_tags, termo_busca = core.gerar_roteiro_factual(
            fatos_validados, 
            nicho=nicho_escolhido,
            alucinacoes_anteriores=auditoria.get('alucinacoes')
        )
        
        if not roteiro_com_tags:
            print("❌ Falha crítica ao gerar roteiro de reparo.")
            return

        # Re-auditoria do roteiro reparado
        roteiro_limpo = re.sub(r'\[SCENE:.*?\]', '', roteiro_com_tags, flags=re.IGNORECASE).strip()
        aprovado, auditoria = verificar_veracidade_roteiro(roteiro_limpo, fatos_validados)
        
        if not aprovado:
            print("\n" + "="*50)
            print("🚨 FALHA NO REPARO: ROTEIRO CONTINUA COM ALUCINAÇÕES!")
            print(f"   Justificativa: {auditoria.get('justificativa')}")
            print("="*50 + "\n")
            # Por segurança, vamos encerrar se o reparo também falhar.
            print("❌ Execução cancelada devido à falha persistente de veracidade.")
            return

    print("✅ Auditoria de veracidade aprovou o roteiro.")

    print("✅ Auditoria de veracidade aprovou o roteiro.")
    print(f"--- ROTEIRO GERADO (com tags para debug) ---\n{roteiro_com_tags}")
    print(f"\n[!] Por favor, revise o roteiro acima.")
    confirmacao = input("O roteiro está factual e limpo (S/N)? ")
    if confirmacao.lower() != "s":
        print("Cancelando renderização...")
        exit(1)

    # 5. Renderização (Core Original)
    print("🎬 Iniciando produção de mídia e renderização...")

    urls_video = core.obter_url_pexels(termo_busca)
    arquivos_video = await core.descarregar_videos(urls_video)

    # Obtém o estilo baseado no nicho
    from styles import obter_estilo

    estilo = obter_estilo(nicho_escolhido if nicho_escolhido else "default")

    await core.gerar_audio(roteiro_limpo, voz=estilo["voz"])
    segmentos = core.gerar_legendas()

    arquivo_resultado = core.montar_video(segmentos, arquivos_video, estilo=estilo)

    # Organizar por pasta de perfil
    handle = estilo.get("handle", "@Fatos").replace("@", "")
    pasta_perfil = os.path.join("outputs", handle)
    os.makedirs(pasta_perfil, exist_ok=True)
    novo_nome = os.path.join(pasta_perfil, os.path.basename(arquivo_resultado))
    os.rename(arquivo_resultado, novo_nome)

    # Gerar arquivo de metadados para facilitar o upload manual
    with open(novo_nome.replace(".mp4", ".txt"), "w", encoding="utf-8") as f:
        f.write(f"TEMA: {tema_titulo_final}\n")
        f.write(f"ROTEIRO: {roteiro_limpo}\n")
        f.write(f"HASHTAGS: #curiosidades #fatos #{handle}\n")

    # 6. Limpeza
    print("🧹 Limpando arquivos temporários...")
    temp_dir = "temp"
    if os.path.exists(temp_dir):
        for arq in os.listdir(temp_dir):
            caminho = os.path.join(temp_dir, arq)
            try:
                if os.path.isfile(caminho):
                    os.remove(caminho)
            except Exception as e:
                print(f"⚠️ Erro ao limpar {arq}: {e}")

    print(f"\n✅ VÍDEO CONCLUÍDO COM SUCESSO: {novo_nome}")
    print(f"📌 Tema: {tema_titulo_final}")


def menu_interativo():
    print("\n--- AUTO-VIDEO FACTUAL ---")
    print("1. Tema Aleatório (Todos os Nichos)")
    print("2. Nicho: Games")
    print("3. Nicho: Desenhos Animados / Anime")
    print("4. Nicho: Ciência e Espaço")
    print("5. Nicho: História e Mistérios")
    print("6. Nicho: Tecnologia e Inteligência Artificial")
    print("7. Nicho: True Crime e Mistérios Não Resolvidos")
    print("8. GERENCIAR LOGINS (TikTok Upload)")
    print("9. Digitar um Nicho Customizado")
    opcao = input("\nEscolha uma opção (1-9): ")

    if opcao == "1":
        return None
    if opcao == "2":
        return "Games"
    if opcao == "3":
        return "Games" # Anime/Desenhos mapeia para o Agente Games
    if opcao == "4":
        return "Ciência e Espaço"
    if opcao == "5":
        return "História e Mistérios"
    if opcao == "6":
        return "Tecnologia e Futuro"
    if opcao == "7":
        return "True Crime e Mistérios"
    if opcao == "8":
        from uploader import gerenciar_login
    if opcao == "9":
        return input("Digite o nicho desejado (ex: Carros Antigos): ")

        perfil = input("Digite o nome do perfil (ex: MundoGamer): ")
        asyncio.run(gerenciar_login(perfil))
        return "SKIP"  # Indica para não rodar o pipeline após o login
    return None


if __name__ == "__main__":
    nicho = menu_interativo()
    if nicho != "SKIP":
        asyncio.run(executar_pipeline_factual(nicho))
