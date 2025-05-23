from rest_framework.decorators import api_view
from rest_framework.response import Response
# from utility import *



from graph.utility import run_query
from django.http import JsonResponse


from rest_framework.decorators import api_view
from rest_framework.response import Response
from graph.utility import run_query  # Ensure this function runs Cypher queries

from graph.utility_neo4j import parse_to_graph_with_transformer, run_query

from ..utility   import driver

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.conf import settings



@api_view(['POST'])
def calculate_centrality(request):
    """
    API endpoint to calculate centrality for a given node type using specified parameters.
    
    Parameters (in request body):
    - nodeType: The node type/label (e.g., 'Account')
    - centralityAlgorithm: The centrality algorithm to use (e.g., 'Betweenness Centrality')
    - attributeName: The name for the output property (will be prefixed with '_')
    - normalize: Boolean indicating whether to normalize results
    - weightProperty: Optional property to use as weight (for Betweenness Centrality)
    - isDirected: Boolean indicating if the graph is directed
    - selectedRelationships: List of real relationship types
    - virtualRelationships: List of virtual relationship names (not used in calculations)
    
    Returns:
    - Centrality calculation results and top 10 nodes
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
def get_relationship_types_for_node_type(request):
    """
    API endpoint to get all relationship types where both start and end nodes are of the specified node type.
    
    Parameters:
    - nodeType: The node type/label (e.g., 'Person', 'Phone')
    
    Returns:
    - List of distinct relationship types connecting nodes of the specified type
    """
    node_type = request.query_params.get('nodeType')
    
    if not node_type:
        return Response(
            {"error": "nodeType parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get distinct relationship types where both nodes are of the specified type
            query = f"""
            MATCH (start:{node_type})-[r]->(end:{node_type})
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
def Secteur_Activite(request):
    query = """
    // Match Personne nodes where 'soutien' is in their class array
    MATCH (p:Personne)
    WHERE 'soutien' IN p._class

    // Iterate over each affiresoutin ID
    WITH p, p._affiresoutin AS affaireIds
    UNWIND affaireIds AS affaireId

    // Match the Affaire, Unite, Commune, Daira, and Wilaya nodes
    MATCH (affaire:Affaire {identity: affaireId})-[:Traiter]-(unite:Unite)-[:situer]-(comune:Commune)-[:appartient]-(daira:Daira)-[:appartient]-(wilaya:Wilaya)

    // Collect nom_arabe values without redundancy
    WITH p, 
        collect(DISTINCT comune.nom_arabe) AS comuneActivite, 
        collect(DISTINCT daira.nom_arabe) AS dairaActiviti, 
        collect(DISTINCT wilaya.nom_arabe) AS wiliyaActiviti

    // Empty the lists first, then set with new values
    SET p._comune_Activite = [],    // Clear the list
        p._daira_activiti = [],     // Clear the list
        p._wiliya_Activiti = []     // Clear the list
    SET p._comune_Activite = comuneActivite,
        p._daira_activiti = dairaActiviti,
        p._wiliya_Activiti = wiliyaActiviti
"""
    
    try:
        result = run_query(query)
         # Return the result as a JSON response
        return JsonResponse(result, safe=False)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
def Node_clasification(request):
    # Extract templates and depth from the request
    templates = request.data.get('templates', [])
    depth = int(request.data.get('depth', 1))  # Default depth is 1

    # Validate templates and depth
    if not templates:
        return JsonResponse({"error": "No templates provided."}, status=400)
    if depth < 1:
        return JsonResponse({"error": "Depth must be at least 1."}, status=400)

    # Generate Part 1 queries for each template
    part1_queries = []
    for template in templates:
        query = f"""
        // Part 1: Create contactWithRelation relationships for template: {template}
        MATCH {template}
        WHERE p1 <> p2
        WITH p1, p2
        MERGE (p1)-[e:contactWithRelation]->(p2);
        """
        part1_queries.append(query)

    # Generate Part 2 query dynamically based on depth
    part2_query = """
    // Part 2: Calculate _Lvl_of_Implications for each Personne node
    MATCH (p:Personne)
    OPTIONAL MATCH (p)-[r:Impliquer]-(:Affaire)  
    WITH p, COUNT(r) AS num_affaires_LvL0
    """

    # Dynamically add levels based on depth
    for level in range(1, depth):
        part2_query += f"""
        OPTIONAL MATCH (p)-[:contactWithRelation*{level}]-(p{level}:Personne)-[r{level}:Impliquer]-(:Affaire)
        WITH p, {', '.join(f'num_affaires_LvL{i}' for i in range(level))}, COUNT(r{level}) AS num_affaires_LvL{level}
        """

    # Finalize Part 2 query
    part2_query += f"""
    SET p._Lvl_of_Implications = [{', '.join(f'num_affaires_LvL{i}' for i in range(depth ))}];
    """

    # Define the rest of the queries (Parts 3-7)
    queries = part1_queries + [part2_query] + [
        """
        // Part 3: Initialize properties for all Personne nodes
        MATCH (p:Personne)
        SET p._class = ["neutre"],
            p._affireOpretioneele = [],
            p._affiresoutin = [],
            p._affireleader = [];
        """,
        """
        // Part 4: Assign "operationeel" to Personne nodes with _Lvl_of_Implications[0] > 0
        MATCH (p:Personne)
        WHERE "neutre" IN p._class AND p._Lvl_of_Implications[0] > 0
        SET p._class = p._class + "operationeel"
        WITH p
        MATCH (p)-[:Impliquer]-(a:Affaire)
        WITH p, COLLECT(a.identity) AS affaire_ids
        SET p._affireOpretioneele = affaire_ids;
        """,
        """
        // Part 5: Assign "soutien" to Personne nodes connected to "operationeel" nodes
        MATCH (p1:Personne)-[:contactWithRelation]-(p2:Personne)
        WHERE "operationeel" IN p1._class AND p2._Lvl_of_Implications[1] > p1._Lvl_of_Implications[0]
        SET p2._class = CASE WHEN NOT "soutien" IN p2._class THEN p2._class + "soutien" ELSE p2._class END,
            p2._affiresoutin = apoc.coll.toSet(p2._affiresoutin + p1._affireOpretioneele);
        """,
        f"""
        WITH range(1, {depth - 1}) AS levels
        UNWIND levels AS i
        MATCH (p1:Personne)-[:contactWithRelation]-(p2:Personne)
        WHERE "soutien" IN p1._class AND p2._Lvl_of_Implications[i+1] > p1._Lvl_of_Implications[i]
        SET p2._class = CASE WHEN NOT "soutien" IN p2._class THEN p2._class + "soutien" ELSE p2._class END,
            p2._affiresoutin = apoc.coll.toSet(p2._affiresoutin + p1._affiresoutin);
        """,
        # f"""
        # // Part 6: Assign "leader" to Personne nodes that qualify
        # WITH range({depth - 2}, {depth - 2}) AS leader_levels
        # UNWIND leader_levels AS i
        # MATCH (p1:Personne)
        # WHERE "soutien" IN p1._class
        # WITH p1, i,
        #      ALL(p2 IN [(p1)-[:contactWithRelation]-(p2:Personne) | p2] 
        #          WHERE p2._Lvl_of_Implications[i] < p1._Lvl_of_Implications[i+1]) AS level_leader
        # WITH p1, COLLECT(level_leader) AS leader_flags
        # WHERE ANY(flag IN leader_flags WHERE flag = true)
        # SET p1._class = CASE WHEN NOT "leader" IN p1._class THEN p1._class + "leader" ELSE p1._class END,
        #     p1._affireleader = p1._affiresoutin;
        # """,
        """
        // Part 7: Delete all contactWithRelation relationships
        MATCH (p1:Personne)-[r:contactWithRelation]-(p2:Personne)
        DELETE r;
        """
    ]

    # Execute each query sequentially
    results = []
    for query in queries:
        print(query)
        data = run_query(query)
        results.append(data)

    # Return the result as a JSON response
    return JsonResponse(results, safe=False)



@api_view(['POST'])
def calculate_betweenness_centrality(request):
    """
    Calculate normalized betweenness centrality for Personne nodes.
    Returns statistics about the calculation process.
    """
    try:
        

        # Step 1: Create temporary relationships
        
        query_part1 = """
        MATCH (p1:Personne)-[:Impliquer]-(a:Affaire)-[:Impliquer]-(p2:Personne)
        WHERE p1 <> p2
        MERGE (p1)-[rel:contactWithAffaire {affaireId: a.identity}]-(p2);
        """
        run_query(query_part1)

      
        query_part2 = """
        MATCH (p1:Personne)-[:Proprietaire]-(ph1:Phone)-[ap:Appel_telephone]->(ph2:Phone)-[:Proprietaire]-(p2:Personne)
        WHERE p1 <> p2
        MERGE (p1)-[e:contactWithPhone]-(p2);
        """
        run_query(query_part2)

        # Step 2: Project the graph for GDS
       
        query_part3 = """
        CALL gds.graph.project(
            'predictionGraph',
            {
                Personne: {
                    properties: []
                }
            },
            {
                contactWithAffaire: {  
                    orientation: 'UNDIRECTED'
                },
                contactWithPhone: {  
                    orientation: 'UNDIRECTED'
                }
            }
        );
        """
        run_query(query_part3)

        # Step 3: Calculate betweenness centrality
       
        query_part4 = """
        CALL gds.betweenness.write(
            'predictionGraph',
            {
                writeProperty: '_betweennessCentrality'
            }
        )
        YIELD nodePropertiesWritten, computeMillis, writeMillis, centralityDistribution;
        """
        run_query(query_part4)

        # Step 4: Calculate min-max normalized score
      
        query_part5 = """
        MATCH (p:Personne)
        WITH min(p._betweennessCentrality) AS minCentrality, 
             max(p._betweennessCentrality) AS maxCentrality
        MATCH (p:Personne)
        SET p._betweennessCentrality = 
            CASE 
                WHEN maxCentrality = minCentrality THEN 0
                ELSE (p._betweennessCentrality - minCentrality) / (maxCentrality - minCentrality)
            END;
        """
        run_query(query_part5)

        # Step 5: Delete temporary relationships
       
        query_part6 = """
        MATCH (p1:Personne)-[rel:contactWithAffaire]-(p2:Personne)
        DELETE rel;
        """
        run_query(query_part6)

        query_part7 = """
        MATCH (p1:Personne)-[rel:contactWithPhone]-(p2:Personne)
        DELETE rel;
        """
        run_query(query_part7)

        # Step 6: Clean up the projected graph
      
        query_part8 = """
        CALL gds.graph.drop('predictionGraph') YIELD graphName;
        """
        run_query(query_part8)

        # Return success response
        response_data = {
            "status": "success",
            "message": "Betweenness centrality calculated and normalized successfully",
        }
       
        return JsonResponse(response_data, status=200)

    except Exception as e:
       
        return Response({
            "status": "error",
            "message": "Failed to calculate betweenness centrality",
            "error": str(e)
        }, status=500)

    finally:
        # Ensure the graph is dropped even if there's an error
        try:
         
            run_query("CALL gds.graph.drop('predictionGraph') YIELD graphName;")
        except Exception as e:
            pass



@api_view(['POST'])
def analyse_fetch_nodes_by_range(request):
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
    Expands paths from a starting node with attribute filtering and optional direction filtering.
    Parameters (POST JSON body):
    - id_start: The internal Neo4j ID of the starting node (required)
    - attribute: The node attribute to filter on (default: '_betweenness')
    - threshold: The minimum value for the attribute (default: 0.001)
    - max_level: The maximum path expansion level (default: 10)
    - relationship_type: The relationship type to follow (default: 'GROUPED_TRANSACTION')
    - direction: The direction of relationships ('in', 'out', 'both') when max_level is 1 (default: 'both')
    """
    try:
        # Extract and validate parameters
        params = request.data
        id_start = params.get('id_start')
        attribute = params.get('attribute', '_betweenness')
        threshold = float(params.get('threshold', 0.001))
        max_level = int(params.get('max_level', 10))
        relationship_type = params.get('relationship_type', 'GROUPED_TRANSACTION')
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