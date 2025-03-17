from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain import LLMChain 
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from .exemples import exemples

schema_description = """
use just the nodes and properties and relations that existe in this Database Schema:
Node properties:
- **Daira**
  - `nom_francais`: STRING Example: "Aoulef"
  - `nom_arabe`: STRING Example: "أولف"
- **Commune**
  - `longitude`: FLOAT Min: -1.3565692, Max: 8.1994276
  - `nom_francais`: STRING Example: "Aoulef"
  - `latitude`: FLOAT Min: 0, Max: 36.839681
  - `nom_arabe`: STRING Example: "أولف"
- **Wilaya**
  - `nom_francais`: STRING Example: "Adrar"
  - `nom_arabe`: STRING Example: "ادرار"
  - `matricule`: INTEGER Min: 1, Max: 58
- **Unite**
  - `nom_francais`: STRING Example: "Brigade territoriale de la GN Aoulef"
  - `Type`: STRING Available options: ['Brigade']
  - `nom_arabe`: STRING Example: "الفرقة الإقليمية للدرك الوطني بأولف"
- **Affaire**
  - `Number`: STRING Example: "Drog_1"
  - `date`: STRING Example: "17-04-2023"
  - `Type`: STRING Available options: ['مخدرات']
- **Personne**
  - `birth_date`: STRING Example: "22-09-1994"
  - `national_id`: STRING Example: "45339030376158"
  - `firstname`: STRING Example: "موهوب"
  - `num`: INTEGER Example: "1"
  - `lastname`: STRING Example: "منير"
- **Virtuel**
  - `Nom`: STRING Example: "Michael Morales"
  - `Type`: STRING Example: "Facebook"
  - `ID`: STRING Example: "175575809826100"
- **Phone**
  - `operateur`: STRING Example: "Djezzy"
  - `num`: STRING Example: "0792803473"
Relationship properties:
- **appartient**
  - `identity: INTEGER` Min: 0, Max:  632
- **situer**
  - `identity: INTEGER` Min: 633, Max:  1090
- **Traiter**
  - `identity: INTEGER` Min: 1091, Max:  4090
- **Impliquer**
  - `identity: INTEGER` Min: 4091, Max:  13209
- **Proprietaire**
  - `identity: INTEGER` Example: "13210"
- **Appel_telephone**
  - `identity: INTEGER` Min: 44734, Max:  54356
  - `duree_sec: INTEGER` Min: 11, Max:  115
The relationships:
(:Daira)-[:appartient]-(:Wilaya)
(:Commune)-[:appartient]-(:Daira)
(:Unite)-[:situer]-(:Commune)
(:Affaire)-[:Impliquer]-(:Personne)
(:Affaire)-[:Traiter]-(:Unite)
(:Personne)-[:Appel_telephone]-(:Affaire)
(:Virtuel)-[:Proprietaire]-(:Personne)
(:Phone)-[:Proprietaire]-(:Personne)
(:Phone)-[:Appel_telephone]-(:Phone)
"""

# Define the example template to format examples as "Question: ... Entities: ... Answer: ..."
example_prompt = PromptTemplate(
    input_variables=["question", "query"],
    template="Question: {question}\nquery: {query}"
)


from langchain import LLMChain
from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_community.embeddings import HuggingFaceEmbeddings

# Neo4j connection details
neo4j_url = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "12345678"

arabic_embedder = HuggingFaceEmbeddings(
    model_name="aubmindlab/bert-base-arabertv02",
    model_kwargs={'device': 'cpu'}
)

example_selector = SemanticSimilarityExampleSelector.from_examples(
    exemples,
    arabic_embedder,
    Neo4jVector,
    url=neo4j_url,
    username=neo4j_user,
    password=neo4j_password,
    k=3,
    input_keys=["question"],
)