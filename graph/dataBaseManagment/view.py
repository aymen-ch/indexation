
from ..utility import driver, get_neo4j_driver
import os
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from neo4j import GraphDatabase
from django.conf import settings


@api_view(['GET'])
def get_database_stats_view(request):
    """
    API endpoint to get counts of nodes, relationships, labels, relationship types, and property keys.
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query for counts
            queries = {
                "nodes": "MATCH (n) RETURN COUNT(n) AS count",
                "relationships": "MATCH ()-[r]->() RETURN COUNT(r) AS count",
                "labels": "CALL db.labels() YIELD label RETURN COUNT(label) AS count",
                "relationship_types": "CALL db.relationshipTypes() YIELD relationshipType RETURN COUNT(relationshipType) AS count",
                "property_keys": "CALL db.propertyKeys() YIELD propertyKey RETURN COUNT(propertyKey) AS count",
            }

            stats = {}
            for key, query in queries.items():
                result = session.run(query)
                stats[key] = result.single()["count"]

            return Response({
                "nodes": stats["nodes"],
                "relationships": stats["relationships"],
                "labels": stats["labels"],
                "relationship_types": stats["relationship_types"],
                "property_keys": stats["property_keys"],
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def get_current_database_view(request):
    """
    API endpoint to get the current database name.
    POST request (no body required).
    """
    print("NEO4J_DATABASE" ,settings.NEO4J_DATABASE)
    # driver = get_neo4j_driver()
    try:
        # query = "CALL db.info() YIELD name RETURN name"
        # with driver.session(database=settings.NEO4J_DATABASE) as session:
            # result = session.run(query)
            # db_name = result.single()["name"]
            return Response({"current_database": settings.NEO4J_DATABASE}, status=status.HTTP_200_OK)
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
    

@api_view(['DELETE'])
def delete_database_view(request):
    """
    API endpoint to delete a database.
    DELETE request body: {"db_name": "your_database_name"}
    """
    db_name = request.data.get("db_name")
    if not db_name:
        return Response({"error": "db_name is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        query = f"DROP DATABASE {db_name}"
        with driver.session(database="system") as session:
            session.run(query)
            return Response({"message": f"Database '{db_name}' deleted successfully"}, status=status.HTTP_200_OK)
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




@api_view(['POST'])
def import_file_to_neo4j_view(request):
    """
    API endpoint to import JSON files into Neo4j.
    POST request body (form-data):
    - json_file: Required JSON file
    - file_type: Optional (must be 'json') - if not provided, inferred from extension
    - config: Optional JSON string for APOC configuration
    """
    print("Starting import_file_to_neo4j_view")
    # Check if JSON file is provided
    if 'json_file' not in request.FILES:
        print("No JSON file provided in request")
        return Response({"error": "No JSON file provided"}, status=status.HTTP_400_BAD_REQUEST)

    file_type = request.data.get('file_type', '').lower()
    print(f"File type received: {file_type}")
    uploaded_files = {
        'json_file': request.FILES.get('json_file'),
    }
    print(f"Uploaded files: {[(k, v.name if v else None) for k, v in uploaded_files.items()]}")

    # Infer file type if not provided
    if not file_type:
        print("Inferring file type")
        if uploaded_files['json_file']:
            file_type = 'json'
        else:
            print("No supported file type detected")
            return Response({"error": "Unsupported file type. Use .json"},
                            status=status.HTTP_400_BAD_REQUEST)
        print(f"Inferred file type: {file_type}")

    # Validate file type
    if file_type != 'json':
        print(f"Invalid file type: {file_type}")
        return Response({"error": "Invalid file type. Only JSON is supported"},
                        status=status.HTTP_400_BAD_REQUEST)

    # Parse JSON configuration
    try:
        config = json.loads(request.data.get('config', '{}'))
        print("JSON configuration parsed successfully")
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

        # Process JSON file
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            print("Processing JSON file type")
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
                    with open(json_file_path, 'r', encoding='utf-8-sig') as f:
                        sample_content = f.read(1024)  # Read first 1KB
                        print(f"Sample JSON file content: {sample_content[:100]}...")
                except Exception as e:
                    print(f"Error reading JSON file: {str(e)}")
            else:
                print(f"JSON file does not exist at: {json_file_path}")

            # Extract labels for constraints
            labels = set()
            try:
                with open(json_file_path, 'r', encoding='utf-8-sig') as file_handle:
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
            documentation = f"CALL apoc.import.json('file://{json_file.name}', $config)"
            print(f"Executing APOC JSON import: {documentation}")
            try:
                result = session.run(documentation, config=config)
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

    except Exception as e:
        print(f"Unexpected error during import: {str(e)}")
        return Response({"error": f"Failed to import file: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        # Clean up saved files
        for file_path in saved_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Cleaned up file: {file_path}")
            except Exception as e:
                print(f"Error cleaning up file {file_path}: {str(e)}")

        # Close Neo4j driver
        if 'driver' in locals():
            driver.close()
            print("Neo4j driver closed")