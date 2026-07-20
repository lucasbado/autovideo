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
    Monitora os horários e realiza o upload dos vídeos pendentes.
    """
    print("🕒 Agendador de Postagem iniciado...")
    
    while True:
        agora = datetime.datetime.now()
        hora_atual = agora.strftime("%H:%M")
        data_atual = agora.strftime("%Y-%m-%d")
        
        if hora_atual in HORARIOS_POSTAGEM:
            print(f"⏰ Hora de postar! ({hora_atual})")
            
            log = carregar_log()
            # Verifica se já postamos hoje neste horário
            ja_postado = any(p for p in log if p['data'] == data_atual and p['hora'] == hora_atual)
            
            if not ja_postado:
                # 1. Procurar vídeos em outputs que não foram postados
                for perfil_dir in os.listdir("outputs"):
                    perfil_path = os.path.join("outputs", perfil_dir)
                    if not os.path.isdir(perfil_path):
                        continue
                    
                    # Busca arquivos .mp4
                    videos = [f for f in os.listdir(perfil_path) if f.endswith(".mp4")]
                    
                    for video in videos:
                        # Verifica se este vídeo específico já foi postado
                        foi_postado = any(p for p in log if p['video'] == video)
                        if foi_postado:
                            continue
                            
                        video_full_path = os.path.join(perfil_path, video)
                        metadata_path = video_full_path.replace(".mp4", ".txt")
                        
                        # Extrair legenda do arquivo .txt
                        legenda = "Confira essa curiosidade! #fatos #curiosidades"
                        if os.path.exists(metadata_path):
                            with open(metadata_path, "r", encoding="utf-8") as f:
                                linhas = f.readlines()
                                for linha in linhas:
                                    if linha.startswith("HASHTAGS:"):
                                        legenda = linha.replace("HASHTAGS:", "").strip()
                        
                        # 2. Realizar o upload
                        sucesso = await fazer_upload_tiktok(video_full_path, legenda, perfil_dir)
                        
                        if sucesso:
                            log.append({
                                "data": data_atual,
                                "hora": hora_atual,
                                "perfil": perfil_dir,
                                "video": video,
                                "status": "sucesso"
                            })
                            salvar_log(log)
                            print(f"✅ Vídeo '{video}' postado com sucesso no perfil '{perfil_dir}'")
                            # Espera um pouco antes do próximo perfil para não parecer spam
                            await asyncio.sleep(60) 
                            break # Posta apenas um vídeo por perfil por horário
                
            else:
                print(f"⏸️ Já postado às {hora_atual}. Aguardando próximo horário.")
        
        # Espera 1 minuto antes de checar novamente
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(agendador_de_postagem())
