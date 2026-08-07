import os
import json
import re
import numpy as np
import faiss
import ollama
import asyncio
from datetime import datetime

# Configurações
VAULT_KNOWLEDGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault", "knowledge")
INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vault_index.faiss")
CHUNKS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vault_chunks.json")
EMBED_MODEL = "nomic-embed-text"

def chunk_text(text, filename, chunk_size=500):
    """
    Divide o texto em pedaços respeitando parágrafos e cabeçalhos.
    """
    # Remove frontmatter se existir
    text = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL)
    
    # Divide por cabeçalhos ## ou parágrafos duplos
    sections = re.split(r'\n(##\s+.*?\n|\n\n)', text)
    
    chunks = []
    current_chunk = ""
    
    for section in sections:
        if not section.strip():
            continue
            
        if len(current_chunk) + len(section) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = section
        else:
            current_chunk += "\n" + section
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    # Adiciona metadados ao chunk para o LLM saber a origem
    return [{"text": f"Fonte: {filename}\nConteúdo: {c}", "source": filename} for c in chunks]

async def get_embedding(text):
    """
    Gera o vetor de embedding usando o cliente seguro.
    """
    from ollama_client import get_embedding_safe
    return await get_embedding_safe(EMBED_MODEL, text)

async def sincronizar_vault():
    """
    Lê todos os arquivos em vault/knowledge, gera embeddings e salva o índice.
    """
    print(f"🔄 Sincronizando conhecimento do Vault ({VAULT_KNOWLEDGE_PATH})...")
    
    all_chunks = []
    
    if not os.path.exists(VAULT_KNOWLEDGE_PATH):
        print(f"⚠️ Pasta {VAULT_KNOWLEDGE_PATH} não encontrada.")
        return False

    files = []
    for root, _, filenames in os.walk(VAULT_KNOWLEDGE_PATH):
        for filename in filenames:
            if filename.endswith(".md"):
                files.append(os.path.join(root, filename))
    
    if not files:
        print("ℹ️ Nenhum arquivo .md encontrado em vault/knowledge.")
        return False

    for path in files:
        filename = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            chunks = chunk_text(content, filename)
            all_chunks.extend(chunks)
    
    print(f"📄 Processados {len(files)} arquivos. Gerados {len(all_chunks)} chunks.")
    
    embeddings = []
    valid_chunks = []
    
    for i, chunk in enumerate(all_chunks):
        print(f"   Vetorizando chunk {i+1}/{len(all_chunks)}...", end="\r")
        vector = await get_embedding(chunk["text"])
        if vector:
            embeddings.append(vector)
            valid_chunks.append(chunk)
            
    if not embeddings:
        print("\n❌ Nenhun embedding gerado.")
        return False

    # Criar índice FAISS
    dimension = len(embeddings[0])
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    # Salvar índice e chunks
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    faiss.write_index(index, INDEX_PATH)
    
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(valid_chunks, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Sincronização concluída! {len(valid_chunks)} vetores salvos em data/.")
    return True

async def buscar_conhecimento_local(query, top_k=3):
    """
    Busca os chunks mais relevantes no índice local.
    """
    if not os.path.exists(INDEX_PATH) or not os.path.exists(CHUNKS_PATH):
        return []
        
    query_vector = await get_embedding(query)
    if not query_vector:
        return []
        
    index = faiss.read_index(INDEX_PATH)
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    distances, indices = index.search(np.array([query_vector]).astype('float32'), top_k)
    
    results = []
    for i, idx in enumerate(indices[0]):
        if idx != -1 and idx < len(chunks):
            # Filtra resultados com distância muito alta (opcional)
            results.append({
                "text": chunks[idx]["text"],
                "score": float(distances[0][i]),
                "source": chunks[idx]["source"]
            })
            
    return results

if __name__ == "__main__":
    # Teste rápido
    async def _test():
        await sincronizar_vault()
        res = await buscar_conhecimento_local("O que você sabe sobre?")
        for r in res:
            print(f"\n[{r['source']}] (Score: {r['score']:.2f}):\n{r['text'][:200]}...")
            
    asyncio.run(_test())
