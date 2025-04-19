


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
from graph.utility_neo4j import parse_to_graph_with_transformer,run_query

@api_view(['POST'])
def get_possible_relations(request):
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

    # Construct the Cypher query to return relationship type and node labels
    query = f"""
    MATCH (n:{node_type})-[r]-(m)
    WHERE id(n) = $id
    RETURN DISTINCT type(r) AS relationship_type, labels(n) AS start_labels, labels(m) AS end_labels
    """
    parameters = {"id": id}

    try:
        results = run_query(query, parameters, database=settings.NEO4J_DATABASE)
        relationship_types = [
            {
                "name": record["relationship_type"],
                "startNode": record["start_labels"][0],  # Assume primary label is first
                "endNode": record["end_labels"][0]       # Assume primary label is first
            }
            for record in results
        ]
        return Response({"relations": relationship_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def personne_criminal_network(request):
    # Get properties from request body
    properties = request.data.get('properties', {})
    
    if not isinstance(properties, dict) or 'identity' not in properties:
        return Response(
            {"error": "Missing or invalid 'properties'. Must include 'identity'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Simplified Cypher query to return paths, letting the transformer handle the rest
    query = """
    MATCH (context:Personne {identity: $identity})
    CALL apoc.path.expandConfig(context, {
      relationshipFilter: "Proprietaire|Appel_telephone|Impliquer",
      minLevel: 1,
      maxLevel: 5
    })
    YIELD path
    WHERE last(nodes(path)):Affaire
    RETURN path
    """
    
    parameters = {'identity': properties['identity']}
    
    try:
        # Use the graph parser to process the result
        graph_data = parse_to_graph_with_transformer(query, parameters)
        
        # If no nodes are returned, return an empty graph
        if not graph_data["nodes"]:
            return Response({"nodes": [], "edges": []}, status=status.HTTP_200_OK)
        
        return Response(graph_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {"error": f"Error executing query: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def get_node_relationships(request):
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    id = request.data.get('id',12)
    relation_type = request.data.get('relation_type')  # Optional: Filter by specific relation type

    # if not node_type or not id:
    #     return Response(
    #         {"error": "Missing or invalid 'node_type' or 'id'."},
    #         status=status.HTTP_400_BAD_REQUEST,
    #     )

    # Construct the Cypher query dynamically based on provided properties
    parameters = {}
   
    # Base Cypher query with relationships
    query = f"""
    MATCH (n:{node_type})-[r]-(related)
    WHERE  id(n)={id}
    """

    # Add condition to filter by specific relationship type if provided
    if relation_type:
        query += f" AND type(r) = $relation_type"
        parameters['relation_type'] = relation_type

    # Complete the query
    query += """
    RETURN n, r, related
    LIMIT 100
    """

    try:
        # Use the transformer-based parser to get graph data
        graph_data = parse_to_graph_with_transformer(query, parameters)
        print(graph_data)
        return Response(graph_data, status=status.HTTP_200_OK)
    except Exception as e:
        print(e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def get_virtual_relationships(request):
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    id = request.data.get('id')
    virtual_relation = request.data.get('virtual_relation')
    path = request.data.get('path')

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
        LIMIT 100
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