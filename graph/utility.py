from django.conf import settings
from django.core.cache import cache
from neo4j import GraphDatabase
def get_neo4j_driver():
    return GraphDatabase.driver(
        settings.NEO4J_URI, 
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
    )


driver = get_neo4j_driver()

def fetch_node_types():
    query = """
    CALL db.labels() YIELD label
    RETURN label
    """
    print("NEO4J_DATABASE &&&" ,settings.NEO4J_DATABASE)

    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(query)
            node_types = [{"type": record["label"]} for record in result]
            
            # Cache the result for 10 minutes (600 seconds)
            return node_types
    finally:
        print("")
def fetch_node_properties(node_type):
    """
    Fetches properties and their types for a specific node type from Neo4j.
    """
    query = f"""
    MATCH (n:{node_type})
    RETURN n
    LIMIT 5
    """

    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(query)
            nodes = [dict(record["n"]) for record in result]

            if not nodes:
                return []

            # Determine properties and their types
            property_types = {}
            for node in nodes:
                for key, value in node.items():
                    # Skip 'elementId' and 'identity'
                    if key in ["elementId", "identity"]:
                        continue
                    value_type = type(value).__name__
                    if key in property_types:
                        if property_types[key] != value_type:
                            property_types[key] = "mixed"
                    else:
                        property_types[key] = value_type

            return [
                {"name": key, "type": property_types[key]}
                for key in property_types
            ]
    finally:
        print("")
def run_query(query, params=None):
    print("NEO4J_DATABASE !!" ,settings.NEO4J_DATABASE)
    with driver.session(database = settings.NEO4J_DATABASE) as session:
        results = session.run(query, params or {})
        return [record.data() for record in results]
    

# #################################

