from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from .selector_exemple import *
from .exemples import exemples
from langchain_neo4j import Neo4jGraph

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



def simple_prompet(question,type):
    prompet = f"""
      You are a Neo4j expert tasked with converting Arabic questions into Cypher queries for a Neo4j database. Translate the Arabic question mentally into English to understand its intent and map it to the provided English schema.

**Database Schema:**
<Schema>
{schema_description}
</Schema>

**Input:**
- The question is in Arabic, optionally prefixed with a response type (`type:table` or `type:graph`).
- No specific nodes are selected; queries should apply broadly or as inferred from the question.

**Rules:**
1. Use node aliases (e.g., `(p:Personne)`).
2. Adhere strictly to the schema: only use defined node labels, properties, and relationship types.
3. Analyze the question carefully to map nodes, relationships, and properties accurately.
4. **Do not add any explanation, notes, or additional text under any circumstances.**
5. **Output only the Cypher query** in the specified format.

**Response Type Handling:**
1. **Table Response (`type:table` or default):**
   - Return a tabular result with properties or aggregations.
   - alwayse Use meaningful Arabic aliases in the case of table response (e.g., `p.name AS الاسم`, `COUNT(p) AS عدد_الأشخاص`).
   - Example:
     <Question>
       ما هو متوسط مدة المكالمات الهاتفية لكل شخص؟
     </Question>
     <Type>table</Type>
     <Query>
       MATCH (p:Personne)-[:Proprietaire]->(ph:Phone)-[ph_call:Appel_telephone]->()
RETURN p.birth_date AS تاريخ_الميلاد, p.national_id AS الرقم_الوطني, p.firstname AS الاسم, p.num AS الرقم, p.lastname AS اللقب, AVG(ph_call.duree_sec) AS متوسط_المدة
     </Query>

2. **Graph Response (`type:graph`):**
   - Always return the full path of the Cypher query.
   - Example:
     <Question>
       ما هي المكالمات الهاتفية لكل شخص؟
     </Question>
     <Type>graph</Type>
     <Query>
       MATCH path=(p:Personne)-[pr:Proprietaire]->(ph:Phone)-[ph_call:Appel_telephone]->()
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
*** type ***
<Type>{type}</Type>
. **Do not add any explanation, notes, or additional text under any circumstances.** , just return the cypher query in the specified format
  """
    return prompet



def simple_prompt_table(question):
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

def simple_prompt_graph(question):
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
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError

uri = "bolt://localhost:7687"
username = "neo4j"
password = "12345678"

try:
    driver = GraphDatabase.driver(uri, auth=(username, password))
    with driver.session() as session:
        result = session.run("RETURN 'Connected to Neo4j'")
        for record in result:
            print(record)
except Exception as e:
    print(f"An error occurred: {e}")



import requests

def call_ollama(prompt: str, model: str = "llama2") -> str:
    """
    Sends a prompt to the Ollama server and returns the response.
    Args:
        prompt (str): The input prompt.
        model (str): The model to use (default is "llama2").
    Returns:
        str: The generated response.
    """
    ollama_url = "http://127.0.0.1:11434/api/chat"
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




from neo4j.exceptions import CypherSyntaxError
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError

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


from langchain.prompts import PromptTemplate


zero_shot_prompt = PromptTemplate(
    template=(
        "Your task is to rephrase the result of a Neo4j Cypher query execution into a clear and natural human-readable answer in Arabic. "
        "Do not include any text other than the generated answer. If the result is empty, say 'لا يمكنني الإجابة'.\n"
        "Use only the result; do not add anything else or any additional information.\n"
        "**Important: Your output must only contain the generated answer. Do not include any extra text, explanations, or notes.**\n\n"
        "### Example 1\n"
        "السؤال: كم عدد الأشخاص المتورطين في قضايا ذات رقم Drog_6؟\n"
        "Cypher: MATCH (p:Personne)-[:Impliquer]-(a:Affaire {{Number: 'Drog_6'}}) RETURN p, count(p) AS عدد_الأشخاص\n"
        "النتيجة: {{'عدد_الأشخاص': 5}}\n"
        "الإجابة: يوجد <b>5</b> أشخاص متورطون في قضايا ذات رقم <b>Drog_6</b>.\n\n"
        "### Example 2\n"
        "السؤال: ما هي أسماء الأشخاص المتورطين في قضايا ذات رقم Drog_6؟\n"
        "Cypher: MATCH (p:Personne)-[:Impliquer]-(a:Affaire {{Number: 'Drog_6'}}) RETURN p.name AS أسماء_الأشخاص\n"
        "النتيجة: {{'أسماء_الأشخاص': ['علي', 'محمد', 'سارة']}}\n"
        "الإجابة: الأشخاص المتورطون في قضايا ذات رقم <b>Drog_6</b> هم:<br><b>علي</b><br><b>محمد</b><br><b>سارة</b>.\n\n"
        "### Example 3\n"
        "السؤال: كم عدد القضايا المرتبطة بشخص يدعى أحمد؟\n"
        "Cypher: MATCH (p:Personne {{name: 'أحمد'}})-[:Impliquer]-(a:Affaire) RETURN count(a) AS عدد_القضايا\n"
        "النتيجة: {{'عدد_القضايا': 3}}\n"
        "الإجابة: يوجد <b>3</b> قضايا مرتبطة بشخص يدعى <b>أحمد</b>.\n\n"
        "### Example 4 (Handling Properties)\n"
        "السؤال: ما هي تفاصيل الشخص المسمى أحمد؟\n"
        "Cypher: MATCH (p:Personne {{name: 'أحمد'}}) RETURN p\n"
        "النتيجة: {{'p': {{'name': 'أحمد', 'age': 30, 'city': 'القاهرة'}}}}\n"
        "الإجابة: تفاصيل الشخص المسمى <b>أحمد</b> هي:<br><b>الاسم</b>: أحمد<br><b>العمر</b>: 30<br><b>المدينة</b>: القاهرة.\n\n"
        "### New Query\n"
        "السؤال: {input_question}\n"
        "Cypher: {Cypher}\n"
        "النتيجة: {input_context}\n"
        "الإجابة:"
    ),
    input_variables=["input_question", "Cypher", "input_context"]
)



from langchain.prompts import PromptTemplate
table_with_keys_as_headers_prompt = PromptTemplate(
    template=(
        "Your task is to format the given context into a clear, well-organized table. "
        "The context contains the result of a Neo4j query. "
        "If the context is empty, say in Arabic: 'لا أعرف الجواب'. "
        "The question that generated this context is: '{input_question}'.\n"
        "Please display the question above the table and format the result as follows:\n"
        "The table should include **all details** from the context in a tabular format, "
        "with the **keys of the context as the column headers**, **excluding the 'identity' and 'elementId' keys**. "
        "Do not include any text except the table. Make sure to properly align the columns for easy readability.\n"
        "Table format example:\n"
        "Question: {input_question}\n"
        "| Key 1     | Key 2     |\n"
        "|-----------|-----------|\n"
        "| Value 1   | Value 2   |\n"
        "\nContext: {input_context}\nAnswer:"
    ),
    input_variables=["input_question", "input_context"]
)



graph_generation_prompt = PromptTemplate(
    template=(
        "Your task is to convert the given context into a subgraph format. "
        "The context contains the result of a Neo4j query. "
        "If the context is empty, return an empty subgraph. "
        "The subgraph format should include **nodes** and **relations** as follows:\n"
        "Nodes: A list of nodes, where each node has a `node_type` and `properties`.\n"
        "Relations: A list of relations, where each relation has `from`, `to`, `type`, and `properties`.\n"
        "**IMPORTANT: Your output must ONLY contain the subgraph in JSON format. Do not include any additional text, explanations, or numbering.**\n"
        "Context: {input_context}\n"
        "Subgraph:"
    ),
    input_variables=["input_context"]
)
def simple_prompet_resume(context, question, cypher_query):
    prompt = f"""
Using the provided context (result of the previous Cypher query), the original Arabic question, and the previous Cypher query, generate a resumed response for a Neo4j database.

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
1. Analyze the context, question, and previous Cypher query to generate a meaningful continuation of the response.
2. **Output only the resumed response** in the specified format.
3. The resumed response should be a natural continuation or enhancement of the previous result, potentially refining the query or summarizing the context in a user-friendly way.

**Output Requirements:**
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

**Example 2: Complex Case**
- Question: من هم الأشخاص المرتبطون بالشركة التي يعمل بها الشخص صاحب رقم التعريف الوطني 19454664525774، وما هي أدوارهم؟
- Cypher Query:
  MATCH (p:Person {{national_id: '19454664525774'}})-[:WORKS_FOR]->(c:Company)<-[:WORKS_FOR]-(colleague:Person)
  RETURN colleague.name AS colleague_name, colleague.role AS colleague_role, c.name AS company_name
- Context: [
    {{'colleague_name': 'أحمد محمد', 'colleague_role': 'مدير مشروع', 'company_name': 'شركة تقنية'}},
    {{'colleague_name': 'سارة علي', 'colleague_role': 'مهندس برمجيات', 'company_name': 'شركة تقنية'}},
    {{'colleague_name': 'خالد حسن', 'colleague_role': 'محلل بيانات', 'company_name': 'شركة تقنية'}}
  ]
- Resumed Response:
  <Resume>
    الأشخاص المرتبطون بالشركة التي يعمل بها صاحب رقم التعريف الوطني 19454664525774 هم:
    - أحمد محمد (مدير مشروع)
    - سارة علي (مهندس برمجيات)
    - خالد حسن (محلل بيانات)
    في شركة تقنية.
  </Resume>
"""
    return prompt




def simple_prompt_with_nodes(question, type, selected_nodes):
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