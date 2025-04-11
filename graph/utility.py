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


# views.py
import os
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from neo4j import GraphDatabase


@api_view(['POST'])
def import_file_to_neo4j_view(request):
    """
    API endpoint to import files into Neo4j.
    POST request body (form-data):
    - nodes_file: Optional CSV file for nodes
    - relationships_file: Optional CSV file for relationships
    - json_file: Optional JSON file
    - cypher_file: Optional Cypher file
    - file_type: Optional (csv, json, cypher) - if not provided, inferred from extension
    - config: Optional JSON string for APOC configuration (for CSV/JSON)
    - nodes: Optional JSON string of node mappings (for CSV)
    - relationships: Optional JSON string of relationship mappings (for CSV)
    """
    print("Starting import_file_to_neo4j_view")
    # Check if at least one file is provided
    if not any(key in request.FILES for key in ['nodes_file', 'relationships_file', 'json_file', 'cypher_file']):
        print("No file provided in request")
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    file_type = request.data.get('file_type', '').lower()
    print(f"File type received: {file_type}")
    uploaded_files = {
        'nodes_file': request.FILES.get('nodes_file'),
        'relationships_file': request.FILES.get('relationships_file'),
        'json_file': request.FILES.get('json_file'),
        'cypher_file': request.FILES.get('cypher_file'),
    }
    print(f"Uploaded files: {[(k, v.name if v else None) for k, v in uploaded_files.items()]}")

    # Infer file type if not provided
    if not file_type:
        print("Inferring file type")
        if uploaded_files['nodes_file'] or uploaded_files['relationships_file']:
            file_type = 'csv'
        elif uploaded_files['json_file']:
            file_type = 'json'
        elif uploaded_files['cypher_file']:
            file_type = 'cypher'
        else:
            print("No supported file type detected")
            return Response({"error": "Unsupported file type. Use .csv, .json, or .cypher"},
                            status=status.HTTP_400_BAD_REQUEST)
        print(f"Inferred file type: {file_type}")

    # Parse JSON configurations
    try:
        nodes_config_input = json.loads(request.data.get('nodes', '[]'))
        relationships_config_input = json.loads(request.data.get('relationships', '[]'))
        config = json.loads(request.data.get('config', '{}'))
        print("JSON configurations parsed successfully")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return Response({"error": f"Invalid JSON configuration: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get the import directory path from Neo4j
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("CALL dbms.listConfig('server.directories.import') YIELD value RETURN value AS importDirectoryPath")
            import_dir = result.single()["importDirectoryPath"]
            print(f"Neo4j import directory: {import_dir}")

        saved_files = []
        nodes_created = 0
        relationships_created = 0
        properties_set = 0

        # Process based on file type
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            if file_type == 'csv':
                print("Processing CSV file type")
                nodes_config = []
                relationships_config = []

                # Save nodes file if provided
                if uploaded_files['nodes_file']:
                    nodes_file = uploaded_files['nodes_file']
                    nodes_file_path = os.path.join(import_dir, nodes_file.name)
                    print(f"Saving nodes file to: {nodes_file_path}")
                    try:
                        with open(nodes_file_path, 'wb+') as destination:
                            for chunk in nodes_file.chunks():
                                destination.write(chunk)
                        saved_files.append(nodes_file_path)
                        print(f"Nodes file saved: {nodes_file_path}")
                    except Exception as e:
                        print(f"Error saving nodes file: {str(e)}")
                        return Response({"error": f"Failed to save nodes file: {str(e)}"},
                                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    # Prepare nodes configuration
                    for node in nodes_config_input:
                        node_config = {
                            "fileName": f"file:///{nodes_file.name}",
                            "labels": node.get("labels", []),
                            "mapping": node.get("mapping", {})
                        }
                        if "header" in node:
                            node_config["header"] = node["header"]
                        nodes_config.append(node_config)
                    print(f"Nodes configuration: {nodes_config}")

                # Save relationships file if provided
                if uploaded_files['relationships_file']:
                    rels_file = uploaded_files['relationships_file']
                    rels_file_path = os.path.join(import_dir, rels_file.name)
                    print(f"Saving relationships file to: {rels_file_path}")
                    try:
                        with open(rels_file_path, 'wb+') as destination:
                            for chunk in rels_file.chunks():
                                destination.write(chunk)
                        saved_files.append(rels_file_path)
                        print(f"Relationships file saved: {rels_file_path}")
                    except Exception as e:
                        print(f"Error saving relationships file: {str(e)}")
                        return Response({"error": f"Failed to save relationships file: {str(e)}"},
                                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    # Prepare relationships configuration
                    for rel in relationships_config_input:
                        rel_config = {
                            "fileName": f"file:///{rels_file.name}",
                            "type": rel.get("type", ""),
                            "mapping": rel.get("mapping", {})
                        }
                        if "header" in rel:
                            rel_config["header"] = rel["header"]
                        relationships_config.append(rel_config)
                    print(f"Relationships configuration: {relationships_config}")

                # Execute APOC import if either nodes or relationships are provided
                if nodes_config or relationships_config:
                    query = """
                    CALL apoc.import.csv($nodes, $relationships, $config)
                    """
                    print(f"Executing APOC CSV import query: {query}")
                    result = session.run(query, {
                        "nodes": nodes_config,
                        "relationships": relationships_config,
                        "config": config
                    })
                    summary = result.consume()
                    nodes_created = summary.counters.nodes_created
                    relationships_created = summary.counters.relationships_created
                    properties_set = summary.counters.properties_set
                    print(f"CSV import results: nodes_created={nodes_created}, relationships_created={relationships_created}, properties_set={properties_set}")

                return Response({
                    "message": "CSV imported successfully",
                    "nodes_created": nodes_created,
                    "relationships_created": relationships_created,
                    "properties_set": properties_set
                }, status=status.HTTP_200_OK)

            elif file_type == 'json':
                print("Processing JSON file type")
                if not uploaded_files['json_file']:
                    print("No JSON file provided in request")
                    return Response({"error": "No JSON file provided"},
                                    status=status.HTTP_400_BAD_REQUEST)

                json_file = uploaded_files['json_file']
                json_file_path = os.path.join(import_dir, json_file.name)
                print(f"Attempting to save JSON file to: {json_file_path}")
                try:
                    with open(json_file_path, 'wb+') as destination:
                        print(f"Writing chunks for JSON file: {json_file.name}")
                        for chunk in json_file.chunks():
                            destination.write(chunk)
                            print(f"Wrote chunk of size: {len(chunk)}")
                    saved_files.append(json_file_path)
                    print(f"JSON file saved successfully: {json_file_path}")
                except Exception as e:
                    print(f"Error saving JSON file: {str(e)}")
                    return Response({"error": f"Failed to save JSON file: {str(e)}"},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Verify file exists and is readable
                if os.path.exists(json_file_path):
                    print(f"Confirmed JSON file exists at: {json_file_path}")
                    try:
                        with open(json_file_path, 'r') as f:
                            sample_content = f.read(1024)  # Read first 1KB
                            print(f"Sample JSON file content: {sample_content[:100]}...")
                    except Exception as e:
                        print(f"Error reading JSON file: {str(e)}")
                else:
                    print(f"JSON file does not exist at: {json_file_path}")

                # Extract labels for constraints
                labels = set()
                try:
                    with open(json_file_path, 'r') as file_handle:  # Changed variable name to avoid overwriting json_file
                        lines = file_handle.readlines()
                        print(f"Read {len(lines)} lines from JSON file")
                        for i, line in enumerate(lines):
                            try:
                                data = json.loads(line)
                                print(f"Processing JSON line {i+1}: {line[:50]}...")
                                if data.get('type') == 'node' and 'labels' in data:
                                    for label in data['labels']:
                                        labels.add(label)
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error on line {i+1}: {str(e)}")
                                continue
                except Exception as e:
                    print(f"Error reading JSON file for labels: {str(e)}")
                    return Response({"error": f"Failed to read JSON file: {str(e)}"},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Create constraints
                print(f"Creating constraints for labels: {labels}")
                for label in labels:
                    try:
                        constraint_query = f"""
                        CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.neo4jImportId IS UNIQUE
                        """
                        session.run(constraint_query)
                        print(f"Constraint created for label: {label}")
                    except Exception as e:
                        print(f"Error creating constraint for label {label}: {str(e)}")
                        return Response({
                            "error": f"Failed to create constraint for label {label}: {str(e)}"
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Execute APOC JSON import
                documentation = f"CALL apoc.import.json('file://{json_file.name}')"
                print(f"Executing APOC JSON import: {documentation}")
                try:
                    result = session.run(documentation)
                    summary = result.consume()
                    nodes_created = summary.counters.nodes_created
                    relationships_created = summary.counters.relationships_created
                    properties_set = summary.counters.properties_set
                    print(f"JSON import results: nodes_created={nodes_created}, relationships_created={relationships_created}, properties_set={properties_set}")
                except Exception as e:
                    print(f"Error executing APOC JSON import: {str(e)}")
                    return Response({
                        "error": f"Failed to import JSON: {str(e)}"
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                print(f"JSON import completed: nodes_created={nodes_created}, relationships_created={relationships_created}")
                return Response({
                    "message": "JSON imported successfully",
                    "nodes_created": nodes_created,
                    "relationships_created": relationships_created,
                    "properties_set": properties_set,
                    "constraints_created": list(labels)
                }, status=status.HTTP_200_OK)

            elif file_type == 'cypher':
                print("Processing Cypher file type")
                if not uploaded_files['cypher_file']:
                    print("No Cypher file provided")
                    return Response({"error": "No Cypher file provided"},
                                    status=status.HTTP_400_BAD_REQUEST)

                cypher_file = uploaded_files['cypher_file']
                cypher_file_path = os.path.join(import_dir, cypher_file.name)
                print(f"Saving Cypher file to: {cypher_file_path}")
                try:
                    with open(cypher_file_path, 'wb+') as destination:
                        for chunk in cypher_file.chunks():
                            destination.write(chunk)
                    saved_files.append(cypher_file_path)
                    print(f"Cypher file saved: {cypher_file_path}")
                except Exception as e:
                    print(f"Error saving Cypher file: {str(e)}")
                    return Response({"error": f"Failed to save Cypher file: {str(e)}"},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Execute Cypher queries
                print("Executing Cypher queries")
                with open(cypher_file_path, 'r') as cypher_file:
                    cypher_queries = cypher_file.read().split(';')
                    for i, query in enumerate(cypher_queries):
                        query = query.strip()
                        if query:
                            print(f"Executing Cypher query {i+1}: {query[:50]}...")
                            session.run(query)
                return Response({"message": "Cypher queries executed successfully"},
                                status=status.HTTP_200_OK)

            else:
                print(f"Invalid file type: {file_type}")
                return Response({"error": "Invalid file type specified"},
                                status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print(f"Unexpected error during import: {str(e)}")
        return Response({"error": f"Failed to import file: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        # Clean up saved files
       
        if 'driver' in locals():
            driver.close()
            print("Neo4j driver closed")


# @api_view(['POST'])
# def import_file_to_neo4j_view(request):
#     """
#     API endpoint to import a file into Neo4j.
#     POST request body (form-data):
#     - file: The file to upload (CSV, JSON, or Cypher)
#     - file_type: Optional (csv, json, cypher) - if not provided, inferred from extension
#     - config: Optional JSON string for APOC configuration (for CSV/JSON)
#     - nodes: Optional JSON string of node mappings (for CSV)
#     - relationships: Optional JSON string of relationship mappings (for CSV)
#     """
#     # Check if a file is provided
#     if 'file' not in request.FILES:
#         return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

#     uploaded_file = request.FILES['file']
#     file_name = uploaded_file.name
#     file_type = request.data.get('file_type', '').lower()
    
#     # Infer file type from extension if not provided
#     if not file_type:
#         file_extension = os.path.splitext(file_name)[1].lower()
#         if file_extension == '.csv':
#             file_type = 'csv'
#         elif file_extension == '.json':
#             file_type = 'json'
#         elif file_extension == '.cypher':
#             file_type = 'cypher'
#         else:
#             return Response({"error": "Unsupported file type. Use .csv, .json, or .cypher"}, 
#                           status=status.HTTP_400_BAD_REQUEST)

#     # Parse JSON configurations
#     try:
#         nodes = json.loads(request.data.get('nodes', '[]'))
#         relationships = json.loads(request.data.get('relationships', '[]'))
#         config = json.loads(request.data.get('config', '{}'))
#     except json.JSONDecodeError as e:
#         return Response({"error": f"Invalid JSON configuration: {str(e)}"}, 
#                       status=status.HTTP_400_BAD_REQUEST)

#     # # Initialize Neo4j driver
#     # driver = GraphDatabase.driver(
#     #     settings.NEO4J_URI,
#     #     auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
#     # )

#     try:
#         # Get the import directory path from Neo4j
#         with driver.session(database=settings.NEO4J_DATABASE) as session:
#             result = session.run("CALL dbms.listConfig('server.directories.import') YIELD value RETURN value AS importDirectoryPath")
#             import_dir = result.single()["importDirectoryPath"]
            
#         # Save the file to the import directory
#         file_path = os.path.join(import_dir, file_name)
        
#         try:
#             with open(file_path, 'wb+') as destination:
#                 for chunk in uploaded_file.chunks():
#                     destination.write(chunk)
#         except Exception as e:
#             return Response({"error": f"Failed to save file: {str(e)}"}, 
#                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#         # Process the file based on type
#         with driver.session(database=settings.NEO4J_DATABASE) as session:
#             if file_type == 'csv':
#                 # Prepare nodes configuration
#                 nodes_config = []
#                 for node in nodes:
#                     node_config = {
#                         "fileName": f"file:///{file_name}",
#                         "labels": node.get("labels", []),
#                         "mapping": node.get("mapping", {})
#                     }
#                     if "header" in node:
#                         node_config["header"] = node["header"]
#                     nodes_config.append(node_config)

#                 # Prepare relationships configuration
#                 relationships_config = []
#                 for rel in relationships:
#                     rel_config = {
#                         "fileName": f"file:///{file_name}",
#                         "type": rel.get("type", ""),
#                         "mapping": rel.get("mapping", {})
#                     }
#                     if "header" in rel:
#                         rel_config["header"] = rel["header"]
#                     relationships_config.append(rel_config)

#                 # Execute APOC import
#                 query = """
#                 CALL apoc.import.csv($nodes, $relationships, $config)
#                 """
#                 result = session.run(query, {
#                     "nodes": nodes_config,
#                     "relationships": relationships_config,
#                     "config": config
#                 })
#                 summary = result.consume()
#                 return Response({
#                     "message": "CSV imported successfully",
#                     "nodes_created": summary.counters.nodes_created,
#                     "relationships_created": summary.counters.relationships_created,
#                     "properties_set": summary.counters.properties_set
#                 }, status=status.HTTP_200_OK)

#             elif file_type == 'json':
#                 # Handle JSON import with APOC
#                 query = """
#                 CALL apoc.import.json($file_url, $config)
#                 """
#                 result = session.run(query, {
#                     "file_url": f"file:///{file_name}",
#                     "config": config
#                 })
#                 summary = result.consume()
#                 return Response({
#                     "message": "JSON imported successfully",
#                     "nodes_created": summary.counters.nodes_created,
#                     "relationships_created": summary.counters.relationships_created,
#                     "properties_set": summary.counters.properties_set
#                 }, status=status.HTTP_200_OK)

#             elif file_type == 'cypher':
#                 # Handle Cypher file execution
#                 with open(file_path, 'r') as cypher_file:
#                     cypher_queries = cypher_file.read().split(';')
#                     for query in cypher_queries:
#                         query = query.strip()
#                         if query:
#                             session.run(query)
#                 return Response({"message": "Cypher queries executed successfully"}, 
#                                 status=status.HTTP_200_OK)

#             else:
#                 return Response({"error": "Invalid file type specified"}, 
#                               status=status.HTTP_400_BAD_REQUEST)

#     except Exception as e:
#         return Response({"error": f"Failed to import file: {str(e)}"}, 
#                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     finally:
#         # Clean up the temporary file
#         if 'file_path' in locals() and os.path.exists(file_path):
#             try:
#                 os.remove(file_path)
#             except:
#                 pass
#         if 'driver' in locals():
#             driver.close()