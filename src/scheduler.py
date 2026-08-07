import os
import json
import asyncio
import datetime
from uploader import fazer_upload_tiktok

# Configurações de agendamento
# Por enquanto, postaremos 2 vídeos por dia em horários fixos
HORARIOS_POSTAGEM = ["12:00", "19:00"]
LOG_FILE = os.path.join("data", "post_log.json")

def carregar_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_log(log):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=4)

async def agendador_de_postagem():
    """
    Monitora a agenda semanal e realiza o upload nos horários marcados.
    """
    from agenda_manager import obter_proxima_semana, AGENDA_PATH
    print("🕒 Agendador Turbo iniciado...")
    
    while True:
        agora = datetime.datetime.now()
        hora_atual = agora.strftime("%H:%M")
        data_atual = agora.strftime("%Y-%m-%d")
        
        # 1. Busca a agenda atual
        id_semana, _ = obter_proxima_semana()
        filepath = os.path.join(AGENDA_PATH, f"{id_semana}.json")
        
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                agenda = json.load(f)
            
            for slot in agenda.get("slots", []):
                # Critérios para postar:
                # 1. Data e Hora batem
                # 2. Status é 'rendered' (ou 'script_ready' se quisermos renderizar na hora, mas melhor 'rendered')
                # 3. Tem perfil definido
                # 4. Ainda não foi postado (usamos o log para garantir)
                
                if (slot["data"] == data_atual and 
                    slot["horario"] == hora_atual and 
                    slot["status"] == "rendered" and 
                    slot["perfil"]):
                    
                    log = carregar_log()
                    ja_postado = any(p for p in log if p['video'] == slot['arquivo_vault'] and p['data'] == data_atual)
                    
                    if not ja_postado:
                        print(f"⏰ Hora de postar: {slot['tema']} no perfil {slot['perfil']}")
                        
                        # Extrai legenda
                        legenda = f"Confira essa curiosidade sobre {slot['tema']}! #fatos #curiosidades"
                        video_path = None
                        
                        # No sistema novo, podemos buscar o markdown para pegar a legenda real
                        if os.path.exists(slot["arquivo_vault"]):
                            from vault_manager import read_markdown_file
                            meta, _ = read_markdown_file(slot["arquivo_vault"])
                            video_path = meta.get("video_path")
                        
                        if video_path and os.path.exists(video_path):
                            sucesso = await fazer_upload_tiktok(video_path, legenda, slot["perfil"])
                            if sucesso:
                                log.append({
                                    "data": data_atual,
                                    "hora": hora_atual,
                                    "perfil": slot["perfil"],
                                    "video": slot["arquivo_vault"],
                                    "status": "sucesso"
                                })
                                salvar_log(log)
                                print(f"✅ Postagem concluída!")
                        else:
                            print(f"⚠️ Vídeo não encontrado para {slot['tema']}: {video_path}")

        # Espera 1 minuto
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(agendador_de_postagem())
