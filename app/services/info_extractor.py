import spacy
from app.services import config
from app.services.rag import compute_embeddings
import app.services.utils as utils

from qdrant_client.models import PointStruct
from keybert import KeyBERT
import subprocess


kw_model = KeyBERT()
nlp = spacy.load("en_core_web_sm")

def extract_preferences(text):
    '''Extracts user preferences from the text.'''
    keywords = [k[0] for k in kw_model.extract_keywords(text, keyphrase_ngram_range=(1,2), stop_words='english', top_n=2)] # extract only representative keywords/phrases with KeyBERT (top 2, can be adjusted)

    # Filter banal keywords
    stop_keywords = {"hi", "hello", "ok", "thanks", "thank you", "please"}
    return [kw for kw in keywords if kw and kw.lower() not in stop_keywords]

def extract_relations(text):
    '''Extracts subject-verb-object relations from the text.'''
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
    '''Extracts named entities from the text.'''
    utils.append_server_log(f"Extracting entities from text: {text}")
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]

def rewrite_extracted_info(entities, preferences, relations, text, model):
    """
    Pass extracted entities, preferences, and relations to an LLM to rewrite them in a more structured and meaningful format.
    """
    utils.append_server_log(f"Rewriting extracted info for text: {text}")

    prompt = f"""
    Extract and rewrite personal information from the user's message. Focus on what the user reveals about themselves.

    ALWAYS SAVE these types of information:
    - Likes/dislikes: "I love X", "I hate Y", "I prefer Z"
    - Personal facts: age, location, family, work, health conditions
    - Future plans: "I want to travel to X", "I will visit Y"
    - Personal experiences: "I have been to X", "I tried Y"
    - Characteristics: personality traits, habits, allergies

    NEVER SAVE these:
    - Pure questions: "What is my favorite food?" (no new info revealed)
    - Commands: "Tell me about X", "Show me Y" 
    - Greetings: "Hello", "Thanks", "Goodbye"

    Format: Always start with "The user..." when saving information.
    If no personal information is revealed, respond exactly: "No personal information found"

    Examples:
    - "I love chocolate" → "The user loves chocolate"
    - "I want to travel to Japan" → "The user wants to travel to Japan"
    - "I love Japan" → "The user loves Japan"
    - "I love dogs" → "The user loves dogs"
    - "What is my favorite color?" → "No personal information found"
    - "Tell me a joke" → "No personal information found"

    User message: "{text}"
    Detected entities: {entities}
    Keywords: {preferences}
    Relations: {relations}

    Response:"""

    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt.encode(),
        capture_output=True
    )
    try:
        response = result.stdout.decode().strip()
        if response.startswith("Response:"):
            response = response[9:].strip()
        return response
    except Exception as e:
        utils.append_server_log(f"Error in LLM processing: {e}")
        return "No personal information found"
    
def is_useful_message(text):
    """ Check if the message contains useful information by extracting entities, preferences, and relations.
    Returns a tuple (is_useful, entities, preferences, relations).
    """
    utils.append_server_log(f"Checking if message is useful: {text}")
    entities = extract_entities(text)
    preferences = extract_preferences(text)
    relations = extract_relations(text)
    # if we find at least one among entities, preferences, relations
    if entities or preferences or relations:
        utils.append_server_log(
            f"Message is possibly useful with entities: {entities}, preferences: {preferences}, relations: {relations}"
        )
        return True, entities, preferences, relations
    else:
        utils.append_server_log(f"Message is not useful: no entities, preferences, relations or events found.")
        return False, [], [], []

def process_and_store_message(text, qdrant_client,embedding_model=config.EMBEDDING_MODEL, llm_model=config.MAIN_MODEL):
    """ Process a user message: check if it's useful, rewrite extracted info, and store in Qdrant if relevant. """
    is_useful, entities, preferences, relations = is_useful_message(text)
    if is_useful:
        # Check if similar message already exists in Qdrant (similarity > 0.9)
        existing = qdrant_client.search(
            collection_name=config.MEMORY_COLLECTION_NAME,
            query_vector=compute_embeddings(embedding_model, [text])[0],
            limit=20,
            with_payload=True,
        )
        existing_texts = [r.payload.get("text", "") for r in existing if r.score > 0.9]
        if text in existing_texts:
            utils.append_server_log(f"Similar message already in memory, skipping: {text}")
            return
        
        rewrited_info = rewrite_extracted_info(
            entities, preferences, relations, text, llm_model
        )
        utils.append_server_log(f"Rewritten info: {rewrited_info}")
        # Filter: save only if the rewritten info contains relevant information (not generic questions)
        if not rewrited_info:
            utils.append_server_log(f"Rewritten info is empty, skipping insert: {text}")
            return
        # if the message is generic (the user asks something) skip it
        info_str = str(rewrited_info).lower()

        # Block responses that indicate no useful information
        no_info_indicators = [
            "no extracted information",
            "no useful information", 
            "no relevant information",
            "no personal information",
            "the user asks",
            "asks"
        ]

        if any(indicator in info_str for indicator in no_info_indicators):
            utils.append_server_log(f"Rewritten info indicates no useful information, skipping insert: {text}")
            return
        
        # Prepare the payload
        payload = {
            "rewrited_info": rewrited_info,
            "text": text
        }
        embedding = compute_embeddings(embedding_model, [text])[0]
        qdrant_client.upsert(
            collection_name=config.MEMORY_COLLECTION_NAME,
            points=[
                PointStruct(
                    id=hash(f"{hash(text)}") % (2**31),
                    vector=embedding,
                    payload=payload
                )
            ]
        )
        utils.append_server_log(f"Message processed and stored: {rewrited_info}")
        utils.append_memory_log(rewrited_info)