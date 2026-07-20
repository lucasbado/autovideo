import asyncio
import os
import sys

# Adiciona o diretório atual ao path para importações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ideator_new as ideator
import researcher
import core
import veracity_check


async def executar_pipeline_factual(nicho_escolhido=None):
    """
    Orquestra o novo pipeline factual com suporte a nicho específico.
    """
    max_tentativas = 5
    tentativa = 0
    fatos_validados = None
    tema_escolhido = ""

    print("🚀 Iniciando Pipeline Factual...")

    while tentativa < max_tentativas:
        tentativa += 1
        print(f"\n--- Tentativa {tentativa}/{max_tentativas} ---")

        # 1. Ideação (Usa Banco de Dados de Entidades Reais para garantir qualidade)
        if nicho_escolhido:
            # Se o usuário escolheu um nicho, tentamos pegar uma entidade real desse nicho
            tema_obj = ideator.gerar_tema_da_base_por_nicho(nicho_escolhido)
            if not tema_obj:
                tema_obj = ideator.gerar_tema_factual(nicho_especifico=nicho_escolhido)
        else:
            tema_obj = ideator.gerar_tema_com_base()

        # Validação extra: se a IA retornar um título muito curto ou genérico, descarte imediatamente
        if not tema_obj or len(str(tema_obj)) < 10:
            print("⚠️ Ideator retornou tema inválido. Tentando novamente...")
            continue

        if isinstance(tema_obj, dict):
            tema_escolhido = tema_obj.get("title")
            tema_keywords = tema_obj.get("keywords", [])
        else:
            tema_escolhido = str(tema_obj)
            tema_keywords = []

        # 2. Pesquisa
        texto_bruto = researcher.pesquisar_dados_brutos(
            tema_escolhido, keywords=tema_keywords
        )

        # VALIDAÇÃO DE TEMA: Se a pesquisa retornou 0 fragmentos relevantes,
        # o tema é lixo. Descarte imediatamente.
        if len(texto_bruto) < 3:
            print(f"⚠️ Tema '{tema_escolhido}' é uma alucinação. Descartando...")
            continue

        # 3. Resumo e Validação
        # Preferir extração local (mais rápida) e só cair no LLM se necessário
        fatos_json = researcher.gerar_resumo_factual(
            texto_bruto, tema_escolhido, use_llm=False
        )
        if not fatos_json:
            print("ℹ️ Extração local insuficiente. Tentando LLM para resumo factual...")
            fatos_json = researcher.gerar_resumo_factual(
                texto_bruto, tema_escolhido, use_llm=True
            )

        if researcher.validar_densidade(fatos_json):
            fatos_validados = fatos_json
            break
        else:
            print(f"⚠️ Tema '{tema_escolhido}' descartado por falta de dados reais.")

    if not fatos_validados:
        print(
            "❌ Falha crítica: Não foi possível encontrar um tema factual válido após várias tentativas."
        )
        return

    # 4. Geração de Roteiro Grounded (Passando o nicho para o Agente Especialista)
    roteiro, termo_busca = core.gerar_roteiro_factual(fatos_validados, nicho=nicho_escolhido)

    if not roteiro:
        print("❌ Falha ao gerar roteiro factual.")
        return

    # --- AUDITORIA DE VERACIDADE ---
    aprovado, auditoria = veracity_check.verificar_veracidade_roteiro(roteiro, fatos_validados)
    if not aprovado:
        print(f"⚠️ Roteiro REPROVADO na auditoria de veracidade!")
        print(f"   Alucinações: {auditoria.get('alucinacoes')}")
        print(f"   Score: {auditoria.get('score_fidelidade')}")
        print(f"   Justificativa: {auditoria.get('justificativa')}")
        confirmacao_auditoria = input("Deseja prosseguir mesmo assim (S/N)? ")
        if confirmacao_auditoria.lower() != "s":
            print("Abortando devido a falha na veracidade.")
            return
    else:
        print(f"✅ Roteiro APROVADO na auditoria de veracidade (Score: {auditoria.get('score_fidelidade')}).")

    print(f"--- ROTEIRO GERADO ---\n{roteiro}")
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

    await core.gerar_audio(roteiro, voz=estilo["voz"])
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
        f.write(f"TEMA: {tema_escolhido}\n")
        f.write(f"ROTEIRO: {roteiro}\n")
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

    print(f"\n✅ VÍDEO CONCLUÍDO COM SUCESSO: {arquivo_resultado}")
    print(f"📌 Tema: {tema_escolhido}")


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
        return "Desenhos e Anime"
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
        perfil = input("Digite o nome do perfil (ex: MundoGamer): ")
        asyncio.run(gerenciar_login(perfil))
        return "SKIP"
    if opcao == "9":
        return input("Digite o nicho desejado (ex: Carros Antigos): ")

    return None


if __name__ == "__main__":
    nicho = menu_interativo()
    if nicho != "SKIP":
        asyncio.run(executar_pipeline_factual(nicho))
