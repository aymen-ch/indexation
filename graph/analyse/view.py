from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.http import JsonResponse
from django.conf import settings

from graph.Utility_QueryExecutors import driver
from graph.Utility_QueryExecutors import run_query
from graph.Utility_QueryExecutors import parse_to_graph_with_transformer




@api_view(['POST'])
def calculate_centrality(request):
    """
    Calculate node centrality in a graph.

    Parameters:
        node_type (str): Node type to calculate centrality for.
        centrality_algorithm (str): Algorithm to use (e.g. 'Degree Centrality', 'Betweenness Centrality').
        attribute_name (str): write Attribute  for centrality calculation.

    Returns:
        dict: Centrality values for each node, keyed by node ID.
    """
  
    data = request.data
    node_type = data.get('nodeType')
    centrality_algorithm = data.get('centralityAlgorithm')
    attribute_name = data.get('attributeName')
    normalize = data.get('normalize', False)
    weight_property = data.get('weightProperty')
    is_directed = data.get('isDirected', True)
    selected_relationships = data.get('selectedRelationships', [])
    virtual_relationships = data.get('virtualRelationships', [])

    if not all([node_type, centrality_algorithm, attribute_name, selected_relationships]):
        return Response(
            {"error": "nodeType, centralityAlgorithm, attributeName, and selectedRelationships are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
       
            with driver.session(database=settings.NEO4J_DATABASE) as session:
                # Create graph projection
                relationship_query = '|'.join(selected_relationships)
                graph_query = f"""
                    MATCH (source:{node_type})-[r:{relationship_query}]->(target:{node_type})
                    RETURN gds.graph.project(
                        'centralityGraph',
                        source,
                        target,
                        {{ 
                            relationshipProperties: r {{ .{weight_property if weight_property else 'weight'} }}
                        }},
                        {{ 
                            graph: '{ 'DIRECTED' if is_directed else 'UNDIRECTED' }' 
                        }}
                    )
                """
                session.run(graph_query)

                # Map centrality algorithms to their properties and Cypher procedures
                algorithm_map = {
                    'Degree Centrality': {'procedure': 'gds.degree', 'property': '_degree'},
                    'Betweenness Centrality': {'procedure': 'gds.betweenness', 'property': '_betweenness'},
                    'Page Rank': {'procedure': 'gds.pageRank', 'property': '_pagerank'},
                    'Article Rank': {'procedure': 'gds.articleRank', 'property': '_articleRank'},
                    'Eigenvector Centrality': {'procedure': 'gds.eigenvector', 'property': '_eigenvector'},
                }

                if centrality_algorithm not in algorithm_map:
                    return Response(
                        {"error": f"Unsupported centrality algorithm: {centrality_algorithm}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                algo_config = algorithm_map[centrality_algorithm]
                write_property = f"_{attribute_name}"

                # Run centrality calculation
                centrality_query = f"""
                    CALL {algo_config['procedure']}.write('centralityGraph', {{
                        relationshipWeightProperty: '{weight_property if weight_property else None}',
                        writeProperty: '{write_property}'
                    }})
                    YIELD centralityDistribution, nodePropertiesWritten
                    RETURN 
                        centralityDistribution.min AS minimumScore,
                        centralityDistribution.mean AS meanScore,
                        nodePropertiesWritten
                """
                centrality_result = session.run(centrality_query).single()

                # Normalize results if requested
                if normalize:
                    normalize_query = f"""
                        MATCH (n)
                        WITH 
                            apoc.agg.minItems(n, n.{write_property}) AS minValue,
                            apoc.agg.maxItems(n, n.{write_property}) AS maxValue
                        MATCH (n)
                        SET n.{write_property} = CASE 
                            WHEN maxValue.value <> minValue.value AND n.{write_property} IS NOT NULL 
                            THEN (n.{write_property} - minValue.value) / (maxValue.value - minValue.value) 
                            ELSE n.{write_property} END
                        RETURN count(n) AS nodes_updated
                    """
                    normalize_result = session.run(normalize_query).single()

                # Get top 10 nodes
                top_nodes_query = f"""
                    MATCH (n)
                    WHERE n.{write_property} IS NOT NULL
                    RETURN n, n.{write_property} AS score
                    ORDER BY n.{write_property} DESC
                    LIMIT 10
                """
                top_nodes = [
                    {
                        'node': record['n'].get('name', record['n'].id),
                        'score': record['score']
                    }
                    for record in session.run(top_nodes_query)
                ]

                # Drop the graph projection
                session.run("CALL gds.graph.drop('centralityGraph', false)")

                return Response({
                    'node_type': node_type,
                    'centrality_algorithm': centrality_algorithm,
                    'write_property': write_property,
                    'minimum_score': centrality_result['minimumScore'],
                    'mean_score': centrality_result['meanScore'],
                    'nodes_written': centrality_result['nodePropertiesWritten'],
                    'nodes_normalized': normalize_result['nodes_updated'] if normalize else 0,
                    'top_nodes': top_nodes
                }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_relationship_numeric_properties(request):
    """
    API endpoint to get all numeric properties for a given relationship type.
    
    Parameters:
    - relationshipType: The relationship type (e.g., 'KNOWS', 'WORKED_WITH')
    
    Returns:
    - List of all numeric property keys for the specified relationship type
    """
    relationship_type = request.query_params.get('relationshipType')
    
    if not relationship_type:
        return Response(
            {"error": "relationshipType parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get all properties of the relationship type and filter for numeric ones
            query = f"""
            MATCH ()-[r:{relationship_type}]-()
            RETURN properties(r) AS props
            LIMIT 1
            """
            
            result = session.run(query)
            properties = result.single()
            print("pro2p" ,properties )

            if not properties:
                return Response({
                    "relationship_type": relationship_type,
                    "numeric_properties": [],
                    "count": 0
                }, status=status.HTTP_200_OK)
                
            # Filter for numeric properties (integer or float)
            props = properties["props"]
            numeric_properties = [
                key for key, value in props.items()
                if isinstance(value, (int, float))
            ]

            return Response({
                "relationship_type": relationship_type,
                "numeric_properties": numeric_properties,
                "count": len(numeric_properties)
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_relationship_types_for_node_type(request):
    """
    API endpoint to get all relationship types connected to a given node type.
    
    Parameters:
    - nodeType: The node type/label (e.g., 'Person', 'Movie')
    
    Returns:
    - List of all relationship types connected to the specified node type
    """
    node_type = request.query_params.get('nodeType')
    
    if not node_type:
        return Response(
            {"error": "nodeType parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get all relationship types connected to the node type
            query = f"""
            MATCH (n:{node_type})-[r]-()
            RETURN DISTINCT type(r) AS relationship_type
            """
            
            result = session.run(query)
            relationship_types = [record["relationship_type"] for record in result]

            return Response({
                "node_type": node_type,
                "relationship_types": relationship_types,
                "count": len(relationship_types)
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
def get_attribute_values_for_node_type(request):
    """
    API endpoint to get all values of a specific attribute for a given node type.
    
    Parameters:
    - selectedGroup: The node type/label (e.g., 'Person', 'Movie')
    - selectedCentralityAttribute: The attribute/property name (e.g., 'pagerank', 'betweenness')
    
    Returns:
    - List of all values for the specified attribute in the specified node type
    """
    selected_group = request.query_params.get('selectedGroup')
    selected_attribute = request.query_params.get('selectedCentralityAttribute')
    
    if not selected_group or not selected_attribute:
        return Response(
            {"error": "Both selectedGroup and selectedCentralityAttribute parameters are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get all values of the specified attribute for the node type
            query = f"""
            MATCH (n:{selected_group})
            WHERE n.{selected_attribute} IS NOT NULL
            RETURN n.{selected_attribute} AS attribute_value
            """
            
            result = session.run(query)
            attribute_values = [record["attribute_value"] for record in result]

            return Response({
                "node_type": selected_group,
                "attribute": selected_attribute,
                "values": attribute_values,
                "count": len(attribute_values)
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def fetch_distinct_relations(request):
    query = """
    CALL db.relationshipTypes() YIELD relationshipType
    RETURN COLLECT(relationshipType) AS distinct_relationships
    """
    
    try:
        result = run_query(query)
        return Response({"distinct_relationships": result[0]['distinct_relationships']}, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    











@api_view(['POST'])
def analyse_fetch_nodes_by_range(request):
    """
    Fetch and analyse nodes of a given type within a specified attribute range.

    Objective:
    -----------
    This function aims to retrieve a subset of nodes from the graph that match the specified type and attribute range.
    The function is designed to support data analysis and filtering tasks, such as:
        - Identifying nodes with attribute values within a specific range
        - Filtering out nodes with attribute values outside the specified range
        - Retrieving nodes for further analysis or processing

    Parameters:
        node_type (str): Type of nodes to fetch (e.g. "Person", "Organization", etc.)
        attribute (str): Attribute to filter nodes by (e.g. "age", "score", etc.)
        start (int): Start of the range (inclusive)
        end (int): End of the range (inclusive)

    Returns:
        list: Nodes of the specified type within the attribute range

    Example Use Case:
    -----------------
    Fetch all "Person" top nodes with an "mony" attribute ordre by attribute then give the onces form start index to end index
    """
    # Extract parameters from the request
    node_type = request.data.get('node_type')
    attribute = request.data.get('attribute')
    start = request.data.get('start')
    end = request.data.get('end')

    # Validate inputs
    if not node_type or not attribute:
        return Response({"error": "node_type and attribute are required."}, status=400)
    if not isinstance(start, int) or not isinstance(end, int):
        return Response({"error": "start and end must be integers."}, status=400)
    if start < 0 or end < start:
        return Response({"error": "Invalid range: start must be non-negative, and end must be >= start."}, status=400)

    # Construct Cypher query to fetch, sort, and slice nodes
    query = f"""
    MATCH (n:{node_type})
    WHERE n.{attribute} IS NOT NULL
    RETURN n
    ORDER BY n.{attribute} DESC
    SKIP {start}
    LIMIT {end - start + 1}
    """

    try:
        # Execute the query using parse_to_graph_with_transformer
        graph_result = parse_to_graph_with_transformer(query)

        # Return the full graph result
        return Response(graph_result, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    






@api_view(['POST'])
def expand_path_from_node(request):
    """
    Expand a path from a given node in the graph.

    Objective:
    -----------
    This function aims to traverse the graph from a specified node and expand a path based on the given direction.
    The function is designed to support graph traversal and path exploration tasks, such as:
        - Finding all nodes connected to a given node within a certain depth
        - Identifying the shortest path between two nodes
        - Retrieving all nodes and relationships within a certain distance from a given node

    Parameters:
        node_id (str): ID of the node to start the path from
        max_depth (int): Maximum depth to traverse from the starting node
        direction (str): Direction of traversal (e.g. "OUTGOING", "INCOMING", "BOTH")

    Returns:
        list: Expanded path from the starting node, including nodes and relationships

    Example Use Case:
    -----------------
    Expand a path from node "123" up to a depth of 2:
    expand_path_from_node("123", 2, "OUTGOING")
    """
   
    try:
        # Extract and validate parameters
        params = request.data
        id_start = params.get('id_start')
        attribute = params.get('attribute', '_betweenness')
        threshold = float(params.get('threshold', 0.001))
        max_level = int(params.get('max_level', 10))
        direction = params.get('direction', 'both').lower()

        # Validate required parameters
        if id_start is None:
            return Response({"error": "id_start is required"}, status=400)
        
        if not isinstance(id_start, int):
            return Response({"error": "id_start must be an integer"}, status=400)

        if direction not in ['in', 'out', 'both']:
            return Response({"error": "direction must be 'in', 'out', or 'both'"}, status=400)

        # Construct Cypher query (unchanged)
        query = f"""
        MATCH (start)
        WHERE id(start) = {id_start}
        
        CALL apoc.path.expandConfig(start, {{
            minLevel: 1,
            maxLevel: {max_level},
            uniqueness: "NODE_GLOBAL"
        }}) YIELD path
        
        WHERE ALL(node IN nodes(path) WHERE node.{attribute} > {threshold})
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        RETURN COLLECT(DISTINCT node) AS nodes, COLLECT(DISTINCT rel) AS relationships
        """

        # Execute query
        graph_result = parse_to_graph_with_transformer(query)

        # Filter edges based on direction when max_level is 1
        if max_level == 1 and direction != 'both':
            filtered_nodes = []
            filtered_edges = []

            # Filter edges based on direction
            for edge in graph_result.get('edges', []):
                source_id = edge.get('startNode')
                target_id = edge.get('endNode')

                if direction == 'out' and source_id == id_start:
                    filtered_edges.append(edge)
                elif direction == 'in' and target_id == id_start:
                    filtered_edges.append(edge)

            # Collect nodes that are part of filtered edges
            node_ids = {id_start}  # Always include the start node
            for edge in filtered_edges:
                node_ids.add(edge['startNode'])
                node_ids.add(edge['endNode'])

            # Filter nodes to include only those connected by filtered edges
            for node in graph_result.get('nodes', []):
                if node['id'] in node_ids:
                    filtered_nodes.append(node)

            # Update graph_result with filtered data
            graph_result = {
                'nodes': filtered_nodes,
                'edges': filtered_edges
            }

        return Response({
            "status": "success",
            "data": graph_result
        }, status=200)

    except ValueError as e:
        return Response({"error": f"Invalid parameter value: {str(e)}"}, status=400)
    except Exception as e:
        return Response({"error": str(e)}, status=500)