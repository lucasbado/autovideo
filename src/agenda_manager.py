import os
import json
import asyncio
from datetime import datetime, timedelta
from ideator_new import gerar_tema_factual
from batch_researcher import processar_tema

AGENDA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault", "agenda")

def obter_semana_atual():
    """Calcula o ID da semana corrente."""
    hoje = datetime.now()
    # Se for domingo, a semana produtiva é a que vai começar amanhã
    if hoje.weekday() == 6:
        return obter_proxima_semana()
    
    segunda = hoje - timedelta(days=hoje.weekday())
    semana = []
    for i in range(5):
        dia = segunda + timedelta(days=i)
        semana.append(dia.strftime("%Y-%m-%d"))
    return segunda.strftime("%Y-W%W"), semana

def obter_proxima_semana():
    """Calcula as datas da próxima segunda a sexta."""
    hoje = datetime.now()
    dias_para_segunda = (7 - hoje.weekday()) % 7
    if dias_para_segunda == 0: dias_para_segunda = 7 # Próxima segunda
    
    segunda = hoje + timedelta(days=dias_para_segunda)
    semana = []
    for i in range(5):
        dia = segunda + timedelta(days=i)
        semana.append(dia.strftime("%Y-%m-%d"))
    return segunda.strftime("%Y-W%W"), semana

async def criar_agenda_semanal(nicho=None):
    """Gera 10 temas e os distribui na agenda da semana."""
    os.makedirs(AGENDA_PATH, exist_ok=True)
    id_semana, dias = obter_proxima_semana()
    filepath = os.path.join(AGENDA_PATH, f"{id_semana}.json")
    
    if os.path.exists(filepath):
        print(f"📅 Agenda para {id_semana} já existe.")
        return filepath

    print(f"🚀 Planejando produção para a semana {id_semana}...")
    agenda = {"semana": id_semana, "slots": []}
    
    for dia in dias:
        for periodo in ["Manhã", "Tarde"]:
            print(f"💡 Gerando tema para {dia} ({periodo})...")
            tema = await gerar_tema_factual(nicho_especifico=nicho)
            
            # Busca perfil padrão do nicho
            from styles import obter_estilo
            estilo = obter_estilo(tema.get("nicho", "default"))
            perfil_sugerido = estilo.get("perfil_padrao", "")

            agenda["slots"].append({
                "data": dia,
                "periodo": periodo,
                "tema": tema["title"],
                "keywords": tema["keywords"],
                "nicho": tema.get("nicho", "default"),
                "status": "planejado",
                "arquivo_vault": "",
                "perfil": perfil_sugerido,
                "horario": "12:00" if periodo == "Manhã" else "19:00"
            })
            
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(agenda, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Agenda semanal criada: {filepath}")
    return filepath

async def executar_agenda(id_semana=None):
    """Executa o pipeline completo (Pesquisa -> Roteiro -> Render) para itens pendentes."""
    from script_preparer import preparar_roteiro
    from vault_renderer import renderizar_video
    
    if not id_semana:
        id_semana, _ = obter_proxima_semana()
        
    filepath = os.path.join(AGENDA_PATH, f"{id_semana}.json")
    if not os.path.exists(filepath):
        print(f"❌ Agenda {id_semana} não encontrada.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        agenda = json.load(f)

    print(f"🏗️ Iniciando produção FULL AUTOMATION da agenda {id_semana}...")
    
    for slot in agenda["slots"]:
        # Se já está pronto, pula
        if slot["status"] == "rendered":
            continue

        # 1. Pesquisa (se status for planejado ou error)
        if slot["status"] in ["planejado", "error"]:
            print(f"\n--- [1/4] Pesquisando: {slot['tema']} ---")
            tema_obj = {
                "title": slot["tema"], 
                "keywords": slot["keywords"],
                "nicho": slot.get("nicho"),
                "perfil": slot.get("perfil")
            }
            path = await processar_tema(tema_obj, nicho=slot.get("nicho"))
            if path:
                slot["status"] = "pesquisado"
                slot["arquivo_vault"] = path
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)
            else:
                print(f"⚠️ Falha na pesquisa de {slot['tema']}")
                slot["status"] = "error"
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)
                continue

        # 2. Roteiro (se status for pesquisado)
        if slot["status"] == "pesquisado" and slot.get("arquivo_vault"):
            print(f"--- [2/4] Preparando Roteiro: {slot['tema']} ---")
            slot["status"] = "scripting" # Status intermediário para UI
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(agenda, f, indent=4, ensure_ascii=False)
            
            sucesso_script = await preparar_roteiro(slot["arquivo_vault"])
            if sucesso_script:
                slot["status"] = "script_ready"
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)
            else:
                print(f"⚠️ Falha no roteiro de {slot['tema']}")
                slot["status"] = "error"
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)
                continue

        # 3. Renderização (se status for script_ready)
        if slot["status"] == "script_ready" and slot.get("arquivo_vault"):
            print(f"--- [3/4] Renderizando Vídeo: {slot['tema']} ---")
            slot["status"] = "rendering" # Status intermediário
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(agenda, f, indent=4, ensure_ascii=False)

            sucesso_render = await renderizar_video(slot["arquivo_vault"])
            if sucesso_render:
                slot["status"] = "rendered"
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)
            else:
                print(f"⚠️ Falha na renderização de {slot['tema']}")
                slot["status"] = "error"
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)

    print(f"\n✨ Agenda {id_semana} concluída!")

if __name__ == "__main__":
    # Teste rápido
    asyncio.run(criar_agenda_semanal())
