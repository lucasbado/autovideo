# Configurações de Estilo por Nicho

ESTILOS = {
    "Ciência e Espaço": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "#E0F7FA",
        "stroke_color": "#006064",
        "font_size": 80,
        "posicao_y": 0.75,
        "font": "C:/Windows/Fonts/georgiab.ttf",
        "handle": "@HorizonteCosmico",
        "perfil_padrao": "HorizonteCosmico",
        "visual_tint": [0, 255, 255], # Cyan
        "tint_opacity": 0.05
    },
    "História e Mistérios": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "#FFF9C4",
        "stroke_color": "#5D4037",
        "font_size": 75,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/timesbd.ttf",
        "handle": "@Curiosando",
        "perfil_padrao": "Curiosando",
        "visual_tint": [255, 191, 0], # Amber
        "tint_opacity": 0.08
    },
    "Games": {
        "voz": "pt-BR-FranciscaNeural", 
        "cor_legenda": "#00FF00",
        "stroke_color": "black",
        "font_size": 85,
        "posicao_y": 0.65,
        "font": "C:/Windows/Fonts/ariblk.ttf",
        "handle": "@MundoGamer",
        "perfil_padrao": "MundoGamer",
        "visual_tint": [0, 255, 0], # Green
        "tint_opacity": 0.05
    },
    "Desenhos e Anime": {
        "voz": "pt-BR-FranciscaNeural",
        "cor_legenda": "#FCE4EC",
        "stroke_color": "#880E4F",
        "font_size": 80,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/comicbd.ttf",
        "handle": "@Animania",
        "perfil_padrao": "Animania",
        "visual_tint": [255, 20, 147], # Deep Pink
        "tint_opacity": 0.05
    },
    "True Crime e Mistérios": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "#FFEBEE",
        "stroke_color": "#B71C1C",
        "font_size": 75,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/arialbd.ttf",
        "handle": "@CrimeEmFoco",
        "perfil_padrao": "CrimeEmFoco",
        "visual_tint": [255, 0, 0], # Red
        "tint_opacity": 0.1
    },
    "Tecnologia e Futuro": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "#E3F2FD",
        "stroke_color": "#0D47A1",
        "font_size": 80,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/consola.ttf",
        "handle": "@NexoDigital",
        "perfil_padrao": "NexoDigital",
        "visual_tint": [0, 191, 255], # Deep Sky Blue
        "tint_opacity": 0.05
    },
    "default": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "white",
        "stroke_color": "black",
        "font_size": 75,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/arialbd.ttf",
        "handle": "@FatosCuriosos",
        "perfil_padrao": "MundoGamer",
        "visual_tint": None,
        "tint_opacity": 0
    }
}

def obter_estilo(nicho):
    """Retorna o dicionário de estilo baseado no nicho ou o default."""
    return ESTILOS.get(nicho, ESTILOS["default"])

# --- CONFIGURAÇÕES DA CENTRAL COMMAND (UI) ---
TURBO_BLUE = "#00BFFF"
TURBO_DARK = "#0A0A0A"
TURBO_GRAY = "#1E1E1E"
TURBO_GREEN = "#00FA9A"
ACCENT_COLOR = TURBO_BLUE
BORDER_RADIUS = 12
SIDEBAR_WIDTH = 250
