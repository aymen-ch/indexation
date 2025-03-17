from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from .selector_exemple import *

few_shot_prompt = FewShotPromptTemplate(
    example_selector=example_selector,
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