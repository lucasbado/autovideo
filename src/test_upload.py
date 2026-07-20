import asyncio
import os
import sys

# Adiciona o diretório atual ao path para importações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from uploader import fazer_upload_tiktok

async def testar_upload_imediato():
    print("\n🧪 --- TESTE DE UPLOAD IMEDIATO ---")
    
    perfil = input("Digite o nome do perfil que você acabou de logar (ex: MundoGamer): ")
    
    # Procura por um vídeo disponível para teste
    pasta_perfil = os.path.join("outputs", perfil)
    if not os.path.exists(pasta_perfil):
        print(f"❌ Pasta '{pasta_perfil}' não encontrada. Gere um vídeo primeiro ou crie a pasta com um vídeo dentro.")
        return

    videos = [f for f in os.listdir(pasta_perfil) if f.endswith(".mp4")]
    
    if not videos:
        print(f"❌ Nenhum vídeo .mp4 encontrado em '{pasta_perfil}'.")
        return

    print(f"✅ Vídeos encontrados para o perfil '{perfil}':")
    for i, v in enumerate(videos):
        print(f"{i+1}. {v}")
    
    escolha = int(input("\nEscolha o número do vídeo que deseja postar AGORA para teste: ")) - 1
    video_escolhido = videos[escolha]
    video_path = os.path.join(pasta_perfil, video_escolhido)
    
    legenda = "Teste de upload automático! #tecnologia #automacao #bot"
    
    print(f"\n🚀 Iniciando upload de teste...")
    print(f"🎥 Vídeo: {video_escolhido}")
    print(f"👤 Perfil: {perfil}")
    
    # IMPORTANTE: No teste, vamos deixar o navegador VISÍVEL para você ver o que está acontecendo
    # Para isso, vou modificar temporariamente o comportamento do uploader se possível 
    # ou apenas avisar que ele vai rodar.
    
    sucesso = await fazer_upload_tiktok(video_path, legenda, perfil)
    
    if sucesso:
        print(f"\n✨ SUCESSO! O vídeo deve estar aparecendo no seu perfil em instantes.")
    else:
        print(f"\n❌ O upload falhou. Verifique as mensagens de erro acima.")

if __name__ == "__main__":
    asyncio.run(testar_upload_imediato())
