
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from datetime import datetime
import uuid
from django.conf import settings
import neo4j
from graph.utility_neo4j import parse_to_graph_with_transformer, run_query
def fetch_node_types():
    """
    Fetches all distinct node labels from the Neo4j database.
    """
    query = """
    CALL db.labels() YIELD label
    RETURN label
    """
    print("NEO4J_DATABASE &&&", settings.NEO4J_DATABASE)

    try:
        results = run_query(query, database=settings.NEO4J_DATABASE)
        node_types = [{"type": record["label"]} for record in results]
        return node_types
    except Exception as e:
        print(f"Error fetching node types: {str(e)}")
        return []
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
        results = run_query(query, database=settings.NEO4J_DATABASE)
        nodes = [record["n"] for record in results]

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
    except Exception as e:
        print(f"Error fetching node properties: {str(e)}")
        return []
    finally:
        print("")


@api_view(['GET'])
def get_node_types(request):
    try:
        node_types = fetch_node_types()
        return Response({"node_types": node_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_node_properties(request):
    node_type = request.GET.get('node_type', '')
    if not node_type:
        return Response(
            {"error": "Missing required parameter 'node_type'"},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        properties = fetch_node_properties(node_type)
        return Response(
            {"node_type": node_type, "properties": properties},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
def search_nodes(request):
    try:
        node_type = request.data.get('node_type')
        search_payload = request.data.get('properties', {})
        print(search_payload)
        if not node_type or not isinstance(search_payload, dict):
            return Response(
                {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
                status=status.HTTP_400_BAD_REQUEST
            )
        values = search_payload.get('values', {})
        operations = search_payload.get('operations', {})
        if not isinstance(values, dict) or not isinstance(operations, dict):
            return Response(
                {"error": "'properties' must contain 'values' and 'operations' dictionaries."},
                status=status.HTTP_400_BAD_REQUEST
            )
        match_conditions = []
        parameters = {}
        for key, value in values.items():
            if value is None or value == '':
                continue
            operation = operations.get(key, '=')
            if operation == '=':
                match_conditions.append(f"n.{key} = ${key}")
                parameters[key] = value
            elif operation == '!=':
                match_conditions.append(f"n.{key} <> ${key}")
                parameters[key] = value
            elif operation in ['>', '<', '>=', '<=']:
                match_conditions.append(f"n.{key} {operation} ${key}")
                parameters[key] = value
            elif operation == 'contains':
                match_conditions.append(f"n.{key} CONTAINS ${key}")
                parameters[key] = str(value)
            elif operation == 'startswith':
                match_conditions.append(f"n.{key} STARTS WITH ${key}")
                parameters[key] = str(value)
            elif operation == 'endswith':
                match_conditions.append(f"n.{key} ENDS WITH ${key}")
                parameters[key] = str(value)
            else:
                return Response(
                    {"error": f"Unsupported operation '{operation}' for property '{key}'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if not match_conditions:
            query = f"MATCH (n:{node_type}) RETURN n"
        else:
            query = f"""
            MATCH (n:{node_type})
            WHERE {' AND '.join(match_conditions)}
            RETURN n
            """
        print(query)
        graph_data = parse_to_graph_with_transformer(query, parameters)
        return Response(graph_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
def recherche(request):
    search_value = request.data.get('query')
    print(f"Search query: {search_value}")
    
    if not search_value:
        return Response(
            {"error": "Search value is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Step 1: Handle node full-text indexes
        index_count_query = """
        SHOW FULLTEXT INDEXES
        YIELD name, type, entityType
        WHERE entityType = 'NODE'
        RETURN count(name) AS index_count, collect(name) AS index_names
        """
        index_results = run_query(index_count_query, database=settings.NEO4J_DATABASE)
        index_record = index_results[0] if index_results else {}
        node_index_count = index_record.get("index_count", 0)
        node_index_names = index_record.get("index_names", [])

        label_count_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH DISTINCT label
        RETURN count(label) AS label_count, collect(label) AS labels
        """
        label_results = run_query(label_count_query, database=settings.NEO4J_DATABASE)
        label_record = label_results[0] if label_results else {}
        label_count = label_record.get("label_count", 0)
        all_labels = label_record.get("labels", [])

        if node_index_count < label_count:
            existing_index_labels = [name.replace("index_", "") for name in node_index_names]
            missing_labels = [label for label in all_labels if label not in existing_index_labels]

            for label in missing_labels:
                properties_query = f"""
                MATCH (n:{label})
                UNWIND keys(n) AS property
                RETURN collect(DISTINCT property) AS properties
                """
                prop_results = run_query(properties_query, database=settings.NEO4J_DATABASE)
                prop_record = prop_results[0] if prop_results else {}
                properties = prop_record.get("properties", [])

                if properties:
                    property_list = ", ".join([f"n.`{prop}`" for prop in properties])
                    create_index_query = f"""
                    CREATE FULLTEXT INDEX index_{label} IF NOT EXISTS
                    FOR (n:{label}) ON EACH [{property_list}]
                    OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'standard-no-stop-words' }} }}
                    """
                    run_query(create_index_query, database=settings.NEO4J_DATABASE)
                    print(f"Created node index for {label}: {create_index_query}")

            updated_node_results = run_query(index_count_query, database=settings.NEO4J_DATABASE)
            updated_node_record = updated_node_results[0] if updated_node_results else {}
            node_index_names = updated_node_record.get("index_names", [])

        # Step 2: Handle relationship full-text indexes
        rel_index_count_query = """
        SHOW FULLTEXT INDEXES
        YIELD name, type, entityType
        WHERE entityType = 'RELATIONSHIP'
        RETURN count(name) AS rel_index_count, collect(name) AS rel_index_names
        """
        rel_index_results = run_query(rel_index_count_query, database=settings.NEO4J_DATABASE)
        rel_index_record = rel_index_results[0] if rel_index_results else {}
        rel_index_count = rel_index_record.get("rel_index_count", 0)
        rel_index_names = rel_index_record.get("rel_index_names", [])

        rel_type_count_query = """
        MATCH ()-[r]->()
        WITH DISTINCT type(r) AS rel_type
        RETURN count(rel_type) AS rel_type_count, collect(rel_type) AS rel_types
        """
        rel_type_results = run_query(rel_type_count_query, database=settings.NEO4J_DATABASE)
        rel_type_record = rel_type_results[0] if rel_type_results else {}
        rel_type_count = rel_type_record.get("rel_type_count", 0)
        all_rel_types = rel_type_record.get("rel_types", [])

        if rel_index_count < rel_type_count:
            existing_rel_indexes = [name for name in rel_index_names]
            for rel_type in all_rel_types:
                index_name = f"index_{rel_type.lower()}_rel"
                if index_name not in existing_rel_indexes:
                    rel_properties_query = f"""
                    MATCH ()-[r:{rel_type}]->()
                    UNWIND keys(r) AS property
                    RETURN collect(DISTINCT property) AS properties
                    """
                    rel_prop_results = run_query(rel_properties_query, database=settings.NEO4J_DATABASE)
                    rel_prop_record = rel_prop_results[0] if rel_prop_results else {}
                    rel_properties = rel_prop_record.get("properties", [])

                    if rel_properties:
                        rel_property_list = ", ".join([f"r.`{prop}`" for prop in rel_properties])
                        create_rel_index_query = f"""
                        CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
                        FOR ()-[r:{rel_type}]-() ON EACH [{rel_property_list}]
                        OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'standard-no-stop-words' }} }}
                        """
                        run_query(create_rel_index_query, database=settings.NEO4J_DATABASE)
                        print(f"Created relationship index for {rel_type}: {create_rel_index_query}")

            updated_rel_results = run_query(rel_index_count_query, database=settings.NEO4J_DATABASE)
            updated_rel_record = updated_rel_results[0] if updated_rel_results else {}
            rel_index_names = updated_rel_record.get("rel_index_names", [])

        # Step 3: Check if there are any indexes to search
        if not node_index_names and not rel_index_names:
            return Response(
                {"error": "No full-text indexes available for search."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Step 4: Search nodes and relationships with full-text capabilities
        search_query = ""
        if node_index_names:
            search_query += """
            UNWIND $node_index_names AS node_index_name
            CALL db.index.fulltext.queryNodes(node_index_name, $search_value) YIELD node, score
            RETURN id(node) AS id, labels(node)[0] AS type, properties(node) AS properties, score
            """
        if rel_index_names:
            if node_index_names:
                search_query += " UNION "
            search_query += """
            UNWIND $rel_index_names AS rel_index_name
            CALL db.index.fulltext.queryRelationships(rel_index_name, $search_value) YIELD relationship, score
            RETURN id(relationship) AS id, type(relationship) AS type, properties(relationship) AS properties, score
            """

        if not search_query:
            return Response(
                {"error": "No search query generated."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Enhance search_value for broader matching if needed
        if not any(c in search_value for c in ['*', '?', '"', '+', '-', 'AND', 'OR', 'NOT']):
            search_value = f"{search_value}*"  # Add wildcard for partial matching

        results = run_query(search_query, {
            "search_value": search_value,
            "node_index_names": node_index_names,
            "rel_index_names": rel_index_names
        }, database=settings.NEO4J_DATABASE)

        # Step 5: Process results into a response
        response_data = [
            {
                "id": record["id"],
                "properties": {
                    **record["properties"],  # Include all existing properties
                    "type": record["type"],  # Add type as a property
                    "score": record["score"]  # Add score as a property
                }
            }
            for record in results
        ]
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )