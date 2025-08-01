import spacy
from app.services import config
from app.services.rag import compute_embeddings
from qdrant_client.models import PointStruct
import app.services.utils as utils
from keybert import KeyBERT
import subprocess
import json


kw_model = KeyBERT()
nlp = spacy.load("en_core_web_sm") # se serve scarica il modello con `python -m spacy download en_core_web_sm`

def extract_preferences(text):
    # Estrai solo keyword/frasi rappresentative con KeyBERT (top 2, puoi regolare)
    keywords = [k[0] for k in kw_model.extract_keywords(text, keyphrase_ngram_range=(1,2), stop_words='english', top_n=2)]
    # Filtro keyword banali
    stop_keywords = {"hi", "hello", "ok", "thanks", "thank you", "please"}
    return [kw for kw in keywords if kw and kw.lower() not in stop_keywords]

# Relation Extraction: soggetto-verbo-oggetto
def extract_relations(text):
    doc = nlp(text)
    relations = []
    for token in doc:
        if token.dep_ == "ROOT" and token.pos_ == "VERB":
            subj = None
            obj = None
            for child in token.children:
                if child.dep_ in ("nsubj", "nsubjpass"):
                    subj = child.text
                if child.dep_ in ("dobj", "attr", "pobj"):
                    obj = child.text
            if subj and obj:
                relations.append({"subject": subj, "verb": token.lemma_, "object": obj})
    return relations

def extract_entities(text):
    utils.append_server_log(f"Extracting entities from text: {text}")
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]

def rewrite_extracted_info(entities, preferences, relations, text, model, utils_module=utils):
    """
    Pass extracted entities, preferences, and relations to an LLM to rewrite them in a more structured and meaningful format.
    """
    utils_module.append_server_log(f"Rewriting extracted info for text: {text}")

    prompt = f"""
    Extract and rewrite only the useful personal information from the following user message. 
    Ignore the question format and focus on facts, preferences, relationships, etc.
    Examples:
    - "Do you know I like chocolate?" → "The user likes chocolate."  
    - "Did you know my favorite color is blue?" → "The user's favorite color is blue."
    - "What is my favorite food?" → [don't save anything, it's just a question]

    Original message: "{text}"
    Extracted entities: {entities}
    Extracted preferences: {preferences}
    Extracted relations: {relations}
    """

    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt.encode(),
        capture_output=True
    )
    try:
        return json.loads(result.stdout.decode())
    except Exception:
        return result.stdout.decode()
    
def is_useful_message(text):
    """ Check if the message contains useful information by extracting entities, preferences, and relations.
    Returns a tuple (is_useful, entities, preferences, relations).
    """
    utils.append_server_log(f"Checking if message is useful: {text}")
    entities = extract_entities(text)
    preferences = extract_preferences(text)
    relations = extract_relations(text)
    # Se troviamo almeno una tra entità, preferenze, relazioni, eventi
    if entities or preferences or relations:
        utils.append_server_log(
            f"Message is useful with entities: {entities}, preferences: {preferences}, relations: {relations}"
        )
        return True, entities, preferences, relations
    else:
        utils.append_server_log(f"Message is not useful: no entities, preferences, relations or events found.")
        return False, [], [], []

def process_and_store_message(text, qdrant_client,embedding_model=config.EMBEDDING_MODEL, llm_model=config.MAIN_MODEL):
    utils.append_server_log(f"process_and_store_message chiamata con: {text}")
    is_useful, entities, preferences, relations = is_useful_message(text)
    if is_useful:
        # Controlla se esistono già le stesse preferenze, entità o relazioni in memoria
        existing = qdrant_client.search(
            collection_name="memory",
            query_vector=compute_embeddings(embedding_model, [text])[0],
            limit=20,
            with_payload=True,
        )
        existing_texts = [r.payload.get("text", "") for r in existing if r.score > 0.9]
        if text in existing_texts:
            utils.append_server_log(f"Similar message already in memory, skipping: {text}")
            return
        
        # Riscrivi le informazioni estratte usando l'LLM
        rewrited_info = rewrite_extracted_info(
            entities, preferences, relations, text, llm_model, utils_module=utils
        )
        # Filter: save only if the rewritten info contains relevant information (not generic questions)
        if not rewrited_info:
            utils.append_server_log(f"Rewritten info is empty, skipping insert: {text}")
            return
        #TODO: If the rewritten info is a question or too generic, do not save (possibili miglioramenti?)
        info_str = str(rewrited_info).lower()
        if info_str.startswith("the user asks") or "asks" in info_str:
            utils.append_server_log(f"Rewritten info is a question, skipping insert: {text}")
            return
        
        # Prepare the payload
        payload = {
            "rewrited_info": rewrited_info,
            "text": text
        }
        # Calcola embedding
        embedding = compute_embeddings(embedding_model, [text])[0]
        # Salva in Qdrant
        qdrant_client.upsert(
            collection_name="memory",
            points=[
                PointStruct(
                    id=hash(f"{hash(text)}") % (2**31),
                    vector=embedding,
                    payload=payload
                )
            ]
        )
        utils.append_server_log(f"Message processed and stored: {rewrited_info}")