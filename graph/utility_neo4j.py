from neo4j import Result
from django.conf import settings
import neo4j
from .utility import driver

def parse_to_graph_with_transformer(query, params=None, database=None):
    """
    Execute a Neo4j query and parse the result into a graph structure using neo4j.Result.graph.
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
    Execute a Neo4j query and return the results as a list of dictionaries.
    """
    with driver.session(database=database or settings.NEO4J_DATABASE) as session:
        results = session.run(query, params or {})
        return [record.data() for record in results]
    

