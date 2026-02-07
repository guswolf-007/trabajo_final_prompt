
#import os

#***** archivo de configuración para agente de Bancos en Chile ***************

# --- OpenAI Configuration ---

import os

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

REDIS_HOST = os.getenv("REDIS_HOST", "")
REDIS_PORT = int(os.getenv("REDIS_PORT", "12419"))
REDIS_INDEX = os.getenv("REDIS_INDEX", "grupo_13")
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# secreto: nunca hardcodear
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")



