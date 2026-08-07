import os
import time
import asyncio
import os
import stat
from playwright.async_api import async_playwright

# Configuração de diretórios para sessões (cookies)
SESSION_DIR = os.path.join("data", "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

def list_connected_accounts():
    """
    Retorna uma lista de nomes de perfis que possuem sessões salvas.
    """
    if not os.path.exists(SESSION_DIR):
        return []
    return [d for d in os.listdir(SESSION_DIR) if os.path.isdir(os.path.join(SESSION_DIR, d))]

def remover_conta(perfil_nome):
    """
    Remove fisicamente a pasta de sessão de uma conta com tratamento de erro agressivo.
    """
    import shutil
    import os

    def remove_readonly(func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    perfil_path = os.path.join(SESSION_DIR, perfil_nome)
    if os.path.exists(perfil_path):
        try:
            shutil.rmtree(perfil_path, onerror=remove_readonly)
            return True
        except Exception as e:
            print(f"⚠️ Erro ao remover {perfil_nome}: {e}")
            return False
    return False


def verificar_sessao(perfil_nome):
    """
    Verifica se a sessão possui dados de login reais (Cookies).
    """
    perfil_path = os.path.join(SESSION_DIR, perfil_nome)
    cookies_path = os.path.join(perfil_path, "Default", "Network", "Cookies")
    
    if os.path.exists(cookies_path):
        size_kb = os.path.getsize(cookies_path) / 1024
        # Um banco de cookies com login real costuma ter > 20KB
        if size_kb > 15:
            return "Conectado"
        return "Sessão Vazia"
    
    return "Desconectado"

async def gerenciar_login(perfil_nome):
    """
    Abre o navegador para que o usuário faça o login manualmente.
    A sessão será salva para uso futuro.
    """
    perfil_path = os.path.join(SESSION_DIR, perfil_nome)
    
    async with async_playwright() as p:
        print(f"🔓 Abrindo navegador para login no perfil: {perfil_nome}")
        print("💡 Faça o login manualmente e feche o navegador quando terminar.")
        
        # Lança o navegador com um contexto de persistência
        context = await p.chromium.launch_persistent_context(
            user_data_dir=perfil_path,
            headless=False, # Precisa ser visível para o login
            args=["--disable-blink-features=AutomationControlled"] # Tenta evitar detecção básica de bot
        )
        
        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login")
        
        # Mantém aberto até o usuário fechar manualmente ou o script ser encerrado
        # (Neste protótipo, vamos apenas esperar o navegador ser fechado pelo usuário)
        # Como o context é um context manager, ele será limpo ao sair.
        # Vamos usar um loop infinito amigável:
        try:
            while True:
                if context.browser is None or not context.browser.is_connected():
                    break
                await asyncio.sleep(1)
        except:
            pass

async def fazer_upload_tiktok(video_path, legenda, perfil_nome):
    """
    Realiza o upload de um vídeo para o TikTok usando a sessão salva.
    """
    perfil_path = os.path.join(SESSION_DIR, perfil_nome)
    
    if not os.path.exists(perfil_path):
        print(f"❌ Sessão não encontrada para '{perfil_nome}'. Execute o login primeiro.")
        return False

    async with async_playwright() as p:
        print(f"🚀 Iniciando upload para TikTok (Perfil: {perfil_nome})...")
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=perfil_path,
            headless=False, # MUDADO PARA FALSE PARA VOCÊ VER O ERRO
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = await context.new_page()
        page.set_default_timeout(60000) # Aumentado para 60 segundos
        
        try:
            # 1. Navegar para a página de upload
            print("🌐 Navegando para o TikTok...")
            await page.goto("https://www.tiktok.com/creator-center/upload?lang=pt-BR")
            
            # 2. Selecionar o arquivo de vídeo
            # O TikTok usa um iframe para o upload em algumas versões.
            # Vamos tentar o seletor mais abrangente.
            print("📁 Selecionando arquivo de vídeo...")
            # Aguarda o seletor de arquivo (pode estar dentro de um iframe)
            file_input = await page.wait_for_selector('input[type="file"]', state="attached")
            await file_input.set_input_files(video_path)
            
            # 3. Preencher a legenda (Caption)
            print("⏳ Aguardando carregamento dos campos...")
            # Aguarda a caixa de texto aparecer após o início do upload
            await page.wait_for_selector('div[contenteditable="true"]', state="visible", timeout=60000)
            
            print("✍️ Preenchendo legenda e hashtags...")
            caption_box = page.locator('div[contenteditable="true"]').first
            await caption_box.click()
            
            # Limpa e digita
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(legenda)
            
            # 4. Aguardar o botão de Publicar ficar ativo
            print("⏳ Monitorando botão de postagem...")
            # O botão pode demorar conforme o vídeo é processado
            publish_button = page.get_by_role("button", name="Publicar")
            await publish_button.wait_for(state="visible", timeout=120000) # Até 2 min para processar vídeo longo
            
            # 5. Clicar em Publicar
            # Às vezes o botão existe mas está desabilitado. Vamos esperar ele ficar clicável.
            await asyncio.sleep(5) # Delay de segurança
            await publish_button.click()
            print("✅ Botão de publicar clicado!")
            
            # Aguarda uma confirmação visual de sucesso (opcional)
            await asyncio.sleep(10)
            
            await context.close()
            return True
            
        except Exception as e:
            print(f"❌ Erro durante o upload: {e}")
            await context.close()
            return False

if __name__ == "__main__":
    # Teste de login (Execute isso uma vez por perfil)
    # asyncio.run(gerenciar_login("MundoGamer"))
    pass
