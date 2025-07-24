## TODO

1. **Create a form interface**

   * Add text questions for the caregiver to answer.
   * Collect answers and generate a `.txt` file from the responses.

2. **Make activity suggestions smarter**

   * Currently, activities are static (stored in an array).
   * Use available user information to ask personalized questions (e.g., via Retrieval-Augmented Generation, RAG).
   * Combine dynamic questions with the same static activities list.

**3. Create a function to handle the end of a conversation**

 * This function should say goodbye to the patient politely.
 * It should also extract the most important pices of information from the conversation and add them to the RAG database.

- [ ] short memory ricorda anche quando aggiorni la pagina e scompare la chat (ma rimane salvata in memoria) -> clean history o mantenerla per diverse chat
- [ ] sintesi vocale con voce più naturale
- [ ] localstorage per le chat per evitare che si cancelli la conversazione quando si aggiorna la pagina
- [ ] forse è meglio avere topic suggeriti non fissi, sia perchè complicano il codice sia perchè limitano le conversazioni
  - [ ] topic vengono ripetuti se l'utente li rifiuta
- [ ] alcune volte il contesto usato per valutare la risposta, influisce sulla risposta stessa nei momenti sbagliati. se dopo una domanda aperta su roma, si trova un nuovo topic di cui parlare esempio musica, la risposta sarà un mix tra roma e musica, mentre dovrebbe essere solo musica.
- [ ] alcune volte non capisce che la risposta è una domanda aperta, e risponde con un topic da suggerire
- [ ] alcune volte si è rifiutato di cambiare argomento, anche se l'utente lo ha chiesto esplicitamente
- [ ] alcune volte sembra non ritrovare elementi in rag, ma questo capitato raramente.