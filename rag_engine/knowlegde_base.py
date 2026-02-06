
import os
import redis
import numpy as np
import hashlib
from redis import Redis
from redis import Redis
from redis.commands.search.query import Query
from redis.commands.search.field import TextField, VectorField

from langchain.text_splitter import CharacterTextSplitter
from langchain.schema import Document
from langchain.docstore.document import Document as DocStoreDocument

#****** Esto está deprecado : from langchain.document_loaders import TextLoader
from langchain_community.document_loaders import TextLoader



import config
from openai import OpenAI

# Opciones de VectorStore y Embeddings de LangChain 
from langchain_community.vectorstores import Redis as RedisVectorStore

#****** 05-febrero: La llamada a la libreria "OpenAIEmbeddings" va a estar deprecado pronto : 
# from langchain.embeddings import OpenAIEmbeddings,
# Por lo tanto,  ha sido remplazado por langchain.community.embeddings de acuerdo a lo solicitado en la consola de terminal. 
from langchain_community.embeddings import OpenAIEmbeddings

#*****from langchain.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.embeddings import SentenceTransformerEmbeddings



#******* Esta clase maneja la creación de vectores del RAG *******************
# *** """Maneja la base de conocimiento de bancos respaldada por Redis leyendo archivos de la carpeta 'rag'."""

class KnowledgeBase:
    
    def __init__(self, api_key: str, redis_host: str, redis_port: int, redis_password: str, redis_index: str):
        self.openai_client = OpenAI(api_key=api_key)
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0, # Ajusta según tu configuración
            password=redis_password,
            decode_responses=False # Importante para manejar vectores binarios
        )
        self.redis_index = redis_index
        self.embedding_model = "text-embedding-ada-002"
        self.vector_field_name = "vector"

    def _create_index_schema(self, dims: int = 1536):
        return (
            TextField("text"),
            VectorField(
                self.vector_field_name,
                "FLAT",
                {"TYPE": "FLOAT32", "DIM": dims, "DISTANCE_METRIC": "COSINE"}
            ),
        )
    


    # def _fingerprint_key(self) -> str:
    #     return f"rag:{self.redis_index}:fingerprint"

    # def _folder_fingerprint(self, folder_path: str) -> str:
    #     h = hashlib.sha256()
    #     for name in sorted(os.listdir(folder_path)):
    #         if not name.endswith((".txt", ".md")):
    #             continue
    #         fp = os.path.join(folder_path, name)
    #         stat = os.stat(fp)
    #         h.update(name.encode("utf-8"))
    #         h.update(str(stat.st_size).encode("utf-8"))
    #         h.update(str(int(stat.st_mtime)).encode("utf-8"))
    #     return h.hexdigest()


#************* 05 -feb : se agrega paarmetro "force_rebuild" para cambiar a voluntad si queremos regenerar
#************* todos los vectores en REDIS cuando hemos cambiado los archivos de rag **************************

    def load_from_folder(self, folder_path: str = "rag", force_rebuild: bool = False):
        """Lee cada archivo .txt de la carpeta y los indexa en Redis."""
        print(f"📂 Buscando archivos en: {folder_path}")

        if not os.path.exists(folder_path):
            print(f"❌ Error: La carpeta {folder_path} no existe.")
            return
        
        
        #******************* identificacion de fingerprint de vectores en REDIS.*********************

        # current_fp = self._folder_fingerprint(folder_path)
        # saved_fp = self.redis_client.get(self._fingerprint_key())
        # saved_fp = saved_fp.decode("utf-8") if saved_fp else None
       
        
        #***********************************************************************************

        #if self.index_exists():
        #    print(f"✅ Índice '{self.redis_index}' ya existe. Saltando ingesta.")
        #    return

        #****************** Solo si toca reconstruir : force_rebuild = TRUE ) ************
        if (force_rebuild):
            print("El parámetro force_rebuild es True, se procede a recrear los vectores... ")  
            self.delete_rag_index(); 
            print(f"♻️ Rebuild solicitado. Recreando índice '{self.redis_index}'...")
            self.redis_client.ft(self.redis_index).dropindex(delete_documents=True)
        else: 
            print(f"✅ El parámetro force rebuild es FALSE, Los vectores ya existen")
            print(f" RAG ya fue hecho antes (índice existe y archivos sin cambios). Saltando ingesta de archivos !")
            return



        # 1. Recopilar todo el texto de los archivos
        all_text = ""
        files = [f for f in os.listdir(folder_path) if f.endswith((".txt",".md"))]

        if not files:
            print("⚠️ No hay archivos .txt o .md para procesar.")
            return

        for file_name in sorted(files):
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'r', encoding='utf-8') as f:
                all_text += f.read() + "\n"
            print(f"📖 Leído: {file_name}")

        # 2. Fragmentar el texto (Chunking)
        splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        docs = [Document(page_content=x) for x in splitter.split_text(all_text)]
        texts = [doc.page_content for doc in docs]

        
        # 3. Preparar el Índice en Redis, esto lo vuelve a crear  en cada ejecución
        #try:
        #    self.redis_client.ft(self.redis_index).info()
        #    print(f"⚠️ Índice '{self.redis_index}' ya existe. Recreando...")
        #    self.redis_client.ft(self.redis_index).dropindex(delete_documents=True)
        #except Exception:
        #    pass
        
        #******* PASO 3 : si existe la BD de vectores,eentonces termina la ejecucion *********
        # 3.- modificación para crear una sola vez y no volver a crear si ya existe: 
        #if self.index_exists(): 
        #    print(f" Indice'{self.redis_index}' ya existe. Saltando la ingesta de archivos para hacer RAG") 
        #    return
        #************************
        

        #********** PASO 4 *********** crear indice SOLO si éste no existe: 
        # 4.- Solo se crea RAG si no existe la base de datos cargada en Redis.
        schema = self._create_index_schema(dims=1536)
        self.redis_client.ft(self.redis_index).create_index(schema)

        # 4. Generar Embeddings y Cargar
        print(f"🧠 Generando embeddings para {len(texts)} fragmentos...")
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=texts
        )
        embeddings = [data.embedding for data in response.data]

        pipe = self.redis_client.pipeline()
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            key = f"doc:{self.redis_index}:{i}"
            vector_bytes = np.array(embedding, dtype=np.float32).tobytes()
            pipe.hset(key, mapping={"text": text, self.vector_field_name: vector_bytes})

        pipe.execute()

        #********** terminado de cargar los embeddings, se guarda el fingerprint de la Base de datos en el mismo REDIS.
        # self.redis_client.set(self._fingerprint_key(), current_fp.encode("utf-8"))
        # print("✅ Fingerprint actualizado.")
        # #**************************************************
        
        print(f"✅ Redis actualizado con éxito. {len(texts)} fragmentos indexados.")


    #*****************  El Método find_vector_in_redis () es CRUCIAL para hacer busqueda semantica usando ********
    #*****************  el modelo KNN (k-nearest neighbors) de Machine Learning                           ********
    def find_vector_in_redis(self, query: str, k: int = 3) -> str:
        # (Se mantiene igual que tu código original)
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        embedded_query = np.array(response.data[0].embedding, dtype=np.float32).tobytes()

        q = (
            Query(f'*=>[KNN {k} @{self.vector_field_name} $vec_param AS vector_score]')
            .sort_by('vector_score')
            .paging(0, k)
            .return_fields('text', 'vector_score')
            .dialect(2)
        )

        params_dict = {"vec_param": embedded_query}
        results = self.redis_client.ft(self.redis_index).search(q, query_params=params_dict)
        print(results.docs[0].vector_score)

        return "\n\n".join([doc.text for doc in results.docs])
    


    # ***** Aqui verificamos si el RAG ya fue generado en Redis **************
    # *** PASO 2 *******
    def index_exists(self) -> bool: 
        try: 
            self.redis_client.ft(self.redis.index).info()
            return True
        except Exception: 
            return False 
        

    # ******** método para borrar los vectores en Redis. ******************
    # Esto es usado cuando se debe de recrear la base de vectores 
    def delete_rag_index(self): 
        try:
            self.redis.client.ft(self.redis_index).dropindex(delete_documents=True)
            print(f" El índice RAG '{self.redis_index}' ha sido eliminado correctamente ")
        except Exception as e: 
            print(f"El índice '{self.redis_index}' no existe o ya fue eliminado anteriomente: {e}")

