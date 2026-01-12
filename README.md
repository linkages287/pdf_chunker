# PDF Chunker per Vector DB

Sistema di chunking per file PDF che estrae, pulisce e prepara il testo per l'inserimento in un Vector Database.

## Caratteristiche

- ✅ Estrazione testo da file PDF
- ✅ Pulizia automatica del testo (rimozione caratteri speciali, normalizzazione spazi)
- ✅ **Chunking basato su token** (non caratteri o parole) - max 300 token per default
- ✅ Divisione intelligente in chunk con overlap
- ✅ Mantenimento dei metadati (numero pagina, nome file, conteggio token, ecc.)
- ✅ Supporto per multipli PDF
- ✅ Pronto per l'uso con Vector DB

## Installazione

```bash
pip install -r requirements.txt
```

## Utilizzo

### Come script da riga di comando

```bash
# Salva automaticamente in JSON (nome file: documento_chunks.json)
python pdf_chunker.py path/to/file.pdf

# Specifica un nome file personalizzato
python pdf_chunker.py path/to/file.pdf --output chunks.json

# Con opzioni personalizzate
python pdf_chunker.py path/to/file.pdf --chunk-size 300 --chunk-overlap-percent 0.1 --output chunks.json

# Oppure specifica l'overlap direttamente in token
python pdf_chunker.py path/to/file.pdf --chunk-size 300 --chunk-overlap 30 --output chunks.json

# Non salvare in JSON (solo stampa a schermo)
python pdf_chunker.py path/to/file.pdf --no-save
```

### Come modulo Python

```python
from pdf_chunker import PDFChunker

# Crea il chunker con parametri personalizzati
chunker = PDFChunker(
    chunk_size=300,              # Dimensione massima chunk (token) - default: 300
    chunk_overlap_percent=0.1,   # Overlap del 10% (default: 0.1 = 10%)
    min_chunk_size=20,           # Dimensione minima chunk (token) - default: 20
    encoding_name="cl100k_base"  # Encoding per tiktoken (default: cl100k_base per GPT-4)
)

# Oppure specifica l'overlap direttamente in token
chunker = PDFChunker(
    chunk_size=300,
    chunk_overlap=30,  # 30 token di overlap (10% di 300)
    min_chunk_size=20
)

# Processa un singolo PDF
chunks = chunker.process_pdf("documento.pdf")

# Processa e salva automaticamente in JSON
chunks = chunker.process_pdf("documento.pdf", save_json="chunks.json")

# Oppure salva manualmente dopo il processing
chunks = chunker.process_pdf("documento.pdf")
chunker.save_to_json(chunks, "chunks.json")

# Ogni chunk contiene metadati completi:
# - 'text': testo pulito
# - 'chunk_id': ID univoco del chunk (es: "documento_p1_c0")
# - 'content_hash': hash SHA256 del contenuto (per deduplicazione)
# - 'chunk_index': indice del chunk nella pagina
# - 'token_count': numero di token (importante per Vector DB)
# - 'char_count': numero di caratteri
# - 'word_count': numero di parole
# - 'sentence_count': numero di frasi
# - 'position_in_doc_percent': posizione relativa nel documento (0-100%)
# - 'created_at': timestamp di creazione (ISO format)
# - 'source': percorso del file
# - 'source_name': nome del file (senza estensione)
# - 'source_path': percorso assoluto del file
# - 'file_name': nome completo del file
# - 'file_extension': estensione del file (.pdf)
# - 'file_size_bytes': dimensione file in bytes
# - 'file_size_mb': dimensione file in MB
# - 'file_modified_at': data di modifica del file (ISO format)
# - 'processing_timestamp': timestamp di processamento (ISO format)
# - 'page_number': numero di pagina
# - 'total_pages': numero totale di pagine

# Processa multipli PDF
chunks = chunker.process_multiple_pdfs([
    "documento1.pdf",
    "documento2.pdf"
])

# I chunk sono pronti per essere inseriti nel Vector DB
for chunk in chunks:
    # Usa chunk['text'] per l'embedding
    # Usa chunk per i metadati
    pass
```

## Parametri di configurazione

- **chunk_size**: Dimensione massima di ogni chunk in **token** (default: 300)
- **chunk_overlap_percent**: Percentuale di overlap tra chunk consecutivi (default: 0.1 = **10%**)
- **chunk_overlap**: Numero di **token** di overlap (se specificato, sovrascrive la percentuale)
- **min_chunk_size**: Dimensione minima di un chunk in **token**, sotto questa soglia viene scartato (default: 20)
- **encoding_name**: Encoding per tiktoken (default: "cl100k_base" per GPT-4). Altri encoding comuni: "gpt2", "p50k_base", "r50k_base"

**Nota**: L'overlap è calcolato automaticamente come **10% del chunk_size** (es: 300 token → 30 token di overlap). Puoi specificare un valore fisso con `chunk_overlap` o cambiare la percentuale con `chunk_overlap_percent`.

## Formato output

Ogni chunk è un dizionario con la seguente struttura:

```python
{
    'text': 'Testo pulito del chunk...',
    'chunk_id': 'documento_p1_c0',  # ID univoco
    'content_hash': 'a1b2c3d4...',  # Hash per deduplicazione
    'chunk_index': 0,
    'token_count': 287,  # Numero di token (importante!)
    'char_count': 856,
    'word_count': 142,
    'sentence_count': 8,
    'position_in_doc_percent': 5.2,  # Posizione nel documento
    'created_at': '2024-01-15T10:30:00',
    'source': '/path/to/documento.pdf',
    'source_name': 'documento',
    'source_path': '/absolute/path/to/documento.pdf',
    'file_name': 'documento.pdf',
    'file_extension': '.pdf',
    'file_size_bytes': 1048576,
    'file_size_mb': 1.0,
    'file_modified_at': '2024-01-10T08:00:00',
    'processing_timestamp': '2024-01-15T10:30:00',
    'page_number': 1,
    'total_pages': 10
}
```

## Integrazione con Vector DB

I chunk prodotti sono pronti per essere utilizzati con Vector DB come:

- **Pinecone**
- **Weaviate**
- **Chroma**
- **Qdrant**
- **Milvus**

Esempio di integrazione:

```python
from pdf_chunker import PDFChunker
import your_vector_db_client

chunker = PDFChunker()
chunks = chunker.process_pdf("documento.pdf")

# Inserisci nel Vector DB
for chunk in chunks:
    vector_db_client.upsert(
        id=chunk['chunk_id'],  # Usa l'ID univoco generato
        vector=embed(chunk['text']),  # Genera embedding
        metadata={
            'text': chunk['text'],
            'source': chunk['source'],
            'source_name': chunk['source_name'],
            'page': chunk.get('page_number'),
            'chunk_index': chunk['chunk_index'],
            'token_count': chunk['token_count'],
            'content_hash': chunk['content_hash'],  # Per deduplicazione
            'position_in_doc': chunk['position_in_doc_percent'],
            'file_size_mb': chunk['file_size_mb'],
            'created_at': chunk['created_at']
        }
    )
```

## Salvataggio JSON

I risultati vengono **salvati automaticamente in JSON** quando si usa lo script da riga di comando. Il file JSON contiene tutti i chunk con i loro metadati completi.

**Formato del file JSON:**
```json
[
  {
    "text": "Testo del chunk...",
    "chunk_index": 0,
    "token_count": 287,
    "char_count": 856,
    "source": "/path/to/documento.pdf",
    "source_name": "documento",
    "page_number": 1,
    "total_pages": 10
  },
  ...
]
```

## Note

- **Il chunking è basato su token, non su caratteri o parole** - questo è fondamentale per i modelli LLM
- Il conteggio token usa `tiktoken` con encoding `cl100k_base` (compatibile con GPT-4)
- Se `tiktoken` non è disponibile, viene usata una stima approssimativa (1 token ≈ 4 caratteri)
- Il testo viene automaticamente pulito da caratteri non stampabili e spazi eccessivi
- La divisione in chunk avviene preferibilmente a livello di frase per mantenere la coerenza semantica
- I metadati includono informazioni utili per il retrieval e la citazione delle fonti
- Ogni chunk rispetta il limite massimo di token specificato (default: 300)
- **I risultati vengono salvati automaticamente in JSON** (nome file: `nomepdf_chunks.json`)
- **Overlap automatico del 10%** tra chunk consecutivi per mantenere il contesto
- **Metadati completi** per ogni chunk:
  - ID univoco e hash del contenuto per deduplicazione
  - Statistiche del testo (parole, frasi, token)
  - Posizione relativa nel documento
  - Informazioni complete sul file sorgente
  - Timestamp di creazione e processamento

# pdf_chunker
