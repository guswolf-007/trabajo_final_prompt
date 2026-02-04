
import os

#***** archivo de configuración para agente de Bancos en Chile ***************

# --- OpenAI Configuration ---

#Esta es la api key personal: 
OPENAI_API_KEY = os.getenv("OPEN_API_KEY").strip()
OPENAI_MODEL = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-ada-002" 

# --- Redis Configuration ---
# Redis del grupo 13 : 
#redis_host = "redis-15094.c282.east-us-mz.azure.cloud.redislabs.com"
#redis_port = 15094
#redis_password = "jJftzSZ0CeyNBUEDEemJwc1C8pOPOFBR"
#redis_index = "grupo_13"
#redis_username = "default"
#redis_db = 0


# ************* Redis database del grupo 09 ***************************

#redis_host = "redis-10429.c56.east-us.azure.cloud.redislabs.com"
#redis_port = 10429
#redis_username = "default"
#redis_password = "ib29eo12rc1QBSBfBJihvtYjEn5ZmLSh"
#redis_index = "grupo_13"
#redis_db = 0


# ************* Redis de Gustavo ************************************
redis_host = "redis-12419.c16.us-east-1-2.ec2.cloud.redislabs.com:12419"
redis_port = 12419
redis_password = "ZswdG0PZMxydrvZjeJRWogZpzo316VHU"
redis_index = "grupo_13"
redis_username = "default"
redis_db = 0


