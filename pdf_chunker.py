"""
PDF Chunker - Estrae, pulisce e divide il testo da file PDF per Vector DB
"""

import re
import os
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import logging

try:
    import pypdf
except ImportError:
    try:
        import PyPDF2 as pypdf
    except ImportError:
        raise ImportError("Installa pypdf o PyPDF2: pip install pypdf")

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not TIKTOKEN_AVAILABLE:
    logger.warning("tiktoken non disponibile. Installalo con: pip install tiktoken")


class PDFChunker:
    """Classe per estrarre, pulire e dividere il testo da file PDF"""
    
    def __init__(
        self,
        chunk_size: int = 300,
        chunk_overlap: Optional[int] = None,
        chunk_overlap_percent: float = 0.1,
        min_chunk_size: int = 20,
        encoding_name: str = "cl100k_base"
    ):
        """
        Inizializza il chunker
        
        Args:
            chunk_size: Dimensione massima di ogni chunk (token)
            chunk_overlap: Numero di token di overlap tra chunk (se None, usa chunk_overlap_percent)
            chunk_overlap_percent: Percentuale di overlap (default: 0.1 = 10%)
            min_chunk_size: Dimensione minima di un chunk in token (sotto questa soglia viene scartato)
            encoding_name: Nome dell'encoding per tiktoken (default: cl100k_base per GPT-4)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap_percent = chunk_overlap_percent
        
        # Calcola l'overlap: se specificato direttamente, usa quello, altrimenti calcola dalla percentuale
        if chunk_overlap is not None:
            self.chunk_overlap = chunk_overlap
        else:
            self.chunk_overlap = int(chunk_size * chunk_overlap_percent)
        
        self.min_chunk_size = min_chunk_size
        self.encoding_name = encoding_name
        
        # Inizializza il tokenizer
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Errore nell'inizializzazione del tokenizer: {e}. Usando fallback.")
                self.encoding = None
        else:
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """
        Conta il numero di token in un testo
        
        Args:
            text: Testo da analizzare
            
        Returns:
            Numero di token
        """
        if not text:
            return 0
        
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.warning(f"Errore nel conteggio token: {e}. Usando stima approssimativa.")
                # Fallback: stima approssimativa (1 token ≈ 4 caratteri)
                return len(text) // 4
        else:
            # Fallback: stima approssimativa (1 token ≈ 4 caratteri)
            return len(text) // 4
    
    def generate_chunk_id(self, source_name: str, page_number: int, chunk_index: int) -> str:
        """
        Genera un ID univoco per il chunk
        
        Args:
            source_name: Nome del file sorgente
            page_number: Numero di pagina
            chunk_index: Indice del chunk
            
        Returns:
            ID univoco del chunk
        """
        return f"{source_name}_p{page_number}_c{chunk_index}"
    
    def generate_content_hash(self, text: str) -> str:
        """
        Genera un hash SHA256 del contenuto del chunk per deduplicazione
        
        Args:
            text: Testo del chunk
            
        Returns:
            Hash SHA256 del contenuto
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def calculate_text_stats(self, text: str) -> Dict[str, int]:
        """
        Calcola statistiche sul testo
        
        Args:
            text: Testo da analizzare
            
        Returns:
            Dizionario con statistiche (word_count, sentence_count)
        """
        word_count = len(text.split())
        sentences = self.split_into_sentences(text)
        sentence_count = len(sentences)
        
        return {
            'word_count': word_count,
            'sentence_count': sentence_count
        }
    
    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, any]]:
        """
        Estrae il testo da un file PDF
        
        Args:
            pdf_path: Percorso del file PDF
            
        Returns:
            Lista di dizionari con testo e metadati per ogni pagina
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"File PDF non trovato: {pdf_path}")
        
        logger.info(f"Estraendo testo da: {pdf_path}")
        
        pages_data = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages, start=1):
                    try:
                        text = page.extract_text()
                        pages_data.append({
                            'page_number': page_num,
                            'text': text,
                            'total_pages': total_pages
                        })
                    except Exception as e:
                        logger.warning(f"Errore nell'estrazione della pagina {page_num}: {e}")
                        continue
                
                logger.info(f"Estratte {len(pages_data)} pagine da {pdf_path}")
                
        except Exception as e:
            raise Exception(f"Errore nella lettura del PDF: {e}")
        
        return pages_data
    
    def clean_text(self, text: str) -> str:
        """
        Pulisce il testo estratto
        
        Args:
            text: Testo da pulire
            
        Returns:
            Testo pulito
        """
        if not text:
            return ""
        
        # Rimuove caratteri di controllo e caratteri non stampabili
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # Normalizza gli spazi multipli in uno solo
        text = re.sub(r' +', ' ', text)
        
        # Normalizza i newline multipli (mantiene al massimo 2 newline consecutivi)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Rimuove spazi all'inizio e alla fine di ogni riga
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Rimuove righe vuote eccessive
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Rimuove spazi all'inizio e alla fine del testo
        text = text.strip()
        
        return text
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Divide il testo in frasi
        
        Args:
            text: Testo da dividere
            
        Returns:
            Lista di frasi
        """
        # Pattern per dividere in frasi (considera punti, punti esclamativi, punti interrogativi)
        # Evita di dividere su abbreviazioni comuni
        sentence_endings = r'(?<=[.!?])\s+(?=[A-ZÀÁÈÉÌÍÒÓÙÚ])'
        sentences = re.split(sentence_endings, text)
        
        # Filtra frasi vuote
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def create_chunks(
        self,
        text: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict[str, any]]:
        """
        Divide il testo in chunk di dimensione appropriata basata su token
        
        Args:
            text: Testo da dividere
            metadata: Metadati da associare ai chunk
            
        Returns:
            Lista di chunk con metadati
        """
        if not text:
            return []
        
        chunks = []
        text = self.clean_text(text)
        
        # Conta i token del testo pulito
        total_tokens = self.count_tokens(text)
        
        # Se il testo è troppo corto, ritorna lista vuota
        if total_tokens < self.min_chunk_size:
            return []
        
        # Calcola statistiche base del testo
        text_stats = self.calculate_text_stats(text)
        # Stima del numero totale di chunk (usato per calcolare la posizione relativa)
        total_chunks_estimate = max(1, (total_tokens // self.chunk_size) + 1)
        
        # Se il testo è più corto della dimensione del chunk, ritorna un unico chunk
        if total_tokens <= self.chunk_size:
            chunk_text = text
            chunk_id = None
            content_hash = self.generate_content_hash(chunk_text)
            
            if metadata:
                source_name = metadata.get('source_name', 'unknown')
                page_number = metadata.get('page_number', 0)
                chunk_id = self.generate_chunk_id(source_name, page_number, 0)
            
                chunk_data = {
                    'text': chunk_text,
                    'chunk_id': chunk_id,
                    'content_hash': content_hash,
                    'chunk_index': 0,
                    'token_count': total_tokens,
                    'char_count': len(chunk_text),
                    'word_count': text_stats['word_count'],
                    'sentence_count': text_stats['sentence_count'],
                    'position_in_doc_percent': 0.0,  # Primo chunk = inizio documento
                    'created_at': datetime.now().isoformat()
                }
            if metadata:
                chunk_data.update(metadata)
            chunks.append(chunk_data)
            return chunks
        
        # Divide in frasi per mantenere la coerenza semantica
        sentences = self.split_into_sentences(text)
        
        current_chunk = []
        current_token_count = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            # Aggiunge 1 token per lo spazio tra le frasi
            space_tokens = 1 if current_chunk else 0
            
            # Se aggiungendo questa frase superiamo la dimensione del chunk
            if current_token_count + sentence_tokens + space_tokens > self.chunk_size and current_chunk:
                # Crea il chunk corrente
                chunk_text = ' '.join(current_chunk)
                chunk_token_count = self.count_tokens(chunk_text)
                chunk_stats = self.calculate_text_stats(chunk_text)
                content_hash = self.generate_content_hash(chunk_text)
                
                # Genera ID univoco
                chunk_id = None
                if metadata:
                    source_name = metadata.get('source_name', 'unknown')
                    page_number = metadata.get('page_number', 0)
                    chunk_id = self.generate_chunk_id(source_name, page_number, chunk_index)
                
                # Calcola posizione relativa nel documento
                position_in_doc = (chunk_index / total_chunks_estimate) * 100 if total_chunks_estimate > 0 else 0
                
                chunk_data = {
                    'text': chunk_text,
                    'chunk_id': chunk_id,
                    'content_hash': content_hash,
                    'chunk_index': chunk_index,
                    'token_count': chunk_token_count,
                    'char_count': len(chunk_text),
                    'word_count': chunk_stats['word_count'],
                    'sentence_count': chunk_stats['sentence_count'],
                    'position_in_doc_percent': round(position_in_doc, 2),
                    'created_at': datetime.now().isoformat()
                }
                if metadata:
                    chunk_data.update(metadata)
                chunks.append(chunk_data)
                
                # Gestisce l'overlap: mantiene le ultime frasi per il prossimo chunk
                if self.chunk_overlap > 0:
                    overlap_sentences = []
                    overlap_token_count = 0
                    
                    # Aggiunge frasi fino a raggiungere l'overlap desiderato
                    for s in reversed(current_chunk):
                        s_tokens = self.count_tokens(s)
                        space_tokens_overlap = 1 if overlap_sentences else 0
                        
                        if overlap_token_count + s_tokens + space_tokens_overlap <= self.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_token_count += s_tokens + space_tokens_overlap
                        else:
                            break
                    
                    current_chunk = overlap_sentences
                    current_token_count = overlap_token_count
                else:
                    current_chunk = []
                    current_token_count = 0
                
                chunk_index += 1
            
            current_chunk.append(sentence)
            current_token_count += sentence_tokens + (1 if current_chunk else 0)
        
        # Aggiunge l'ultimo chunk se non è vuoto
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk_token_count = self.count_tokens(chunk_text)
            
            if chunk_token_count >= self.min_chunk_size:
                chunk_stats = self.calculate_text_stats(chunk_text)
                content_hash = self.generate_content_hash(chunk_text)
                
                # Genera ID univoco
                chunk_id = None
                if metadata:
                    source_name = metadata.get('source_name', 'unknown')
                    page_number = metadata.get('page_number', 0)
                    chunk_id = self.generate_chunk_id(source_name, page_number, chunk_index)
                
                # Calcola posizione relativa nel documento
                position_in_doc = (chunk_index / total_chunks_estimate) * 100 if total_chunks_estimate > 0 else 0
                
                chunk_data = {
                    'text': chunk_text,
                    'chunk_id': chunk_id,
                    'content_hash': content_hash,
                    'chunk_index': chunk_index,
                    'token_count': chunk_token_count,
                    'char_count': len(chunk_text),
                    'word_count': chunk_stats['word_count'],
                    'sentence_count': chunk_stats['sentence_count'],
                    'position_in_doc_percent': round(position_in_doc, 2),
                    'created_at': datetime.now().isoformat()
                }
                if metadata:
                    chunk_data.update(metadata)
                chunks.append(chunk_data)
        
        return chunks
    
    def process_pdf(
        self,
        pdf_path: str,
        include_page_numbers: bool = True,
        save_json: Optional[str] = None
    ) -> List[Dict[str, any]]:
        """
        Processa un file PDF completo: estrae, pulisce e divide in chunk
        
        Args:
            pdf_path: Percorso del file PDF
            include_page_numbers: Se True, include il numero di pagina nei metadati
            save_json: Se specificato, salva i chunk in questo file JSON
            
        Returns:
            Lista di chunk con testo pulito e metadati
        """
        # Estrae il testo dal PDF
        pages_data = self.extract_text_from_pdf(pdf_path)
        
        all_chunks = []
        pdf_path_obj = Path(pdf_path)
        pdf_name = pdf_path_obj.stem
        
        # Ottiene informazioni sul file
        file_stats = pdf_path_obj.stat()
        file_size = file_stats.st_size
        file_modified_at = datetime.fromtimestamp(file_stats.st_mtime).isoformat()
        processing_timestamp = datetime.now().isoformat()
        
        for page_data in pages_data:
            text = page_data['text']
            if not text:
                continue
            
            # Controlla se il testo ha abbastanza token
            text_tokens = self.count_tokens(text.strip())
            if text_tokens < self.min_chunk_size:
                continue
            
            # Metadati base
            metadata = {
                'source': str(pdf_path),
                'source_name': pdf_name,
                'source_path': str(pdf_path_obj.absolute()),
                'file_name': pdf_path_obj.name,
                'file_extension': pdf_path_obj.suffix,
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'file_modified_at': file_modified_at,
                'processing_timestamp': processing_timestamp,
                'total_pages': page_data['total_pages']
            }
            
            if include_page_numbers:
                metadata['page_number'] = page_data['page_number']
            
            # Crea i chunk per questa pagina
            page_chunks = self.create_chunks(text, metadata)
            all_chunks.extend(page_chunks)
        
        # Aggiorna le posizioni relative nel documento dopo aver creato tutti i chunk
        if all_chunks:
            total_chunks = len(all_chunks)
            for idx, chunk in enumerate(all_chunks):
                chunk['position_in_doc_percent'] = round((idx / total_chunks) * 100, 2) if total_chunks > 0 else 0
        
        logger.info(f"Creati {len(all_chunks)} chunk da {pdf_path}")
        
        # Salva in JSON se richiesto
        if save_json:
            self.save_to_json(all_chunks, save_json)
        
        return all_chunks
    
    def process_multiple_pdfs(
        self,
        pdf_paths: List[str],
        include_page_numbers: bool = True
    ) -> List[Dict[str, any]]:
        """
        Processa multipli file PDF
        
        Args:
            pdf_paths: Lista di percorsi ai file PDF
            include_page_numbers: Se True, include il numero di pagina nei metadati
            
        Returns:
            Lista di chunk da tutti i PDF
        """
        all_chunks = []
        
        for pdf_path in pdf_paths:
            try:
                chunks = self.process_pdf(pdf_path, include_page_numbers)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Errore nel processare {pdf_path}: {e}")
                continue
        
        return all_chunks
    
    def save_to_json(
        self,
        chunks: List[Dict[str, any]],
        output_path: str
    ) -> str:
        """
        Salva i chunk in un file JSON
        
        Args:
            chunks: Lista di chunk da salvare
            output_path: Percorso del file JSON di output
            
        Returns:
            Percorso del file salvato
        """
        import json
        
        # Crea la directory se non esiste
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Salva i chunk in JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Chunk salvati in: {output_path}")
        return output_path


def main():
    """Esempio di utilizzo"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Chunker per file PDF')
    parser.add_argument('pdf_path', help='Percorso del file PDF da processare')
    parser.add_argument('--chunk-size', type=int, default=300, help='Dimensione chunk in token (default: 300)')
    parser.add_argument('--chunk-overlap', type=int, default=None, help='Overlap tra chunk in token (se non specificato, usa percentuale)')
    parser.add_argument('--chunk-overlap-percent', type=float, default=0.1, help='Percentuale di overlap (default: 0.1 = 10%%)')
    parser.add_argument('--encoding', type=str, default='cl100k_base', help='Encoding per tiktoken (default: cl100k_base)')
    parser.add_argument('--output', '-o', help='File di output JSON (se non specificato, usa nome PDF + _chunks.json)')
    parser.add_argument('--no-save', action='store_true', help='Non salvare automaticamente in JSON')
    
    args = parser.parse_args()
    
    # Crea il chunker
    chunker = PDFChunker(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        chunk_overlap_percent=args.chunk_overlap_percent,
        encoding_name=args.encoding
    )
    
    # Processa il PDF
    chunks = chunker.process_pdf(args.pdf_path)
    
    # Stampa statistiche
    print(f"\n{'='*60}")
    print(f"Risultati del chunking")
    print(f"{'='*60}")
    print(f"File processato: {args.pdf_path}")
    print(f"Chunk size: {args.chunk_size} token")
    print(f"Overlap: {chunker.chunk_overlap} token ({chunker.chunk_overlap_percent*100:.0f}%)")
    print(f"Numero di chunk creati: {len(chunks)}")
    if chunks:
        avg_tokens = sum(c.get('token_count', 0) for c in chunks) / len(chunks)
        avg_chars = sum(c['char_count'] for c in chunks) / len(chunks)
        print(f"Dimensione media chunk: {avg_tokens:.1f} token ({avg_chars:.0f} caratteri)")
        max_tokens = max(c.get('token_count', 0) for c in chunks)
        print(f"Token massimi in un chunk: {max_tokens}")
    print(f"{'='*60}\n")
    
    # Mostra i primi 3 chunk come esempio
    print("Esempio di chunk (primi 3):\n")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"--- Chunk {i} ---")
        print(f"Metadati: {chunk.get('source_name')}, Pagina: {chunk.get('page_number', 'N/A')}")
        print(f"Token: {chunk.get('token_count', 'N/A')}, Caratteri: {chunk['char_count']}")
        print(f"Testo (primi 200 caratteri): {chunk['text'][:200]}...")
        print()
    
    # Salva in JSON (automatico se non specificato --no-save)
    if not args.no_save:
        if args.output:
            output_path = args.output
        else:
            # Genera nome file automatico basato sul PDF
            pdf_path = Path(args.pdf_path)
            output_path = pdf_path.parent / f"{pdf_path.stem}_chunks.json"
        
        chunker.save_to_json(chunks, str(output_path))
        print(f"\n✓ Chunk salvati in: {output_path}")


if __name__ == "__main__":
    main()

