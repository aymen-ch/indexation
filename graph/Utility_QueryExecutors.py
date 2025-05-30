from neo4j import Result
from django.conf import settings
import neo4j
# from .utility import driver

from django.conf import settings
from django.core.cache import cache
from neo4j import GraphDatabase

"""
To unify the results and make them easier to work with on the frontend.

- 70% of the functions in the project use `parse_to_graph_with_transformer`, which means they return the result as a graph.
- If the result cannot be returned as a graph, the function will use `run_query` instead.
"""

def get_neo4j_driver():
    """
    **Description:** Returns the Neo4j driver instance.

    **Purpose:** This function is used to establish a connection to the Neo4j database.
    It returns a driver instance that can be used to execute Cypher queries and perform other graph-related tasks.

    **What happens inside:** This function reads the Neo4j connection settings from the `../settings.py` file and uses them to create a new driver instance.
    The driver instance is then returned to the caller.

    **Input:**
    None

    **Output:**
    neo4j.Driver: The Neo4j driver instance.
    """
       
    return GraphDatabase.driver(
        settings.NEO4J_URI, 
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
    )


driver = get_neo4j_driver()


def parse_to_graph_with_transformer(query, params=None, database=None):
    """
    **Description:** Execute a Neo4j query and parse the result into a graph structure using neo4j.Result.graph.

    **Purpose:** This function is used to execute a Cypher query and parse the result into a graph structure that can be easily worked with.

    **What happens inside:** This function executes a Cypher query using the Neo4j driver, and then uses the `neo4j.Result.graph` result transformer to parse the query result into a graph structure.

    **Input:**
    query (str): The Cypher query to execute.
    params (dict): Parameters to pass to the query (optional).
    database (str): The name of the database to execute the query against (optional).

    **Output:**
    dict: A dictionary containing the parsed graph structure, with nodes and edges as lists of dictionaries.
    """
    try:
        graph_result = driver.execute_query(
            query,
            params or {},
            database_=database or settings.NEO4J_DATABASE,
            result_transformer_=neo4j.Result.graph
        )
        nodes = {}
        edges = {}
        
        for node in graph_result.nodes:
            labels = list(node.labels)
            node_type = labels[0] if labels else "Unknown"
            nodes[node.id] = {
                "id": node.id,
                "nodeType": node_type,
                "properties": dict(node)
            }
        
        for rel in graph_result.relationships:
            edges[rel.id] = {
                "id": str(rel.id),
                "type": rel.type,
                "startNode": rel.start_node.id,
                "endNode": rel.end_node.id,
                "properties": dict(rel)
            }

        print(f"Number of nodes: {len(graph_result.nodes)}")
        print(f"Number of edges: {len(graph_result.relationships)}")
        
        return {
            "nodes": list(nodes.values()),
            "edges": list(edges.values())
        }
    
    except Exception as e:
        raise Exception(f"Error parsing query result to graph: {str(e)}")


def run_query(query, params=None, database=None):
    """
    Execute a Cypher query against a Neo4j database and return the results.

    **Description:** This function establishes a session with the specified Neo4j database (or the default database if none is provided),
    executes the given Cypher query with the provided parameters, and returns the query results.

    **Args:**
    query (str): The Cypher query to execute.
    params (dict, optional): Parameters to pass to the query.
    database (str, optional): The name of the database to execute the query against.

    **Returns:**
    list[dict]: A list of dictionaries, each representing a record from the query results.
    Execute a Neo4j query and return the results as a list of dictionaries.
    """
    with driver.session(database=database or settings.NEO4J_DATABASE) as session:
        # Run the query with the provided parameters or an empty dictionary if none are given
        results = session.run(query, params or {})
        
        # Convert each result record into a dictionary and return as a list
        return [record.data() for record in results]
    


