
from django.conf import settings
from neo4j import Driver
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from datetime import datetime
import uuid
from graph.views import parse_to_graph_with_transformer, run_query
from graph.utility import driver

##################################################################################################################################
@api_view(['POST'])
def get_all_connections4(request):
    node_ids = request.data.get('ids', [])  # List of node IDs (e.g., [1, 2, 3])
    depth = request.data.get('depth', 1)    # Specific depth level (default: 1)

    if len(node_ids) < 2:
        return JsonResponse({'error': 'At least two node IDs required'}, status=400)

    # Query to find paths at the specified depth
    query = """
    UNWIND $node_ids AS node_id
    MATCH (n) WHERE id(n) = node_id
    WITH collect(n) AS nodes

    UNWIND nodes AS n1
    UNWIND nodes AS n2
    WITH n1, n2
    WHERE id(n1) < id(n2)

    CALL apoc.path.expandConfig(n1, {
        terminatorNodes: [n2],
        minLevel: $depth,
        maxLevel: $depth,
        uniqueness: 'NODE_PATH'
    }) YIELD path

    WITH path, nodes(path) AS pathNodes, relationships(path) AS pathRels
    RETURN 
        [node IN pathNodes | {id: id(node), labels: labels(node), properties: properties(node)}] AS nodes,
        [rel IN pathRels | {source: id(startNode(rel)), target: id(endNode(rel)), type: type(rel), properties: properties(rel), id: id(rel)}] AS relationships
    """

    try:
        result = run_query(query, {'node_ids': node_ids, 'depth': depth})
        
        paths = []
        for record in result:
            nodes_in_path = [
                {
                    'id': node['id'],
                    'type': node['labels'][0] if node['labels'] else 'Unknown',
                    'properties': node['properties']
                }
                for node in record['nodes']
            ]

            relationships_in_path = [
                {
                    'source': rel['source'],
                    'target': rel['target'],
                    'type': rel['type'],
                    'id': str(rel['id']),
                    'properties': rel['properties']
                }
                for rel in record['relationships']
            ]

            paths.append({
                'nodes': nodes_in_path,
                'relationships': relationships_in_path
            })
        
        return JsonResponse({'paths': paths, 'depth': depth}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
def shortestpath(request):
    node_ids = request.data.get('ids', [])  # List of node IDs (e.g., [1, 2, 3])
    
    if len(node_ids) < 2:
        return JsonResponse({'error': 'At least two node IDs required'}, status=400)

    try:
        if len(node_ids) == 2:
            # Query for exactly 2 nodes: return all shortest paths
            query = """
            UNWIND $node_ids AS node_id
            MATCH (n) WHERE id(n) = node_id
            WITH collect(n) AS nodes
            WITH nodes[0] AS n1, nodes[1] AS n2

            MATCH path = shortestPath((n1)-[*]-(n2))
            WHERE n1 <> n2

            WITH path, nodes(path) AS pathNodes, relationships(path) AS pathRels
            RETURN 
                [node IN pathNodes | {id: id(node), labels: labels(node), properties: properties(node)}] AS nodes,
                [rel IN pathRels | {source: id(startNode(rel)), target: id(endNode(rel)), type: type(rel), properties: properties(rel), id: id(rel)}] AS relationships
            """
            result = run_query(query, {'node_ids': node_ids})
            
            paths = []
            for record in result:
                nodes_in_path = [
                    {
                        'id': node['id'],
                        'type': node['labels'][0] if node['labels'] else 'Unknown',
                        'properties': node['properties']
                    }
                    for node in record['nodes']
                ]

            # Extract relationships with source, target, type, and properties
            relationships_in_path = [
                {
                    'source': rel['source'],
                    'target': rel['target'],
                    'type': rel['type'],
                    'id':str( rel['id'] ),  # Include relationship properties,
                    'properties':rel['properties']
                }
                for rel in record['relationships']
            ]

            paths.append({
                    'nodes': nodes_in_path,
                    'relationships': relationships_in_path
                })
            
            return JsonResponse({'paths': paths}, status=200)
        
        else:
            # Query for more than 2 nodes: find the shortest path connecting all nodes
            query = """
            UNWIND $node_ids AS node_id
            MATCH (n) WHERE id(n) = node_id
            WITH collect(n) AS target_nodes
            MATCH path = shortestPath((start)-[*]-(end))
            WHERE start IN target_nodes AND end IN target_nodes
            AND all(n IN target_nodes WHERE n IN nodes(path))
            WITH path, nodes(path) AS pathNodes, relationships(path) AS pathRels
            RETURN 
                [node IN pathNodes | {id: id(node), labels: labels(node), properties: properties(node)}] AS nodes,
                [rel IN pathRels | {source: id(startNode(rel)), target: id(endNode(rel)), type: type(rel), properties: properties(rel), id: id(rel)}] AS relationships
            LIMIT 1
            """
            result = run_query(query, {'node_ids': node_ids})
            
            paths = []
            for record in result:
                nodes_in_path = [
                    {
                        'id': node['id'],
                        'type': node['labels'][0] if node['labels'] else 'Unknown',
                        'properties': node['properties']
                    }
                    for node in record['nodes']
                ]

                relationships_in_path = [
                    {
                        'source': rel['source'],
                        'target': rel['target'],
                        'type': rel['type'],
                        'id': str (rel['id']),
                        'properties': rel['properties']
                    }
                    for rel in record['relationships']
                ]

                paths.append({
                    'nodes': nodes_in_path,
                    'relationships': relationships_in_path
                })
            
            return JsonResponse({'paths': paths}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

############################  for nodes > 2  it return one path as subgraphe that conenct all the specified nodes ######################################
# @api_view(['POST'])
# def get_all_connections2(request):
#     """
#     Endpoint to fetch a single subgraph that connects all the selected nodes.
#     Returns a single path containing all the node IDs, labels, properties,
#     and relationships with their properties.
#     """
#     node_ids = request.data.get('ids', [])  # Get the list of node IDs
#     depth = request.data.get('depth', 3)  # Get the depth, default to 3 if not provided

#     # Ensure at least two node IDs are provided
#     if not isinstance(node_ids, list) or len(node_ids) < 2:
#         return JsonResponse({'error': 'At least two node IDs must be provided'}, status=400)

#     # Ensure node_ids is a list of integers
#     try:
#         node_ids = [int(node_id) for node_id in node_ids]
#     except (ValueError, TypeError):
#         return JsonResponse({'error': 'Invalid node IDs provided'}, status=400)

#     # Ensure depth is a valid integer
#     try:
#         depth = int(depth)
#         if depth < 1:
#             return JsonResponse({'error': 'Depth must be a positive integer'}, status=400)
#     except (ValueError, TypeError):
#         return JsonResponse({'error': 'Invalid depth provided'}, status=400)

#     # Cypher query to find a subgraph that connects all the selected nodes
#     query = """
#     MATCH path = (startNode)-[rels*1..6]-(endNode)
#     WHERE startNode.identity IN $node_ids AND endNode.identity IN $node_ids
#     WITH collect(path) AS paths
#     UNWIND paths AS singlePath
#     WITH singlePath, reduce(connectedNodes = [], node IN nodes(singlePath) | connectedNodes + node.identity) AS nodeIdentities
#     WHERE all(nodeId IN $node_ids WHERE nodeId IN nodeIdentities)
#     RETURN 
#         [node IN nodes(singlePath) | {identity: node.identity, labels: labels(node), properties: properties(node)}] AS nodes, 
#         [r IN relationships(singlePath) | {source: startNode(r).identity, target: endNode(r).identity, type: type(r), properties: properties(r)}] AS relationships
#     LIMIT 1
#     """
#     params = {
#         'node_ids': node_ids
#     }

#     try:
#         result = run_query(query, params)  # Execute the query

#         # Debugging: Print the result to check its structure
#         print("Query Result:", result)

#         if result:
#             # Extract nodes and relationships from the first (and only) result
#             record = result[0]
#             nodes_in_path = [
#                 {
#                     'identity': node['identity'],
#                     'type': node['labels'][0] if node['labels'] else 'Unknown',  # Get the first label as the node type
#                     'properties': node['properties']  # Include node properties
#                 }
#                 for node in record['nodes']
#             ]

#             relationships_in_path = [
#                 {
#                     'source': rel['source'],
#                     'target': rel['target'],
#                     'type': str (rel['type']),
#                     'properties': rel['properties']  # Include relationship properties
#                 }
#                 for rel in record['relationships']
#             ]

#             return JsonResponse({'paths': [{'nodes': nodes_in_path, 'relationships': relationships_in_path}]}, status=200)
#         else:
#             return JsonResponse({'error': 'No subgraph found connecting all nodes'}, status=404)
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)
  