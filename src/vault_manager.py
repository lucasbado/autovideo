import os
import re
import json
from datetime import datetime

VAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault")
PRODUCTION_PATH = os.path.join(VAULT_PATH, "production")
KNOWLEDGE_PATH = os.path.join(VAULT_PATH, "knowledge")
CARDS_PATH = os.path.join(KNOWLEDGE_PATH, "cards")
SCRIPTS_PATH = os.path.join(KNOWLEDGE_PATH, "successful_scripts")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

def save_knowledge_card(fatos_json):
    """
    Salva uma pesquisa validada como uma nota permanente de conhecimento.
    """
    entidade = fatos_json.get("entidade", "Sem Nome")
    slug = slugify(entidade)
    filepath = os.path.join(CARDS_PATH, f"{slug}.md")
    
    os.makedirs(CARDS_PATH, exist_ok=True)
    
    # Formata fatos para o Obsidian
    fatos_markdown = ""
    for f in fatos_json.get("fatos", []):
        fatos_markdown += f"- **Fato**: {f.get('fato')}\n  - *Detalhe*: {f.get('detalhe')}\n"
    
    frontmatter = {
        "tags": ["conhecimento", "pesquisado"],
        "entidade": entidade,
        "data_pesquisa": datetime.now().strftime("%Y-%m-%d"),
        "links": [f"[[{entidade}]]"]
    }
    
    fm_str = "---\n"
    for k, v in frontmatter.items():
        fm_str += f"{k}: {json.dumps(v, ensure_ascii=False)}\n"
    fm_str += "---\n\n"
    
    content = fm_str + f"# {entidade}\n\n## Fatos Pesquisados\n{fatos_markdown}\n"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

def save_successful_script(metadata, roteiro_texto):
    """
    Salva um roteiro aprovado como exemplo de estilo.
    """
    tema = metadata.get("tema", "Sem Tema")
    slug = slugify(tema)
    filepath = os.path.join(SCRIPTS_PATH, f"{slug}.md")
    
    os.makedirs(SCRIPTS_PATH, exist_ok=True)
    
    frontmatter = {
        "tags": ["exemplo_estilo", "roteiro_sucesso"],
        "tema": tema,
        "nicho": metadata.get("nicho", "default"),
        "data_aprovacao": datetime.now().strftime("%Y-%m-%d"),
        "score_auditoria": metadata.get("auditoria_score", 1.0)
    }
    
    fm_str = "---\n"
    for k, v in frontmatter.items():
        fm_str += f"{k}: {json.dumps(v, ensure_ascii=False)}\n"
    fm_str += "---\n\n"
    
    content = fm_str + f"# Roteiro: {tema}\n\n{roteiro_texto}\n"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

def create_markdown_file(tema_obj, status="idea"):
    """
    Cria um arquivo Markdown no vault com metadados iniciais.
    """
    title = tema_obj.get("title", "Sem Título")
    slug = slugify(title)
    filename = f"{slug}.md"
    filepath = os.path.join(PRODUCTION_PATH, filename)
    
    # Se já existir, adiciona um timestamp para não sobrescrever
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%H%M%S")
        filepath = os.path.join(PRODUCTION_PATH, f"{slug}-{timestamp}.md")

    frontmatter = {
        "tema": title,
        "status": status,
        "nicho": tema_obj.get("nicho", "default"),
        "perfil": tema_obj.get("perfil", ""),
        "data_criacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "entidade": tema_obj.get("entity", ""),
        "keywords": tema_obj.get("keywords", []),
        "video_path": ""
    }
    
    fm_str = "---\n"
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_str += f"{k}: {json.dumps(v)}\n"
        else:
            fm_str += f"{k}: \"{v}\"\n"
    fm_str += "---\n\n"
    
    content = fm_str + f"# {title}\n\n## Pesquisa Factual\n(Aguardando pesquisa...)\n\n## Roteiro Final\n(Aguardando roteiro...)\n"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    return filepath

def read_markdown_file(filepath):
    """
    Lê o arquivo e separa frontmatter do conteúdo.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    
    fm_str = match.group(1)
    body = match.group(2)
    
    metadata = {}
    for line in fm_str.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"')
            # Tenta converter listas JSON
            if value.startswith("[") and value.endswith("]"):
                try:
                    value = json.loads(value)
                except:
                    pass
            metadata[key] = value
            
    return metadata, body

def update_markdown_file(filepath, metadata_updates=None, body_updates=None):
    """
    Atualiza metadados e/ou conteúdo do arquivo.
    """
    metadata, body = read_markdown_file(filepath)
    
    if metadata_updates:
        metadata.update(metadata_updates)
    
    if body_updates:
        # Se body_updates for um dict, substituímos seções específicas
        # Para simplificar agora, vamos assumir que body_updates é o novo corpo total
        # ou uma string para concatenar. Aqui vamos substituir o corpo se for string.
        if isinstance(body_updates, str):
            body = body_updates

    fm_str = "---\n"
    for k, v in metadata.items():
        if isinstance(v, list):
            fm_str += f"{k}: {json.dumps(v, ensure_ascii=False)}\n"
        else:
            fm_str += f"{k}: \"{v}\"\n"
    fm_str += "---\n\n"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(fm_str + body)

def get_files_by_status(status):
    files = []
    for f in os.listdir(PRODUCTION_PATH):
        if f.endswith(".md"):
            path = os.path.join(PRODUCTION_PATH, f)
            meta, _ = read_markdown_file(path)
            if meta.get("status") == status:
                files.append(path)
    return files

if __name__ == "__main__":
    # Teste
    test_tema = {"title": "O Segredo do PS2", "nicho": "Games", "entity": "PlayStation 2"}
    path = create_markdown_file(test_tema)
    print(f"Arquivo criado: {path}")
    update_markdown_file(path, {"status": "researching"})
    meta, _ = read_markdown_file(path)
    print(f"Novo status: {meta.get('status')}")
