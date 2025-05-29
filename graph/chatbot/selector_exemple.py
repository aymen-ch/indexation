from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_neo4j import Neo4jGraph
from django.conf import settings
graph = Neo4jGraph(url=settings.NEO4J_URI, username=settings.NEO4J_USERNAME, password=settings.NEO4J_PASSWORD,database=settings.NEO4J_DATABASE, enhanced_schema=True)


schema_description =  graph.schema
print(schema_description)
# Define the example template to format examples as "Question: ... Entities: ... Answer: ..."
example_prompt = PromptTemplate(
    input_variables=["question", "query"],
    template="Question: {question}\nquery: {query}"
)


