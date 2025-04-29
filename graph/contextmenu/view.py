


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
from graph.utility_neo4j import parse_to_graph_with_transformer,run_query
CONFIG_FILE = os.path.join(settings.BASE_DIR, 'actions.json')
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
def get_available_actions(request):
    # Get node type from request body
    node_type = request.data.get('node_type', None)
   
    if not node_type:
        return Response(
            {"error": "Node type is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Path to the actions configuration file
        with open(CONFIG_FILE, 'r') as file:
            actions_config = json.load(file)

        # Filter actions by node type and include all relevant fields
        available_actions = [
            {
                "id": action.get("id"),  # Include if available
                "name": action["name"],
                "node_type": action["node_type"],
                # "id_field": action.get("id_field", "id"),  # Default to 'id' if not specified
                "query": action["query"],
                "description": action["description"],  # Include if available
                # "created_at": action.get("created_at"),  # Include if available
                # "created_by": action.get("created_by")  # Include if available
            }
            for action in actions_config
            if action["node_type"] == node_type
        ]

        return Response({"actions": available_actions}, status=status.HTTP_200_OK)

    except FileNotFoundError:
        print("Actions configuration file not found")
        return Response(
            {"error": "Actions configuration file not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        print(e)
        return Response(
            {"error": f"Error reading actions configuration: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    


@api_view(['POST'])
def add_action(request):
    try:
        # Validate required fields
        required_fields = ['name', 'description', 'node_type', 'id_field', 'query', 'node_id']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"error": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        new_action = {
            "name": request.data['name'],
            "description": request.data['description'],  # Added description field
            "node_type": request.data['node_type'],
            "id_field": request.data['id_field'],
            "query": request.data['query']
        }
        node_id = request.data['node_id']

        # Step 1: Test the Cypher query
        try:
            query = new_action['query']
            id_field = new_action['id_field']
            parameters = {id_field: int(node_id)}
            graph_data = parse_to_graph_with_transformer(query, parameters)

            # Validate that the query returns nodes, relationships, or paths
            if not graph_data["nodes"] and not graph_data["edges"]:
                return Response(
                    {"error": "Query did not return any nodes, relationships, or paths"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {"error": f"Invalid Cypher query: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Load existing actions
        try:
            with open(CONFIG_FILE, 'r') as file:
                actions_config = json.load(file)
        except FileNotFoundError:
            actions_config = []

        # Check for duplicate action name
        if any(action['name'] == new_action['name'] for action in actions_config):
            return Response(
                {"error": f"Action '{new_action['name']}' already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Append new action
        actions_config.append(new_action)

        # Save updated config
        with open(CONFIG_FILE, 'w') as file:
            json.dump(actions_config, file, indent=2)

        return Response(
            {"message": f"Action '{new_action['name']}' added successfully"},
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        return Response(
            {"error": f"Error adding action: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(['POST'])
def execute_action(request):
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
def personne_criminal_network(request):
    # Get properties from request body
    id = request.data.get('id', None)
    

    # Simplified Cypher query to return paths, letting the transformer handle the rest
    query = """
    MATCH (context:Personne {identity: $id})
    CALL apoc.path.expandConfig(context, {
      relationshipFilter: "Proprietaire|Appel_telephone|Impliquer",
      minLevel: 1,
      maxLevel: 5
    })
    YIELD path
    WHERE last(nodes(path)):Affaire
    RETURN path
    """
    
    parameters = {'identity': id}
    
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
def affaire_in_the_same_region(request):
    # Get properties from request body
    id = request.data.get('id', None)
    print(request.data)
    if not id:
        return Response(
            {"error": "Affaire ID is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Cypher query to find all Affaire nodes in the same Wilaya
    query = """
    MATCH (context:Affaire)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya) WHERE id(context) = $id
    MATCH (w)-[:appartient]-(d2:Daira)-[:appartient]-(c2:Commune)-[:situer]-(u2:Unite)-[:Traiter]-(other:Affaire)
    RETURN other
    """

    parameters = {'id': id}

    try:
        # Assuming parse_to_graph_with_transformer executes the query and transforms results into a graph format
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
def get_virtual_relationships(request):
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