AutoVideo — Geração automática de vídeos curtos (PT-BR)

Descrição
---------
AutoVideo é um conjunto de scripts Python para gerar vídeos curtos (formato vertical) baseados em fatos e curiosidades reais. O pipeline faz: ideação de tema (LLM), pesquisa web, extração de fatos, geração de roteiro, síntese de voz, busca por vídeos de banco (Pexels), montagem com MoviePy e upload opcional ao TikTok via sessão salva.

Pré-requisitos
--------------
- Python 3.10+ (recomendado)
- ffmpeg instalado e disponível no PATH (necessário para MoviePy)
- (Opcional) GPU e instalação adequada do torch para acelerar o Whisper
- Playwright: após instalar o pacote, executar "playwright install" para baixar navegadores
- spaCy (opcional, recomendado para melhor extração): após instalar o pacote, execute: python -m spacy download en_core_web_sm

Instalação (Windows)
--------------------
1. Criar e ativar virtualenv:
   python -m venv .venv
   .venv\Scripts\activate

2. Instalar dependências:
   pip install -r requirements.txt

3. Instalar navegadores do Playwright (necessário para o uploader/login):
   playwright install

Configuração de variáveis de ambiente
-------------------------------------
- PEXELS_API_KEY: chave para usar a API do Pexels (opcional). Se não definida, o pipeline usa vídeos de fallback para testes.

Exemplo (PowerShell, sessão atual):
$env:PEXELS_API_KEY = "sua_chave_aqui"

Para tornar permanente (Windows):
setx PEXELS_API_KEY "sua_chave_aqui"

Observação: nunca comitar chaves em repositórios públicos. Use .gitignore (já incluído) e variáveis de ambiente.

Como usar — exemplos práticos
----------------------------
1) Executar o pipeline automático (fluxo único):
   python src\core.py
   - Esse script executa o fluxo de geração (ideação -> pesquisa -> roteiro -> áudio -> edição -> resultado em outputs/).

2) Executar o menu interativo (escolher nicho, gerenciar logins):
   python src\scheduler.py
   - Permite escolher nichos, gerenciar logins TikTok e rodar o pipeline por nicho.

3) Testar upload manual (verifica upload em um perfil já logado):
   python src\test_upload.py
   - Segue instruções interativas para selecionar perfil e vídeo de outputs/ para teste de postagem.

4) Gerenciar login (abrir navegador e salvar sessão TikTok):
   - A partir do menu (opção 7) ou executar:
     python -c "from src.uploader import gerenciar_login; import asyncio; asyncio.run(gerenciar_login('NomeDoPerfil'))"
   - Faça o login manualmente no navegador aberto. A sessão será salva em data\sessions\{NomeDoPerfil}.

Notas técnicas e boas práticas
-----------------------------
- ffmpeg: MoviePy precisa do ffmpeg no PATH. Verifique com: ffmpeg -version
- torch/Whisper: se usar GPU, instale a versão correta do torch (considere seguir instruções oficiais do PyTorch por CUDA).
- Playwright: após instalar, execute "playwright install" e garanta que o navegador aberto para login seja visível (scripts usam headless=False por padrão para login/upload controlado pelo usuário).
- Fonts: os estilos referenciam fonts Windows (C:\Windows\Fonts\...). Se ocorrer erro de fonte no MoviePy, ajuste o caminho ou use fonts disponíveis no sistema.

Segurança
--------
- A chave PEXELS foi removida do código e agora é lida via variável de ambiente (PEXELS_API_KEY).
- .gitignore foi criado para evitar subir ambientes virtuais, caches e arquivos gerados (outputs/, temp/, .venv/ etc.).
- Nunca comite credenciais. Considere usar um gerenciador de segredos em produção.

Soluções de problemas comuns
---------------------------
- Erro de import (torch/whisper): confirme a instalação e compatibilidade com sua plataforma (Windows vs Linux) e se há suporte CUDA para sua GPU.
- Playwright não encontra seletor: interfaces web mudam. Pode ser necessário ajustar seletores em src/uploader.py.
- Upload falha repetidamente: confira se a sessão (data/sessions/{perfil}) existe e se o usuário está logado nesse perfil manualmente.

Exemplo de saída esperada (resumida)
-----------------------------------
- Ao rodar src\core.py, você verá logs como: "🔍 Pesquisando dados reais...", "📝 Extraindo fatos...", "🎙️ A gerar locução...", "🎬 A montar o vídeo...", e no final: "🚀 Sucesso absoluto! O vídeo completo está em: outputs\video_YYYYMMDD_HHMMSS.mp4".

Contribuição e próximos passos sugeridos
--------------------------------------
- Mover configurações (por ex., caminhos, API keys) para um arquivo .env e usar python-dotenv para carregá-las (já incluído no requirements)
- Tornar downloads assíncronos (aiohttp) para acelerar a etapa de aquisição de vídeos
- Adicionar logging estruturado (módulo logging) e tipagem com mypy
- Adicionar testes unitários e CI

Contato
-------
Se quiser que eu aplique algumas melhorias automaticamente (ex: criar README traduzido, converter downloads para aiohttp, adicionar logging ou CI), escolha o que deseja e eu implemento.
