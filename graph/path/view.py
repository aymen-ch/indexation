
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from datetime import datetime
import uuid
from graph.views import run_query

##################################################################################################################################

@api_view(['POST'])
def get_all_connections4(request):
    """
    Endpoint to fetch all paths between two specific nodes with a specified depth using APOC.
    Returns a table of paths, where each path contains all the node IDs, labels, properties,
    and relationships with their properties.
    """
    node_ids = request.data.get('ids', [])  # Get the list of node IDs
    depth = request.data.get('depth', 3)    # Get the depth, default to 3 if not provided

    # Ensure exactly two node IDs are provided
    if not isinstance(node_ids, list) or len(node_ids) != 2:
        return JsonResponse({'error': 'Exactly two node IDs must be provided'}, status=400)

    # Ensure node_ids is a list of integers
    try:
        node_ids = [int(node_id) for node_id in node_ids]
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid node IDs provided'}, status=400)

    # Ensure depth is a valid integer
    try:
        depth = int(depth)
        if depth < 1:
            return JsonResponse({'error': 'Depth must be a positive integer'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid depth provided'}, status=400)

    # Cypher query using apoc.path.expandConfig
    query = """
    MATCH (startNode) WHERE id(startNode) = $start_id
    MATCH (endNode) WHERE id(endNode) = $end_id
    CALL apoc.path.expandConfig(startNode, {
        terminatorNodes: [endNode],
        minLevel: 1,
        maxLevel: $depth,
        uniqueness: 'NODE_PATH'  // Ensures nodes aren't repeated in a single path
    }) YIELD path
    RETURN 
        [node IN nodes(path) | {identity: id(node), labels: labels(node), properties: properties(node)}] AS nodes,
        [r IN relationships(path) | {source: id(startNode(r)), target: id(endNode(r)), type: type(r), properties: properties(r)}] AS relationships
    """
    params = {
        'start_id': node_ids[0],  # First node ID
        'end_id': node_ids[1],    # Second node ID
        'depth': depth
    }

    try:
        result = run_query(query, params)  # Execute the query

        # Process the result to extract paths
        paths = []
        for record in result:
            # Extract nodes with identity, labels, and properties
            nodes_in_path = [
                {
                    'identity': node['identity'],
                    'type': node['labels'][0] if node['labels'] else 'Unknown',  # Get the first label as the node type
                    'properties': node['properties']  # Include node properties
                }
                for node in record['nodes']
            ]

            # Extract relationships with source, target, type, and properties
            relationships_in_path = [
                {
                    'source': rel['source'],
                    'target': rel['target'],
                    'type': rel['type'],
                    'properties': rel['properties']  # Include relationship properties
                }
                for rel in record['relationships']
            ]

            # Avoid duplicate paths (e.g., A->B and B->A)
            if nodes_in_path[::-1] not in [p['nodes'] for p in paths]:
                paths.append({
                    'nodes': nodes_in_path,
                    'relationships': relationships_in_path
                })

        # Remove paths with the same set of node IDs
        unique_paths = []
        seen_node_sequences = set()
        for path in paths:
            node_sequence = tuple(sorted(node['identity'] for node in path['nodes']))
            if node_sequence not in seen_node_sequences:
                seen_node_sequences.add(node_sequence)
                unique_paths.append(path)


        return JsonResponse({'paths': unique_paths}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

############################  for  two nodes need to be fixed couse of multiple same relation  between two nodes######################################
@api_view(['POST'])
def get_all_connections(request):
    """
    Endpoint to fetch all paths between two specific nodes with a specified depth.
    Returns a table of paths, where each path contains all the node IDs, labels, properties,
    and relationships with their properties.
    """
    node_ids = request.data.get('ids', [])  # Get the list of node IDs
    depth = request.data.get('depth', 3)  # Get the depth, default to 3 if not provided

    # Ensure exactly two node IDs are provided
    if not isinstance(node_ids, list) or len(node_ids) != 2:
        return JsonResponse({'error': 'Exactly two node IDs must be provided'}, status=400)

    # Ensure node_ids is a list of integers
    try:
        node_ids = [int(node_id) for node_id in node_ids]
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid node IDs provided'}, status=400)

    # Ensure depth is a valid integer
    try:
        depth = int(depth)
        if depth < 1:
            return JsonResponse({'error': 'Depth must be a positive integer'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid depth provided'}, status=400)

    # Cypher query to find all paths between the two nodes with the specified depth
    query = f"""
    MATCH path = (startNode)-[rels*1..{depth}]-(endNode)
    WHERE startNode.identity = $start_id AND endNode.identity = $end_id
    RETURN 
        [node IN nodes(path) | {{identity: node.identity, labels: labels(node), properties: properties(node)}}] AS nodes, 
        [r IN relationships(path) | {{source: startNode(r).identity, target: endNode(r).identity, type: type(r), properties: properties(r)}}] AS relationships
    """
    params = {
        'start_id': node_ids[0],  # First node ID
        'end_id': node_ids[1],    # Second node ID
    }

    try:

        result = run_query(query, params)  # Execute the query

        # Debugging: Print the result to check its structure
        # print("Query Result:", result)
        print("param : " , params)
        print("Query :", query)

        # Process the result to extract paths
        paths = []
        for record in result:
            # Extract nodes with identity, labels, and properties
            nodes_in_path = [
                {
                    'identity': node['identity'],
                    'type': node['labels'][0] if node['labels'] else 'Unknown',  # Get the first label as the node type
                    'properties': node['properties']  # Include node properties
                }
                for node in record['nodes']
            ]

            # Extract relationships with source, target, type, and properties
            relationships_in_path = [
                {
                    'source': rel['source'],
                    'target': rel['target'],
                    'type': rel['type'],
                    'properties': rel['properties']  # Include relationship properties
                }
                for rel in record['relationships']
            ]

            # Check if any node appears more than once in the path
            node_identities = [node['identity'] for node in nodes_in_path]
            if len(node_identities) == len(set(node_identities)):  # No duplicates
                # Avoid duplicate paths (e.g., A->B and B->A)
                if nodes_in_path[::-1] not in [p['nodes'] for p in paths]:
                    paths.append({
                        'nodes': nodes_in_path,
                        'relationships': relationships_in_path
                    })

        # Remove paths with the same set of node IDs
        unique_paths = []
        seen_node_sequences = set()
        for path in paths:
            node_sequence = tuple(sorted(node['identity'] for node in path['nodes']))
            if node_sequence not in seen_node_sequences:
                seen_node_sequences.add(node_sequence)
                unique_paths.append(path)

        return JsonResponse({'paths': unique_paths}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


############################  for nodes > 2  it return one path as subgraphe that conenct all the specified nodes ######################################
@api_view(['POST'])
def get_all_connections2(request):
    """
    Endpoint to fetch a single subgraph that connects all the selected nodes.
    Returns a single path containing all the node IDs, labels, properties,
    and relationships with their properties.
    """
    node_ids = request.data.get('ids', [])  # Get the list of node IDs
    depth = request.data.get('depth', 3)  # Get the depth, default to 3 if not provided

    # Ensure at least two node IDs are provided
    if not isinstance(node_ids, list) or len(node_ids) < 2:
        return JsonResponse({'error': 'At least two node IDs must be provided'}, status=400)

    # Ensure node_ids is a list of integers
    try:
        node_ids = [int(node_id) for node_id in node_ids]
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid node IDs provided'}, status=400)

    # Ensure depth is a valid integer
    try:
        depth = int(depth)
        if depth < 1:
            return JsonResponse({'error': 'Depth must be a positive integer'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid depth provided'}, status=400)

    # Cypher query to find a subgraph that connects all the selected nodes
    query = """
    MATCH path = (startNode)-[rels*1..6]-(endNode)
    WHERE startNode.identity IN $node_ids AND endNode.identity IN $node_ids
    WITH collect(path) AS paths
    UNWIND paths AS singlePath
    WITH singlePath, reduce(connectedNodes = [], node IN nodes(singlePath) | connectedNodes + node.identity) AS nodeIdentities
    WHERE all(nodeId IN $node_ids WHERE nodeId IN nodeIdentities)
    RETURN 
        [node IN nodes(singlePath) | {identity: node.identity, labels: labels(node), properties: properties(node)}] AS nodes, 
        [r IN relationships(singlePath) | {source: startNode(r).identity, target: endNode(r).identity, type: type(r), properties: properties(r)}] AS relationships
    LIMIT 1
    """
    params = {
        'node_ids': node_ids
    }

    try:
        result = run_query(query, params)  # Execute the query

        # Debugging: Print the result to check its structure
        print("Query Result:", result)

        if result:
            # Extract nodes and relationships from the first (and only) result
            record = result[0]
            nodes_in_path = [
                {
                    'identity': node['identity'],
                    'type': node['labels'][0] if node['labels'] else 'Unknown',  # Get the first label as the node type
                    'properties': node['properties']  # Include node properties
                }
                for node in record['nodes']
            ]

            relationships_in_path = [
                {
                    'source': rel['source'],
                    'target': rel['target'],
                    'type': rel['type'],
                    'properties': rel['properties']  # Include relationship properties
                }
                for rel in record['relationships']
            ]

            return JsonResponse({'paths': [{'nodes': nodes_in_path, 'relationships': relationships_in_path}]}, status=200)
        else:
            return JsonResponse({'error': 'No subgraph found connecting all nodes'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
  