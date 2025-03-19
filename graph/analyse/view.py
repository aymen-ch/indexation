from rest_framework.decorators import api_view
from rest_framework.response import Response
# from utility import *



from graph.utility import run_query
from django.http import JsonResponse


from rest_framework.decorators import api_view
from rest_framework.response import Response
from graph.utility import run_query  # Ensure this function runs Cypher queries

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
def calculate_degree_centrality(request):
    relationships = request.data
    if not relationships:
        return Response({"error": "No relationships provided."}, status=400)
    
    nodes = set()
    edges = []

    if not isinstance(relationships, list):
        return Response({"error": "Invalid input format. Expected a list of relationships."}, status=400)
    
    for rel in relationships:
        if not all(key in rel for key in ['from', 'to', 'label']):
            return Response({"error": "Invalid relationship format. Each relationship must include 'from', 'to', and 'label'."}, status=400)
        
        from_node, to_node, label = rel['from'], rel['to'], rel['label']
        nodes.add(from_node)
        nodes.add(to_node)
        edges.append({"start": from_node, "end": to_node, "type": label})
    
    gds_graph_name = "tempSubgraph"

    try:
        create_nodes_query = """
        UNWIND $nodes AS node_id
        MERGE (n:TempNode {id: node_id})
        """
        create_edges_query = """
        UNWIND $edges AS edge
        MATCH (start:TempNode {id: edge.start}), (end:TempNode {id: edge.end})
        MERGE (start)-[r:TempRel {type: edge.type}]->(end)
        """
        create_gds_graph_query = f"""
        CALL gds.graph.project(
            '{gds_graph_name}',
            'TempNode',
            {{
                TempRel: {{
                    orientation: 'Undirected'
                }}
            }}
        )
        """

        run_query(create_nodes_query, {"nodes": list(nodes)})
        run_query(create_edges_query, {"edges": edges})
        run_query(create_gds_graph_query, {})

        centrality_query = f"""
        CALL gds.eigenvector.stream('{gds_graph_name}')
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).id AS node_id, score
        ORDER BY score DESC
        """
        centrality_results = run_query(centrality_query)

        cleanup_query = f"CALL gds.graph.drop('{gds_graph_name}') YIELD graphName"
        delete_temp_nodes = "MATCH (n:TempNode) DETACH DELETE n"
        run_query(cleanup_query)
        run_query(delete_temp_nodes)

        return Response({"degree_centrality": centrality_results}, status=200)
    
    except Exception as e:
        cleanup_query = f"CALL gds.graph.drop('{gds_graph_name}') YIELD graphName"
        delete_temp_nodes = "MATCH (n:TempNode) DETACH DELETE n"
        run_query(cleanup_query)
        run_query(delete_temp_nodes)
        return Response({"error": str(e)}, status=500)