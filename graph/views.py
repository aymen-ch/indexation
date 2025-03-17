from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from datetime import datetime
import uuid
from .utility import fetch_node_types, fetch_node_properties,driver


def run_query(query, params=None):
    with driver.session() as session:
        results = session.run(query, params or {})
        return [record.data() for record in results]

@api_view(['POST'])
def getdata(request):
    # Extract the identity from the request data
    identity = request.data.get('identity')
    print(identity)
    if not identity:
        return Response(
            {"error": "Identity is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        # Define the Cypher query
        query = """
        MATCH (n {identity: $identity}) RETURN n 
        """
        print("nn")

        # Execute the query using the Neo4j driver
        with driver.session() as session:
            results = session.run(query, {"identity": identity})
            records = list(results)  # Convert the result to a list of records

            if not records:
                return Response(
                    {"error": "Node not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Extract the first result (node data)
            node_data = records[0]["n"]
            return Response(node_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
# Execute query using Neo4j driver
@api_view(['GET'])
def get_node_types(request):
    try:
        node_types = fetch_node_types()
        return Response({"node_types": node_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_node_properties(request):
    """
    Endpoint to fetch properties and their types of a specific node type.
    """
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
        # Get data from request body
        node_type = request.data.get('node_type')
        properties = request.data.get('properties', {})
        if not node_type or not isinstance(properties, dict):
            return Response(
                {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Construct the Cypher query dynamically based on provided properties
        match_conditions = []
        parameters = {}
        for key, value in properties.items():
            match_conditions.append(f"n.{key} = ${key}")
            parameters[key] = value

        query = f"""
        MATCH (n:{node_type})
        WHERE {' AND '.join(match_conditions)}
        RETURN n 
        """

        # Debugging logs (optional)
        print("Generated Cypher Query:", query)
        print("Parameters:", parameters)

    
        with driver.session() as session:
            result = session.run(query, parameters)
            nodes = [record['n'] for record in result]  # Extract nodes from the result

        formatted_nodes = []
        for node in nodes:
            # Exclude 'elementId' and 'identity' properties
            filtered_node = {key: value for key, value in dict(node).items() if key not in ['elementId']}
            formatted_nodes.append(filtered_node)

        return Response(
            {"node_type": node_type, "results": formatted_nodes},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def getPersonneCrimes(request):
    if request.method == 'POST':
        try:
            # Extract node IDs from the request body
            data = request.data
            node_ids = data.get('nodeIds', [])  # Expecting a list of node IDs
            print(node_ids)
            if not node_ids:
                return JsonResponse({'error': 'No node IDs provided'}, status=400)

            # Query to count crimes for each "Personne" node
            query = """
            MATCH (p:Personne)-[:Impliquer]-(c:Affaire)
            WHERE p.identity IN $nodeIds
            RETURN p.identity AS nodeId, COUNT(c) AS crimeCount
            """
            params = {'nodeIds': node_ids}

            # Execute the query
            results = run_query(query, params)

            # Format the results into a dictionary {nodeId: crimeCount}
            crime_counts = {result['nodeId']: result['crimeCount'] for result in results}

            # Include nodes with 0 crimes (if needed)
            for node_id in node_ids:
                if node_id not in crime_counts:
                    crime_counts[node_id] = 0

            return JsonResponse(crime_counts, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


@api_view(['POST'])
def get_possible_relations(request):
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    properties = request.data.get('properties', {})

    if not node_type or not isinstance(properties, dict):
        return Response(
            {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Construct the Cypher query dynamically based on provided properties
    match_conditions = []
    parameters = {}
    for key, value in properties.items():
        # Use backticks around property names to handle spaces or special characters
        match_conditions.append(f"n.`{key}` = $`{key}`")
        parameters[key] = value

    # Base Cypher query to fetch distinct relationship types
    query = f"""
    MATCH (n:{node_type})-[r]-()
    WHERE {' AND '.join(match_conditions)}
    RETURN DISTINCT type(r) AS relationship_type
    """

    # Debug: Print the final query and parameters
    query_with_values = query
    for key, value in parameters.items():
        value_str = f"'{value}'" if isinstance(value, str) else str(value)
        query_with_values = query_with_values.replace(f"${key}", value_str)
    print("Final Cypher Query with Substituted Parameters:")
    print(query_with_values)

    try:
        # Execute the query using the Neo4j driver
        with driver.session() as session:
            result = session.run(query, parameters)
            relationship_types = [record["relationship_type"] for record in result]

            return Response({"relations": relationship_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def get_node_relationships(request):
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    properties = request.data.get('properties', {})
    relation_type = request.data.get('relation_type')  # New: Get the specific relation type

    if not node_type or not isinstance(properties, dict):
        return Response(
            {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Construct the Cypher query dynamically based on provided properties
    match_conditions = []
    parameters = {}
    for key, value in properties.items():
        # Use backticks around property names to handle spaces or special characters
        match_conditions.append(f"n.`{key}` = $`{key}`")
        parameters[key] = value

    # Base Cypher query with relationships
    query = f"""
    MATCH (n:{node_type})-[r]-(related)
    WHERE {' AND '.join(match_conditions)}
    """

    # Add condition to filter by specific relationship type if provided
    if relation_type:
        query += f" AND type(r) = $relation_type"
        parameters['relation_type'] = relation_type

    # Complete the query
    query += """
    RETURN n, related, r, type(r) AS relationship, labels(related) AS related_labels
    LIMIT 100
    """

    # Debug: Print the final query and parameters
    query_with_values = query
    for key, value in parameters.items():
        value_str = f"'{value}'" if isinstance(value, str) else str(value)
        query_with_values = query_with_values.replace(f"${key}", value_str)
    print("Final Cypher Query with Substituted Parameters:")
    print(query_with_values)

    try:
        with driver.session() as session:
            result = session.run(query, parameters)  # Execute the query with parameters
            relationships = []
            for record in result:
                node = record["n"]
                related_node = record["related"]
                relationship = record["r"]
                relationship_type = record["relationship"]
                related_labels = record["related_labels"]  # This will contain the list of labels (node types) for the related node

                # Remove 'elementId' and 'identity' from both the main node and the related node
                node_dict = {key: value for key, value in dict(node).items() if key not in ['elementId', 'identity']}
                related_node_dict = {key: value for key, value in dict(related_node).items() if key not in ['elementId']}
                relationship_dict = {key: value for key, value in dict(relationship).items() if key not in ['elementId']}

                relationships.append({
                    "related": {
                        "node_type": list(related_labels)[0],
                        "properties": related_node_dict  # Add the related node without unwanted properties
                    },
                    "relationship": {
                        "identity": relationship_dict.get("identity"),
                        "type": relationship_type,  # Relationship type
                        "properties": relationship_dict  # Relationship properties
                    }
                })

            return Response(relationships, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
