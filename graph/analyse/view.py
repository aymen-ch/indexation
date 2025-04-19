from rest_framework.decorators import api_view
from rest_framework.response import Response
# from utility import *



from graph.utility import run_query
from django.http import JsonResponse


from rest_framework.decorators import api_view
from rest_framework.response import Response
from graph.utility import run_query  # Ensure this function runs Cypher queries

from graph.utility_neo4j import parse_to_graph_with_transformer, run_query

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
    Expands paths from a starting node with attribute filtering
    Parameters (POST JSON body):
    - id_start: The internal Neo4j ID of the starting node (required)
    - attribute: The node attribute to filter on (default: '_betweenness')
    - threshold: The minimum value for the attribute (default: 0.001)
    - max_level: The maximum path expansion level (default: 10)
    - relationship_type: The relationship type to follow (default: 'GROUPED_TRANSACTION')
    """
    try:
        # Extract and validate parameters
        params = request.data
        id_start = params.get('id_start')
        attribute = params.get('attribute', '_betweenness')
        threshold = float(params.get('threshold', 0.001))
        max_level = int(params.get('max_level', 10))
        relationship_type = params.get('relationship_type', 'GROUPED_TRANSACTION')

        # Validate required parameters
        if id_start is None:
            return Response({"error": "id_start is required"}, status=400)
        
        if not isinstance(id_start, int):
            return Response({"error": "id_start must be an integer"}, status=400)

        # Construct Cypher query
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

        # Execute query using your existing method
        graph_result = parse_to_graph_with_transformer(query)
        print ("graph_result",graph_result)
        return Response({
            "status": "success",
            "data": graph_result
        }, status=200)

    except ValueError as e:
        return Response({"error": f"Invalid parameter value: {str(e)}"}, status=500)
    except Exception as e:
        return Response({"error": str(e)}, status=500)