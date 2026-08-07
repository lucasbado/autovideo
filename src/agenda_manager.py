import os
import json
import asyncio
from datetime import datetime, timedelta
from ideator_new import gerar_tema_factual
from batch_researcher import processar_tema

AGENDA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault", "agenda")

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
            agenda["slots"].append({
                "data": dia,
                "periodo": periodo,
                "tema": tema["title"],
                "keywords": tema["keywords"],
                "status": "planejado",
                "arquivo_vault": ""
            })
            
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(agenda, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Agenda semanal criada: {filepath}")
    return filepath

async def executar_agenda(id_semana=None):
    """Executa a pesquisa de todos os itens pendentes na agenda."""
    if not id_semana:
        id_semana, _ = obter_proxima_semana()
        
    filepath = os.path.join(AGENDA_PATH, f"{id_semana}.json")
    if not os.path.exists(filepath):
        print(f"❌ Agenda {id_semana} não encontrada.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        agenda = json.load(f)

    print(f"🏗️ Iniciando produção em massa da agenda {id_semana}...")
    
    for slot in agenda["slots"]:
        if slot["status"] == "planejado":
            print(f"\n--- Processando: {slot['tema']} ---")
            tema_obj = {"title": slot["tema"], "keywords": slot["keywords"]}
            path = await processar_tema(tema_obj)
            if path:
                slot["status"] = "pesquisado"
                slot["arquivo_vault"] = path
                # Salva progresso a cada item
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(agenda, f, indent=4, ensure_ascii=False)
                    
    print(f"✨ Agenda {id_semana} concluída!")

if __name__ == "__main__":
    # Teste rápido
    asyncio.run(criar_agenda_semanal())
