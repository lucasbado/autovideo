# Configurações de Estilo por Nicho

ESTILOS = {
    "Astronomy and Space Exploration": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "#E0F7FA",  # Azul ciano bem claro
        "stroke_color": "#006064", # Azul escuro
        "font_size": 80,
        "posicao_y": 0.75,
        "font": "C:/Windows/Fonts/georgiab.ttf",
        "handle": "@UniversoCurioso"
    },
    "Historical Mysteries and Archaeological Finds": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "#FFF9C4",  # Amarelo pergaminho
        "stroke_color": "#5D4037", # Marrom terra
        "font_size": 75,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/timesbd.ttf",
        "handle": "@ArquivoHistorico"
    },
    "Video Games and E-sports History": {
        "voz": "pt-BR-FranciscaNeural", 
        "cor_legenda": "#00FF00",  # Verde Matrix/Retro
        "stroke_color": "black",
        "font_size": 85,
        "posicao_y": 0.65,
        "font": "C:/Windows/Fonts/ariblk.ttf",
        "handle": "@MundoGamer"
    },
    "Cartoons and Anime Facts": {
        "voz": "pt-BR-FranciscaNeural",
        "cor_legenda": "#FCE4EC",  # Rosa claro
        "stroke_color": "#880E4F", # Magenta escuro
        "font_size": 80,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/comicbd.ttf",
        "handle": "@ZonaAnime"
    },
    "default": {
        "voz": "pt-BR-AntonioNeural",
        "cor_legenda": "white",
        "stroke_color": "black",
        "font_size": 75,
        "posicao_y": 0.7,
        "font": "C:/Windows/Fonts/arialbd.ttf",
        "handle": "@FatosCuriosos"
    }
}

def obter_estilo(nicho):
    """Retorna o dicionário de estilo baseado no nicho ou o default."""
    return ESTILOS.get(nicho, ESTILOS["default"])
