import os
from dotenv import load_dotenv
from pinecone import Pinecone
from google import genai

# Cargar las variables del .env (asegurate de tener GEMINI_API_KEY y PINECONE_API_KEY ahí)
load_dotenv()

print("Iniciando carga de la base de datos...")

# Inicializar clientes
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("chatbot-inmobiliaria")
ai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Este es tu "Catálogo". El día de mañana esto podría venir de un Excel o tu base SQL
propiedades = [
    {
        "id": "proyecto-brigos-palermo",
        "tipo": "desarrollo_en_pozo",
        "texto": "Brigos Palermo: Exclusivo proyecto en pozo en el corazón de Palermo. Departamentos de 2 y 3 ambientes con amenities de lujo (pileta, gimnasio, SUM). Ideal para inversores jóvenes o alquiler temporario. Entrega estimada: Diciembre 2027. Financiación hasta en 36 cuotas en pesos."
    },
    {
        "id": "proyecto-brigos-recoleta",
        "tipo": "desarrollo_en_pozo",
        "texto": "Brigos Recoleta: Emprendimiento premium orientado a familias y público exigente. Unidades de 4 ambientes con dependencia y balcones aterrazados. Seguridad 24hs y terminaciones de primera calidad europea. Entrega estimada: Marzo 2028. Se aceptan propiedades en parte de pago."
    },
    {
        "id": "proyecto-casa-huidobro",
        "tipo": "desarrollo_en_pozo",
        "texto": "Casa Huidobro: Un concepto diferente. Edificio boutique de pocas unidades tipo loft. Pensado para un público moderno que busca diseño y privacidad en una calle arbolada y tranquila. Unidades apto profesional. Últimas 2 unidades disponibles."
    },
    {
        "id": "info-beltran-libro",
        "tipo": "informacion_general",
        "texto": "El Método Briones: Beltrán Briones es el autor del best seller 'El Método Briones: Cómo promocionar y vender cualquier cosa'. Es una lectura obligada para entender nuestra filosofía de trabajo. Se puede adquirir a través de Mercado Libre con envío a todo el país."
    }
]

print("Generando vectores y subiendo a Pinecone (esto puede tardar unos segundos)...")

for prop in propiedades:
    # 1. Generar el vector con Gemini
    response = ai.models.embed_content(
        model='gemini-embedding-001',
        contents=prop["texto"]
    )
    vector = response.embeddings[0].values
    
    # 2. Subir a Pinecone
    index.upsert(
        vectors=[
            {
                "id": prop["id"],
                "values": vector,
                "metadata": {
                    "tipo": prop["tipo"],
                    "texto_original": prop["texto"] # Este es el texto que va a leer el chatbot
                }
            }
        ]
    )
    print(f"✅ Subido con éxito: {prop['id']}")

print("¡Listo! Tu base de datos Pinecone ya tiene información.")