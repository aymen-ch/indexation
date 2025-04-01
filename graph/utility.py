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
    """
    Fetches all node types from the Neo4j database.
    """
    cache_key = "node_types_cache"
    cached_data = cache.get(cache_key)
    # if cached_data:
    #     return cached_data

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
            cache.set(cache_key, node_types, timeout=600)
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


from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

@api_view(['POST'])
def get_current_database_view(request):
    """
    API endpoint to get the current database name.
    POST request (no body required).
    """
    print("NEO4J_DATABASE" ,settings.NEO4J_DATABASE)
    driver = get_neo4j_driver()
    try:
        query = "CALL db.info() YIELD name RETURN name"
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(query)
            db_name = result.single()["name"]
            return Response({"current_database": db_name}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def list_all_databases_view(request):
    """
    API endpoint to list all databases and their statuses.
    POST request (no body required).
    """
    print("NEO4J_DATABASE" ,settings.NEO4J_DATABASE)
    try:
        query = "SHOW DATABASES YIELD name, currentStatus RETURN name, currentStatus"
        with driver.session(database="system") as session:
            result = session.run(query)
            databases = [{"name": record["name"], "status": record["currentStatus"]} for record in result]
            return Response({"databases": databases}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def create_new_database_view(request):
    """
    API endpoint to create a new database.
    POST request body: {"db_name": "your_database_name"}
    """
    print("NEO4J_DATABASE" ,settings.NEO4J_DATABASE)
    db_name = request.data.get("db_name")
    if not db_name:
        return Response({"error": "db_name is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        query = f"CREATE DATABASE {db_name}"
        with driver.session(database="system") as session:
            session.run(query)
            return Response({"message": f"Database '{db_name}' created successfully"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
def change_current_database_view(request):
    """
    API endpoint to change the current database by updating settings.NEO4J_DATABASE.
    POST request body: {"db_name": "your_database_name"}
    """
    print("NEO4J_DATABASE" ,settings.NEO4J_DATABASE)

    db_name = request.data.get("db_name")
    if not db_name:
        return Response({"error": "db_name is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Check if the database exists and is online
        driver = get_neo4j_driver()
        with driver.session(database="system") as session:
            query = "SHOW DATABASES YIELD name, currentStatus WHERE name = $db_name RETURN currentStatus"
            result = session.run(query, {"db_name": db_name})
            record = result.single()
            if not record:
                return Response({"error": f"Database '{db_name}' does not exist"}, status=status.HTTP_404_NOT_FOUND)
            if record["currentStatus"] != "online":
                return Response({"error": f"Database '{db_name}' is not online"}, status=status.HTTP_400_BAD_REQUEST)

        # Update the settings to switch the database
        print("db_name" , db_name)
        settings.NEO4J_DATABASE = db_name


        # Verify the switch by querying the new database
        driver = get_neo4j_driver()  # Re-instantiate driver with new database
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            query = "CALL db.info() YIELD name RETURN name"
            result = session.run(query)
            current_db = result.single()["name"]

        if current_db != db_name:
            return Response({"error": "Failed to switch database"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": f"Switched to database '{db_name}' successfully", "current_database": current_db}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        driver.close()



import os

import os
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from neo4j import GraphDatabase
from django.conf import settings

@api_view(['POST'])
def import_file_to_neo4j_view(request):
    """
    API endpoint to import a file into Neo4j.
    POST request body (form-data):
    - file: The file to upload (CSV, JSON, or Cypher)
    - file_type: Optional (csv, json, cypher) - if not provided, inferred from extension
    - config: Optional JSON string for APOC configuration (for CSV/JSON)
    - nodes: Optional JSON string of node mappings (for CSV)
    - relationships: Optional JSON string of relationship mappings (for CSV)
    """
    # Check if a file is provided
    if 'file' not in request.FILES:
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    uploaded_file = request.FILES['file']
    file_name = uploaded_file.name
    file_type = request.data.get('file_type', '').lower()
    
    # Infer file type from extension if not provided
    if not file_type:
        file_extension = os.path.splitext(file_name)[1].lower()
        if file_extension == '.csv':
            file_type = 'csv'
        elif file_extension == '.json':
            file_type = 'json'
        elif file_extension == '.cypher':
            file_type = 'cypher'
        else:
            return Response({"error": "Unsupported file type. Use .csv, .json, or .cypher"}, 
                          status=status.HTTP_400_BAD_REQUEST)

    # Parse JSON configurations
    try:
        nodes = json.loads(request.data.get('nodes', '[]'))
        relationships = json.loads(request.data.get('relationships', '[]'))
        config = json.loads(request.data.get('config', '{}'))
    except json.JSONDecodeError as e:
        return Response({"error": f"Invalid JSON configuration: {str(e)}"}, 
                      status=status.HTTP_400_BAD_REQUEST)

    # # Initialize Neo4j driver
    # driver = GraphDatabase.driver(
    #     settings.NEO4J_URI,
    #     auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
    # )

    try:
        # Get the import directory path from Neo4j
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("CALL dbms.listConfig('server.directories.import') YIELD value RETURN value AS importDirectoryPath")
            import_dir = result.single()["importDirectoryPath"]
            
        # Save the file to the import directory
        file_path = os.path.join(import_dir, file_name)
        
        try:
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
        except Exception as e:
            return Response({"error": f"Failed to save file: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Process the file based on type
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            if file_type == 'csv':
                # Prepare nodes configuration
                nodes_config = []
                for node in nodes:
                    node_config = {
                        "fileName": f"file:///{file_name}",
                        "labels": node.get("labels", []),
                        "mapping": node.get("mapping", {})
                    }
                    if "header" in node:
                        node_config["header"] = node["header"]
                    nodes_config.append(node_config)

                # Prepare relationships configuration
                relationships_config = []
                for rel in relationships:
                    rel_config = {
                        "fileName": f"file:///{file_name}",
                        "type": rel.get("type", ""),
                        "mapping": rel.get("mapping", {})
                    }
                    if "header" in rel:
                        rel_config["header"] = rel["header"]
                    relationships_config.append(rel_config)

                # Execute APOC import
                query = """
                CALL apoc.import.csv($nodes, $relationships, $config)
                """
                result = session.run(query, {
                    "nodes": nodes_config,
                    "relationships": relationships_config,
                    "config": config
                })
                summary = result.consume()
                return Response({
                    "message": "CSV imported successfully",
                    "nodes_created": summary.counters.nodes_created,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set
                }, status=status.HTTP_200_OK)

            elif file_type == 'json':
                # Handle JSON import with APOC
                query = """
                CALL apoc.import.json($file_url, $config)
                """
                result = session.run(query, {
                    "file_url": f"file:///{file_name}",
                    "config": config
                })
                summary = result.consume()
                return Response({
                    "message": "JSON imported successfully",
                    "nodes_created": summary.counters.nodes_created,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set
                }, status=status.HTTP_200_OK)

            elif file_type == 'cypher':
                # Handle Cypher file execution
                with open(file_path, 'r') as cypher_file:
                    cypher_queries = cypher_file.read().split(';')
                    for query in cypher_queries:
                        query = query.strip()
                        if query:
                            session.run(query)
                return Response({"message": "Cypher queries executed successfully"}, 
                                status=status.HTTP_200_OK)

            else:
                return Response({"error": "Invalid file type specified"}, 
                              status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"error": f"Failed to import file: {str(e)}"}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        # Clean up the temporary file
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        if 'driver' in locals():
            driver.close()