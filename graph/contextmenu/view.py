


import json
import os
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
from graph.Utility_QueryExecutors import parse_to_graph_with_transformer,run_query
CONFIG_FILE = os.path.join(settings.BASE_DIR, 'actions.json')
@api_view(['POST'])
def get_possible_relations(request):
    """
    Retrieves a list of possible relations for a given node type and ID.

    This function takes the node type and ID as input, and returns a list of possible relations.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the node type and ID.

    Returns:
        Response: A JSON response with a list of possible relations.

    Raises:
        Exception: If any error occurs during relation retrieval.
    """
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    id = request.data.get('id', 12)

    # Validate input
    if not node_type:
        return Response(
            {"error": "Missing required field: 'node_type'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        id = int(id)  # Ensure id is an integer
    except (TypeError, ValueError):
        return Response(
            {"error": "'id' must be a valid integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Construct the Cypher query to return relationship type, node labels, and count
    query = f"""
    MATCH (n:{node_type})-[r]-(m)
    WHERE id(n) = $id
    RETURN DISTINCT type(r) AS relationship_type, 
                    labels(n) AS start_labels, 
                    labels(m) AS end_labels, 
                    COUNT(r) AS relation_count
    """
    parameters = {"id": id}

    try:
        results = run_query(query, parameters, database=settings.NEO4J_DATABASE)
        relationship_types = [
            {
                "name": record["relationship_type"],
                "startNode": record["start_labels"][0],  # Assume primary label is first
                "endNode": record["end_labels"][0],      # Assume primary label is first
                "count": record["relation_count"]        # Include the count of relations
            }
            for record in results
        ]
        return Response({"relations": relationship_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    



@api_view(['POST'])
def get_virtual_relation_count(request):
    """
    Retrieves the count of virtual relations for a given node type, ID, and path.

    This function takes the node type, ID, and path as input, and returns the count of virtual relations.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the node type, ID, and path.

    Returns:
        Response: A JSON response with the count of virtual relations.

    Raises:
        Exception: If any error occurs during virtual relation count retrieval."""
    
    # Get data from the request body
    data = request.data
    node_type = data.get('node_type')
    node_id = data.get('node_id')
    path = data.get('path')  # e.g., ['phone', 'call', 'phone']

    # Validate input
    if not node_type:
        return Response(
            {"error": "Missing required field: 'node_type'."},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not node_id:
        return Response(
            {"error": "Missing required field: 'node_id'."},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not path or not isinstance(path, list) or len(path) < 3 or len(path) % 2 == 0:
        return Response(
            {"error": "Invalid 'path': must be a non-empty list with odd length (alternating node labels and relationship types)."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        node_id = int(node_id)  # Ensure node_id is an integer
    except (TypeError, ValueError):
        return Response(
            {"error": "'node_id' must be a valid integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Construct the Cypher query for the path
    try:
        # Initialize query components
        nodes = []
        relationships = []
        for i, item in enumerate(path):
            if i % 2 == 0:  # Node labels (e.g., 'phone')
                nodes.append(item)
            else:  # Relationship types (e.g., 'call')
                relationships.append(item)

        # Build the MATCH pattern
        # e.g., for ['phone', 'call', 'phone']: MATCH (n0:phone)-[r0:call]->(n1:phone)
        match_clauses = []
        for i in range(len(nodes) - 1):
            node_label = nodes[i]
            next_node_label = nodes[i + 1]
            rel_type = relationships[i]
            match_clauses.append(f"(n{i}:{node_label})-[r{i}:{rel_type}]->(n{i+1}:{next_node_label})")

        match_pattern = "-".join(match_clauses)
        query = f"""
        MATCH {match_pattern}
        WHERE id(n0) = $node_id
        RETURN COUNT(DISTINCT n1) AS total_count
        """
        print(query)
        parameters = {"node_id": node_id}

        # Run the query
        results = run_query(query, parameters, database=settings.NEO4J_DATABASE)
        total_count = results[0]["total_count"] if results else 0

        return Response({"count": total_count}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# 
@api_view(['POST'])
def execute_action(request):
    """
    Retrieves a list of actions.

    This function takes no input, and returns a list of actions.

    Parameters:
        request (HttpRequest): The HTTP request object.

    Returns:
        Response: A JSON response with a list of actions.

    Raises:
        Exception: If any error occurs during action retrieval.
    """
    # Get action name and node ID from request body
    action_name = request.data.get('action_name', None)
    id = request.data.get('id', None)
    print(request.data)
    if not action_name or id is None:
        return Response(
            {"error": "Action name and node ID are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Path to the actions configuration file

        with open(CONFIG_FILE, 'r') as file:
            actions_config = json.load(file)

        # Find the action by name
        action = next((action for action in actions_config if action["name"] == action_name), None)
        if not action:
            return Response(
                {"error": f"Action '{action_name}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get the query and ID field
        query = action["query"]
        print(query)
        id_field = action["id_field"]

        # Prepare parameters
        parameters = {'id': id}

        # Execute the query using parse_to_graph_with_transformer
        graph_data = parse_to_graph_with_transformer(query, parameters)
        print(graph_data)
        # If no nodes are returned, return an empty graph
        if not graph_data["nodes"]:
            return Response({"nodes": [], "edges": []}, status=status.HTTP_200_OK)

        return Response(graph_data, status=status.HTTP_200_OK)

    except FileNotFoundError:
        return Response(
            {"error": "Actions configuration file not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        print(e)
        return Response(
            {"error": f"Error executing action: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@api_view(['POST'])
def extensibility(request):
    """
    Retrieves a list of relationships for a given node type, ID, and relation type.

    This function takes the node type, ID, relation type, and expand limit as input, and returns a list of relationships.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the node type, ID, relation type, and expand limit.

    Returns:
        Response: A JSON response with a list of relationships.

    Raises:
        Exception: If any error occurs during relationship retrieval.
    """
    print(request.data)
    node_type = request.data.get('node_type')
    id = request.data.get('id', 12)
    relation_type = request.data.get('relation_type')  # Optional
    limit = request.data.get('expandLimit', 100)
    sense = request.data.get('expandDirection', 'In')

    parameters = {'id': id, 'limit': limit}

    # Determine the relationship direction
    if sense == 'In':
        relationship_pattern = "<-[r]-"
    elif sense == 'Out':
        relationship_pattern = "-[r]->"
    else:  # both
        relationship_pattern = "-[r]-"

    # Base Cypher query
    query = f"""
    MATCH (n:{node_type}){relationship_pattern}(related)
    WHERE id(n) = $id
    """

    if relation_type:
        query += " AND type(r) = $relation_type"
        parameters['relation_type'] = relation_type

    query += """
    RETURN n, r, related
    LIMIT $limit
    """
    print(query)
    try:
        graph_data = parse_to_graph_with_transformer(query, parameters)
        print(graph_data)
        return Response(graph_data, status=status.HTTP_200_OK)
    except Exception as e:
        print(e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def extensibilty_virtuel(request):

    """
    Retrieves a list of virtual relationships for a given node type, ID, and path.

    This function takes the node type, ID, virtual relation, and path as input, and returns a list of virtual relationships.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the node type, ID, virtual relation, and path.

    Returns:
        Response: A JSON response with a list of virtual relationships.

    Raises:
        Exception: If any error occurs during virtual relationship retrieval.
    """
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    id = request.data.get('id')
    virtual_relation = request.data.get('virtual_relation')
    path = request.data.get('path')
    limit= request.data.get('limit',100)

    # Validate input
    if not all([node_type, id, virtual_relation, path]):
        return Response(
            {"error": "Missing required fields: 'node_type', 'id', 'virtual_relation', or 'path'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(path, list) or len(path) < 2:
        return Response(
            {"error": "'path' must be a list with at least two elements."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        id = int(id)  # Ensure id is an integer
    except (TypeError, ValueError):
        return Response(
            {"error": "'id' must be a valid integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Ensure the path starts with the node_type
    if path[0] != node_type:
        return Response(
            {"error": f"Path must start with the node type '{node_type}'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get the end node type (last element of the path)
    end_node_type = path[-1]

    # Construct Cypher query dynamically based on the path
    try:
        # Build the MATCH clause for the path
        query_parts = []
        parameters = {"id": id}
        node_vars = [f"n0:{node_type}"]  # Starting node
        rel_vars = []

        # Iterate through the path to build the pattern
        for i in range(1, len(path), 2):  # Step by 2: node, relation, node, ...
            if i + 1 >= len(path):  # Ensure we have a node after the relation
                break
            relation = path[i]
            next_node_type = path[i + 1]
            node_var = f"n{i + 1}:{next_node_type}"
            rel_var = f"r{i}"
            query_parts.append(f"-[{rel_var}:{relation}]-({node_var})")
            node_vars.append(node_var)
            rel_vars.append(rel_var)

        # Calculate the end node variable (last node in the path)
        end_node_index = 2 * len(rel_vars)  # Each relation increments index by 2
        end_node_var = f"n{end_node_index}"

        # Construct the Cypher query to return start and end nodes with IDs
        query = f"""
        MATCH (n0:{node_type}) {"".join(query_parts)}
        WHERE id(n0) = $id
        RETURN id(n0) AS start_id, n0 AS start_node, id({end_node_var}) AS end_id, {end_node_var} AS end_node
        LIMIT {limit}
        """

        # Execute the query using run_query
        results = run_query(query, parameters)

        # Parse results into the desired format
        nodes = {}
        edges = {}
        edge_id_counter = 1  # Simple counter for edge IDs

        for record in results:
            start_id = record["start_id"]
            start_node = record["start_node"]
            end_id = record["end_id"]
            end_node = record["end_node"]

            # Add start node (node_type, e.g., Wilaya)
            if start_id not in nodes:
                nodes[start_id] = {
                    "id": start_id,
                    "nodeType": node_type,
                    "properties": {k: v for k, v in start_node.items()}
                }

            # Add end node (end_node_type, e.g., Personne)
            if end_id and end_id not in nodes:
                nodes[end_id] = {
                    "id": end_id,
                    "nodeType": end_node_type,
                    "properties": {k: v for k, v in end_node.items()}
                }

            # Create a virtual relationship (e.g., impliquer_dans)
            if end_id:
                edges[edge_id_counter] = {
                    "type": virtual_relation,
                    "startNode": start_id,
                    "endNode": end_id,
                    "properties": {}
                }
                edge_id_counter += 1

        # Format the response
        graph_data = {
            "nodes": list(nodes.values()),
            "edges": list(edges.values())
        }
        print(graph_data)
        return Response(graph_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(e)
        return Response({"error": f"Error executing query: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)