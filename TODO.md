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