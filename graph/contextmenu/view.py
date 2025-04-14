


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

    # Construct the Cypher query with parameterized id
    query = f"""
    MATCH (n:{node_type})-[r]-()
    WHERE id(n) = $id
    RETURN DISTINCT type(r) AS relationship_type
    """
    parameters = {"id": int(id)}  # Ensure id is an integer

    try:
        results = run_query(query, parameters, database=settings.NEO4J_DATABASE)
        relationship_types = [record["relationship_type"] for record in results]
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