from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from .selector_exemple import *
from .exemples import exemples
from langchain_neo4j import Neo4jGraph

from django.conf import settings

from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError
from neo4j.exceptions import CypherSyntaxError
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError


import requests

try:
    driver = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD,settings.NEO4J_DATABASE))
    with driver.session() as session:
        result = session.run("RETURN 'Connected to Neo4j'")
        for record in result:
            print(record)
except Exception as e:
    print(f"An error occurred: {e}")



def call_ollama(prompt: str, model: str = "llama2") -> str:
    """
    Sends a prompt to the Ollama server and returns the response.
    Args:
        prompt (str): The input prompt.
        model (str): The model to use (default is "llama2").
    Returns:
        str: The generated response.
    """
    ollama_url = settings.OLLAMA_URL+"/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],  # Adjusted payload structure
        "stream": False  # Disable streaming for simplicity
    }
    response = requests.post(ollama_url, json=payload)
    if response.status_code == 200:
        response_json = response.json()
        # Extract the content from the response 
        if 'message' in response_json and 'content' in response_json['message']:
            return response_json['message']['content']
        else:
            raise Exception("No content found in the response.")
    else:
        raise Exception(f"Error from Ollama server: {response.status_code}, {response.text}")






few_shot_prompt = FewShotPromptTemplate(
    examples=exemples,
    example_prompt=example_prompt,
    prefix="You are an expert in neo4j that converts questions into Cypher queries for a Neo4j database. "
           "The questions are in Arabic, while the database schema is in English.\n{schema_description}\n"
           "Always use aliases to refer to nodes in the query (e.g., `(p:Personne)`).\n"
            "- Analyze the question carefully with the database schema to extract the required relationships, including indirect ones. for exemple in the question(Issues in a State depende on the schema we need to pass by this chain (i:Issue)-[:Handles]-(u:Unit)-[:located_in]-(m:Municipality)-[:belongs_to]-(d:District)-[:belongs_to]-(s:State) )\n"
           "**Important: Do not use SQL syntax such as `GROUP BY`, `EXISTS`, `JOIN`, or `SELECT`. Use only Cypher syntax.**\n"
           "For grouping and aggregation, use Cypher's `WITH` and `RETURN` clauses.\n"
           "For filtering, use Cypher's `WHERE` clause.\n"
           "For relationships, use Cypher's `-[:RELATIONSHIP_TYPE]-` syntax.\n"
           "do not  use where clouse  after the return.\n"
           "**Ensure that integer values are correctly mapped as integers in the query and not as strings.**\n"
           "For example, if the question involves filtering by an integer value, ensure that the value is not enclosed in quotes in the Cypher query.\n"
           "**Whenever you use `[*]` for relationships, ALWAYS specify a fixed number (e.g., `[: r*..3]`) instead of an unbounded range like `[*]`.**\n" 
        "Please ensure that your output matches the format of the answers in the examples exactly.\n"
           "**IMPORTANT: Your output must ONLY contain the new Cypher query. Do not include any additional text, explanations, or numbering.**\n"
           "Use examples of questions and accurate Cypher statements below to help  you understand the correct mapping.\n"
           ,
    suffix="Question: {question}\nquery:",
    input_variables=["question", "schema_description"]
)







def prompt_table_query(question):
    prompt = f"""
You are a Neo4j expert tasked with converting Arabic questions into Cypher queries for a Neo4j database. The user requests a table response, meaning the query should return tabular results with properties or aggregations. Translate the Arabic question mentally into English to understand its intent and map it to the provided English schema.

**Database Schema:**
<Schema>
{schema_description}
</Schema>
**Input:**
- The question is in Arabic, requesting a table response .
- No specific nodes are selected; queries should apply broadly or as inferred from the question.
**Rules:**
1. Use node aliases (e.g., `(p:Personne)`).
2. Adhere strictly to the schema: only use defined node labels, properties, and relationship types.
3. Analyze the question carefully to map nodes, relationships, and properties accurately.
4. Always use meaningful Arabic aliases for the returned properties (e.g., `p.name AS الاسم`, `COUNT(p) AS عدد_الأشخاص`).
5. **Do not add any explanation, notes, or additional text under any circumstances.**
6. **Output only the Cypher query** in the specified format.
**Response Type Handling:**
- **Table Response**:
  - Return a tabular result with properties or aggregations.
  - Use meaningful Arabic aliases for all returned properties.
  - Example 1:
    <Question>
      ما هو متوسط مدة المكالمات الهاتفية لكل شخص؟
    </Question>

    <Query>
      MATCH (p:Personne)-[:Proprietaire]->(ph:Phone)-[ph_call:Appel_telephone]->()
      RETURN p.`تاريخ_الميلاد` AS تاريخ_الميلاد, p.`رقم التعريف الوطني` AS الرقم_الوطني, p.الاسم AS الاسم, p.اللقب AS اللقب, AVG(ph_call.duree_sec) AS متوسط_المدة
    </Query>
  - Example 2:
    <Question>
      كم عدد الأشخاص المرتبطين بكل قضية؟
    </Question>

    <Query>
      MATCH (p:Personne)-[:Impliquer]->(a:Affaire)
      RETURN a.Number AS رقم_القضية, COUNT(p) AS عدد_الأشخاص
    </Query>

**Output Requirements:**
- Return **only the Cypher query** in this exact format:
  <Query>
    ...
  </Query>

**Question:**
<Question>
{question}
</Question>

"""
    return prompt


def cypher_promp_action(question, node_type):
    prompt = f"""
You are a Neo4j expert tasked with generating Cypher queries for a Neo4j database based on a natural language question, a specified node type, and a provided schema. The query should return nodes, relationships, or paths as appropriate for the question, ensuring compatibility with the schema.

**Database Schema:**
<Schema>
{schema_description}
</Schema>

**Input:**
- Node Type: {node_type}
- Question: {question}
- The question is in natural language (e.g., English or Arabic) and requests a specific query response.
- The query should focus on the specified node type and its relationships or properties.

**Rules:**
1. Use node aliases (e.g., `(n:{node_type})`).
2. Adhere strictly to the schema: only use defined node labels, properties, and relationship types.
3. Analyze the question to map nodes, relationships, and properties accurately.
4. Use `$id` to reference the ID of the context node when filtering by ID.
5. If the question is in Arabic, translate it mentally to English to understand its intent.
6. **Do not add any explanation, notes, or additional text.**
7. **Output only the Cypher query** in the specified format.

**Response Type Handling:**
- Return nodes, relationships, or paths based on the question’s intent.
- Example 1:
  <Node Type>
    Affaire
  </Node Type>
  <Question>
    Identify other cases that occurred on the same date as the current case.
  </Question>
  <Query>
    MATCH (context:Affaire) WHERE id(context) = $id MATCH (other:Affaire) WHERE id(other) <> $id AND other.date = context.date RETURN other
  </Query>
- Example 2:
  <Node Type>
    Personne
  </Node Type>
  <Question>
    What are the phone calls for a person?
  </Question>
  <Query>
    MATCH path=(n:Personne)-[:Proprietaire]->(ph:Phone)-[:Appel_telephone]->()
    RETURN path
  </Query>

**Output Requirements:**
- Return **only the Cypher query** in this exact format:
  <Query>
    ...
  </Query>

**Node Type:**
<Node Type>
{node_type}
</Node Type>

**Question:**
<Question>
{question}
</Question>
"""
    return prompt
def prompt_graph_query(question):
    prompt = f"""
You are a Neo4j expert tasked with converting Arabic questions into Cypher queries for a Neo4j database. The user requests a graph response, meaning the query should return the full path of relationships and nodes. Translate the Arabic question mentally into English to understand its intent and map it to the provided English schema.

**Database Schema:**
<Schema>
{schema_description}
</Schema>

**Input:**
- The question is in Arabic, requesting a graph response.
- No specific nodes are selected; queries should apply broadly or as inferred from the question.

**Rules:**
1. Use node aliases (e.g., `(p:Personne)`).
2. Adhere strictly to the schema: only use defined node labels, properties, and relationship types.
3. Analyze the question carefully to map nodes, relationships, and properties accurately.
4. Always return the full path using `path = ...` in the `MATCH` clause.
5. **Do not add any explanation, notes, or additional text under any circumstances.**
6. **Output only the Cypher query** in the specified format.

**Response Type Handling:**
- **Graph Response**:
  - Return the full path of the Cypher query.
  - Example 1:
    <Question>
      ما هي المكالمات الهاتفية لكل شخص؟
    </Question>
    <Query>
      MATCH path=(p:Personne)-[pr:Proprietaire]->(ph:Phone)-[ph_call:Appel_telephone]->()
      RETURN path
    </Query>
  - Example 2:
    <Question>
      'ماهي  دوائر التي تنتمي الى ولاية 'المدية
    </Question>
    <Query>
      MATCH path = (d:Daira)-[:appartient]-(w:Wilaya {{nom_arabe: 'المدية'}})
       RETURN path
    </Query>

**Output Requirements:**
- Return **only the Cypher query** in this exact format:
  <Query>
    ...
  </Query>

**Question:**
<Question>
{question}
</Question>
"""
    return prompt



def execute_query_for_response_generation(query):
    def execute_query(query):
        def _execute():
            with driver.session(database="neo4j") as session:
                result = session.run(query)
                records_list = []
                for record in result:
                    record_dict = {}
                    for key in record.keys():
                        record_dict[key] = record[key]
                    records_list.append(record_dict)
                # Concatenate all records into a single string
                concatenated_result = "\n".join([str(record) for record in records_list])
                return concatenated_result, True  #Return the result and a success indicator
                
        # Use ThreadPoolExecutor to enforce a timeout
        with ThreadPoolExecutor() as executor:
            future = executor.submit(_execute)
            try:
                return future.result(timeout=7)
            except TimeoutError:
                return None, False  # Return None and indicate failure
            except Exception as e:
                return None, False  # Return None and indicate failure

    try:
        # Try executing the original query
        return execute_query(query)
    except CypherSyntaxError as e:
        return e, False  # Skip correction if disabled





import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def execute_and_correct_query(query, enable_correction=True):
    def execute_query(query):
            with driver.session(database="neo4j") as session:
                result = session.run(query)
                records_list = []
                for record in result:
                    # Directly extract values into a list
                    values = list(record.values())
                    records_list.append(values)

                # Concatenate all records into a single string
                concatenated_result = "\n".join([f"{{{', '.join(map(str, record))}}}" for record in records_list])
                print(concatenated_result)
                return concatenated_result, True  # Return result and success flag
    try:
        # Try executing the original query
         execute_query(query)
    except CypherSyntaxError as e:
        print("error")
        if True:
            # Proceed to query correction
            corrected_query = correct_query_with_llm(query, str(e))
            if corrected_query:
                print(f"Attempting to execute corrected query: {corrected_query}")
                try:
                    return execute_query(corrected_query)
                except Exception as corrected_error:
                    print(f"Corrected query failed: {corrected_query}\nError: {corrected_error}")
                    return None, False  # Correction failed
            else:
                print("Failed to generate a corrected query.")
                return None, False  # LLM correction failed
        else:
            return None, False  # Correction disabled
    except Exception as e:
        print(f"An error occurred while executing the query: {query}\nError: {e}")
        return None, False  # Other errors

def correct_query_with_llm(query, error_message):
    print("~~~~~~~~~ Entering correction process ~~~~~~~~~")
    # Create a prompt for the LLM to correct the query
    prompt = f"""
        The following Cypher query resulted in an error:
        Query: {query}
        Error: {error_message}
        Please correct the query to fix the syntax error. Ensure the corrected query is valid and follows Cypher syntax rules.
        Return only the corrected query, without any additional explanations or text.
        Corrected Query:
    """
    try:
        # Use the LLM to generate the corrected query
        corrected_query = call_ollama(prompt, model="llama3.1:8b")
        return corrected_query.strip()  # Remove any leading/trailing whitespace
    except Exception as e:
        print(f"Error while correcting query with LLM: {e}")
        return None  # Return None if correction fails




def simple_prompet_resume(context, question, cypher_query):
    prompt = f"""
Using the provided context (result of the Neo4j Cypher query), the original Arabic question (which the result answers), and the Neo4j Cypher query,
generate a concise and natural-language summary of the result.

**Context:**
<Context>
{context}
</Context>

**Question:**
<Question>
{question}
</Question>

**Previous Cypher Query:**
<Cypher>
{cypher_query}
</Cypher>

**Rules:**
1. Analyze the context, question, and Cypher query to generate a meaningful and accurate response.
2. **Output only the resumed response** in the specified format.
3. The resumed response should be a natural continuation or summarization of the result, user-friendly, and informative.

**Output Format:**
- Return **only the resumed response** in this exact format:
  <Resume>
    ...
  </Resume>

**Examples:**

**Example 1: Simple Case**
- Question: ما هو رقم هاتف الشخص الذي لديه رقم التعريف الوطني 19454664525774؟
- Cypher Query:
  MATCH (p:Phone {{num: '0774033106'}})-[:Appel_telephone]-(calledPhone:Phone)
  RETURN calledPhone.num AS أرقام_الهواتف_المنصل_بها
- Context: {{'أرقام_الهواتف_المنصل_بها': '0660838914'}}
- Resumed Response:
  <Resume>
    الرقم المرتبط برقم التعريف الوطني المطلوب هو 0660838914
  </Resume>
"""
    return prompt





def simple_prompt_with_selected_nodes(question, type, selected_nodes):
    prompt = f"""
You are a Neo4j expert tasked with converting Arabic questions into Cypher queries for a Neo4j database. The user has selected specific nodes and asks a question about them. Translate the Arabic question mentally into English to understand its intent and map it to the provided schema.

**Database Schema:**
<Schema>
{schema_description}
</Schema>

**Selected Nodes:**
<Nodes>
{selected_nodes}
</Nodes>
- Format: `Label:ID` (e.g., `Personne:122`, `Affaire:223`).
- Use these nodes as starting points or constraints in the query, matching them by their internal Neo4j ID using `id()` (e.g., `WHERE id(p) = 122`).

**Input:**
- The question is in Arabic, optionally prefixed with a response type (`type:table` or `type:graph`).
- The selected nodes are provided and must be used in the query.

**Rules:**
1. Use node aliases (e.g., `(p:Personne)`).
2. Adhere strictly to the schema: only use defined node labels, properties, and relationship types.
3. Incorporate the selected nodes by matching them explicitly using `id()` for internal Neo4j IDs (e.g., `MATCH (p:Personne) WHERE id(p) = 122`).
4. Analyze the question carefully to map nodes, relationships, and properties accurately.
5. For shortest path queries, use `shortestPath()` with `[*]` to allow relationships in any direction, unless the question specifies a direction.
6. **Do not add any explanation, notes, or additional text under any circumstances.**
7. **Output only the Cypher query** in the specified format.

**Response Type Handling:**
1. **Table Response (`type:table` or default):**
   - Return a tabular result with properties or aggregations.
   - Always use meaningful Arabic aliases (e.g., `p.الاسم AS الاسم`, `COUNT(p) AS عدد_الأشخاص`).
   - Example:
     <Question>
       ما هي خصائص الشخص والقضية المختارين؟
     </Question>
     <Type>table</Type>
     <Nodes>Personne:122,Affaire:223</Nodes>
     <Query>
       MATCH (p:Personne), (a:Affaire)
       WHERE id(p) = 122 AND id(a) = 223
       RETURN p.`رقم التعريف الوطني` AS الرقم_الوطني, p.الاسم AS الاسم, p.اللقب AS اللقب, a.Number AS رقم_القضية
     </Query>
2. **Graph Response (`type:graph`):**
   - Return the full path or relevant graph structure.
   - For shortest path queries, use `shortestPath()` with a variable (e.g., `path = shortestPath(...)`) and return the path.
   - Example:
     <Question>
       ما هو أقصر مسار بين الشخص والقضية؟
     </Question>
     <Type>graph</Type>
     <Nodes>Personne:122,Affaire:223</Nodes>
     <Query>
       MATCH path = shortestPath((p:Personne)-[*]-(a:Affaire))
       WHERE id(p) = 122 AND id(a) = 223
       RETURN path
     </Query>

**Output Requirements:**
- Return **only the Cypher query** in this exact format:
  <Query>
    ...
  </Query>

**Question:**
<Question>
{question}
</Question>
<Type>{type}</Type>
"""
    return prompt