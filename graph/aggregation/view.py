from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
import neo4j 
from graph.utility import run_query,driver

from graph.utility_neo4j import parse_to_graph_with_transformer
# //////////////  neeed to aggregate properties /////////



@api_view(['POST'])
def ExpandAggregation(request):
    # Get data from request
    id_nodes = request.data.get("node_ids", [1160, 126224])  # Default to example IDs
    aggregation_path = request.data.get("aggregationpath", ["Personne", "Impliquer", "Affaire", "Impliquer", "Personne"])

    # Validate input
    if not isinstance(id_nodes, list) or len(id_nodes) < 2:
        return Response({"error": "At least two node IDs are required"}, status=400)
    if not isinstance(aggregation_path, list) or len(aggregation_path) < 3:
        return Response({"error": "Invalid aggregation path"}, status=400)

    # Build the Cypher query
    try:
        # Construct the MATCH pattern dynamically
        # Example: MATCH (p1:Personne {identity: 1160})-[:Impliquer]->(a:Affaire)-[:Impliquer]->(p2:Personne {identity: 126224})
        start_node = aggregation_path[0]  # e.g., "Personne"
        end_node = aggregation_path[-1]   # e.g., "Personne"
        relationships = aggregation_path[1:-1]  # e.g., ["Impliquer", "Affaire", "Impliquer"]

        # Build the relationship pattern
        pattern_parts = []
        current_var = 'n0'  # Starting variable for first node
        for i, part in enumerate(relationships):
            next_var = f'n{i+1}'
            if i % 2 == 0:  # Relationship
                pattern_parts.append(f'-[:{part}]-')
            else:  # Node
                pattern_parts.append(f'({next_var}:{part})')
            current_var = next_var

        # Construct the full Cypher query
        query = (
            f"MATCH path=(n0:{start_node} {{identity: {id_nodes[0]}}})"
            f"{''.join(pattern_parts)}"
            f"({current_var}:{end_node} {{identity: {id_nodes[-1]}}}) "
            "RETURN  path"
        )

     

        # Execute the query using the utility function
        graph_result = driver.execute_query(query_=query,
            result_transformer_=neo4j.Result.graph,
        )
        for node in graph_result.nodes:
    # Extract the required parts
                identity = node.get('properties')  # From properties dictionary

                print(identity)
        # Process the result
        return Response({
            "nodes": "hh",
        
        }, status=200)
           

    except Exception as e:
        print(f"Error executing query: {str(e)}")
        return Response({"error": f"Query failed: {str(e)}"}, status=500)

@api_view(['POST'])
def aggregate(request):
    id_nodes = request.data.get("node_ids", [1160, 126224, 129664, 129668, 136220, 1368, 1370, 34151, 34155])  # List of node IDs
    aggregation_type = request.data.get("aggregation_type", [["Personne", "Impliquer", "Affaire", "Impliquer", "Personne"]])
    type = request.data.get("type","memeaffaire")
    if not id_nodes:
        return Response({"error": "id_nodes parameter is required"}, status=400)
    print(id_nodes)
    query_parts = []
    params = {"id_nodes": id_nodes}
    alias_counter = {}  # Dictionary to track alias counts

    def get_alias(name):
        """Generate a unique alias based on the first letter of the node type."""
        first_letter = name[0].upper()  # Take the first character and capitalize
        alias_counter[first_letter] = alias_counter.get(first_letter, 0) + 1
        return f"{first_letter}{alias_counter[first_letter]}"

    for sublist in aggregation_type:
        print(sublist)
        # Ensure the sublist has an odd length (node-relationship-node pattern)
        if len(sublist) % 2 == 0:  # Even length means invalid path
            continue

        # Generate aliases for all nodes in the path
        aliases = [get_alias(sublist[i]) for i in range(0, len(sublist), 2)]
        print(aliases)
        # Construct the MATCH clause dynamically
        match_clause = []
        for i in range(0, len(sublist), 2):
            node_type = sublist[i]
            alias = aliases[i // 2]
            if i == 0:
                match_clause.append(f"({alias}:{node_type})")
            else:
                relationship_type = sublist[i - 1]
                prev_alias = aliases[(i // 2) - 1]
                match_clause.append(f"-[:{relationship_type}]-({alias}:{node_type})")

        match_clause = "MATCH " + "".join(match_clause)

        # Construct the WHERE clause to filter by node IDs
        if len(sublist)==3:
           intermediate_aliases = aliases  # Exclude the first and last aliases
        else:
            intermediate_aliases = aliases[1:-1]
        if intermediate_aliases:  # Only add WHERE clause if there are intermediate nodes
            where_clause = "WHERE " + " AND ".join([f"id({alias}) IN $id_nodes" for alias in intermediate_aliases])
        else:
            where_clause = ""  # No intermediate nodes, so no WHERE clause

        # Construct the WITH and RETURN clauses with separated properties
        start_alias = aliases[0]  # First node
        end_alias = aliases[-1]   # Last node
        first_intermediate = aliases[1] if len(aliases) > 2 else start_alias  # First intermediate node
        last_intermediate = aliases[-2] if len(aliases) > 2 else end_alias    # Last intermediate node

        with_clause = f"""
        WITH DISTINCT 
            {start_alias} AS start_node, 
            {first_intermediate} AS first_intermediate_node, 
            {end_alias} AS end_node, 
            {last_intermediate} AS last_intermediate_node, 
            count({aliases[1]}) as count
        WITH 
            start_node, 
            properties(start_node) AS start_node_properties,  /* Keep start node properties separate */
            properties(first_intermediate_node) AS first_intermediate_properties,  /* Separate intermediate properties */
            end_node, 
            properties(end_node) AS end_node_properties,  /* Keep end node properties separate */
            properties(last_intermediate_node) AS last_intermediate_properties,  /* Separate intermediate properties */
            count
        WITH 
            CASE 
                WHEN id(start_node) < id(end_node) 
                THEN {{startId: id(start_node), endId: id(end_node), type:'{type}' , count: count}}
                ELSE {{startId: id(end_node), endId: id(start_node), type: '{type}', count: count}}
            END AS relationship,
            COLLECT(DISTINCT {{
                id: id(start_node),
                type: labels(start_node)[0], 
                properties: start_node_properties,  /* Node's own properties */
                aggregated_properties: first_intermediate_properties  /* Aggregated properties from intermediate node */
            }}) +
            COLLECT(DISTINCT {{
                id: id(end_node), 
                type: labels(end_node)[0], 
                properties: end_node_properties,  /* Node's own properties */
                aggregated_properties: last_intermediate_properties  /* Aggregated properties from intermediate node */
            }}) AS nodes
        RETURN nodes, COLLECT(DISTINCT relationship) AS relationships
        """

        query = f"{match_clause}\n{where_clause}\n{with_clause}"
        query_parts.append(query)

    if not query_parts:
        return Response({"error": "No valid aggregation type specified"}, status=400)

    # Combine all queries with UNION ALL
    combined_query = """
    CALL {
        """ + "\n    UNION ALL\n".join(query_parts) + """
    }
    WITH 
        COLLECT(nodes) AS all_nodes, 
        COLLECT(relationships) AS all_relationships
    WITH 
        REDUCE(acc = [], nodes IN all_nodes | acc + nodes) AS combined_nodes,
        REDUCE(acc = [], rels IN all_relationships | acc + rels) AS combined_relationships
    UNWIND combined_nodes AS node
    RETURN 
        COLLECT(DISTINCT {
            id: node.id,
            type: node.type,
            properties: node.properties,  /* Individual node properties */
            aggregated_properties: node.aggregated_properties  /* Aggregated properties from related nodes */
        }) AS nodes,
        combined_relationships AS relationships
    """
    print(combined_query)
    try:
        # Run the query using the provided helper function
        results = run_query(combined_query, params)
        if results:
            data = results[0]
            nodes = data.get("nodes", [])
            relationships = data.get("relationships", [])
        else:
            nodes = []
            relationships = []

        return Response({"nodes": nodes, "relationships": relationships}, status=200)
    except Exception as e:
        print(e)
        
        return Response({"error": f"Query failed: {str(e)}"}, status=500)

@api_view(['POST'])
def aggregate2(request):
    id_nodes = request.data.get("node_ids",[1160, 126224, 129664, 129668, 136220, 1368, 1370, 34151, 34155])  # List of node IDs (Affaire, Personne, Phone)
    aggregation_type = request.data.get("aggregation_type", [["Personne", "Impliquer", "Affaire", "Impliquer", "Personne"]])
    if not id_nodes:
        return Response({"error": "id_nodes parameter is required"}, status=400)
    # Initialize query parts
    print(aggregation_type)
    query_parts = []
    params = {"id_nodes": id_nodes}
    alias_counter = {}  # Dictionary to track alias counts
    def get_alias(name):
        """Generate a unique alias based on the first letter of the node type."""
        first_letter = name[0].upper()  # Take the first character and capitalize
        alias_counter[first_letter] = alias_counter.get(first_letter, 0) + 1
        return f"{first_letter}{alias_counter[first_letter]}"
    for sublist in aggregation_type:
            if len(sublist)==5:
                start_alias = get_alias(sublist[0])
                inter_alias = get_alias(sublist[2])
                end_alias = get_alias(sublist[4])
                affaire_query = f"""
                MATCH ({start_alias}:{sublist[0]})-[:{sublist[1]}]-({inter_alias}:{sublist[2]})-[:{sublist[3]}]-({end_alias}:{sublist[4]})
                WHERE {inter_alias}.identity IN $id_nodes
                WITH DISTINCT {start_alias}, {end_alias}, count({inter_alias}) as ctaffaire
                WITH 
                    CASE 
                        WHEN {start_alias}.identity < {end_alias}.identity 
                        THEN {{startId: {start_alias}.identity, endId: {end_alias}.identity, relationType: "same{sublist[2]}", count: ctaffaire}}
                        ELSE {{startId: {end_alias}.identity, endId: {start_alias}.identity, relationType: "same{sublist[2]}", count: ctaffaire}}
                    END AS relationship,
                    COLLECT(DISTINCT {start_alias}) + COLLECT(DISTINCT {end_alias}) AS affaire_nodes
                RETURN affaire_nodes AS nodes, COLLECT(DISTINCT relationship) AS relationships
                """
                query_parts.append(affaire_query)
            else:
                p3_alias = get_alias(sublist[0])
                inter1_alias = get_alias(sublist[2])
                inter2_alias = get_alias(sublist[2]) 
                p4_alias = get_alias(sublist[6])
                phone_query = f"""
                MATCH ({p3_alias}:{sublist[0]})-[:{sublist[1]}]-({inter1_alias}:{sublist[2]})-[re:{sublist[3]}]-({inter2_alias}:{sublist[4]})-[:{sublist[5]}]-({p4_alias}:{sublist[6]})
                WHERE {inter1_alias}.identity IN $id_nodes AND {inter2_alias}.identity IN $id_nodes  
                WITH DISTINCT {p3_alias}, {p4_alias}, {inter1_alias}, {inter2_alias}, count(re) as cphone
                WITH 
                    CASE 
                        WHEN {p3_alias}.identity < {p4_alias}.identity 
                        THEN {{startId: {p3_alias}.identity, endId: {p4_alias}.identity, relationType: "same{sublist[2]}", count: cphone}}
                        ELSE {{startId: {p4_alias}.identity, endId: {p3_alias}.identity, relationType: "same{sublist[2]}", count: cphone}}
                    END AS relationship,
                    COLLECT(DISTINCT {p3_alias}) + COLLECT(DISTINCT {p4_alias}) AS phone_nodes
                RETURN phone_nodes AS nodes, COLLECT(DISTINCT relationship) AS relationships
                """
                query_parts.append(phone_query) 
    if query_parts:
        combined_query = """
        // Combine results from affaire and phone queries
        CALL {
            """ + "\n    UNION ALL\n".join(query_parts) + """
        }
        WITH 
            COLLECT(nodes) AS all_nodes, 
            COLLECT(relationships) AS all_relationships
        WITH 
            REDUCE(acc = [], nodes IN all_nodes | acc + nodes) AS combined_nodes,
            REDUCE(acc = [], rels IN all_relationships | acc + rels) AS combined_relationships
        UNWIND combined_nodes AS node
        RETURN 
            COLLECT(DISTINCT {
                identity: node.identity,
                type: labels(node)[0],
                properties: properties(node)
            }) AS nodes,
            combined_relationships AS relationships
        """

    else:
        return Response({"error": "No valid aggregation type specified"}, status=400)
    try:
        # Run the query using the provided helper function
        results = run_query(combined_query, params)
    
        if results:
            data = results[0]
            nodes = data.get("nodes", [])
            relationships = data.get("relationships", [])
        else:
            nodes = []
            relationships = []
        return Response({"nodes": nodes, "relationships": relationships}, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
def aggregate_hira2(request):
    # Extract the date and depth from the request body
    id_affaires = request.data.get('id_affaires', [1171])  # Default date if not provided
    depth = int(request.data.get('depth',2))  # Default depth if not provided

    # Base query
    query = """
    MATCH (a:Affaire)-[:Impliquer]-(p1:Personne)
    WHERE a.date = $id_affaires 
    WITH a, p1,
         collect({
             identity: p1.identity,
             type: "Personne"
         }) AS personnesNodes,
         collect({
             source: a.identity,
             target: p1.identity,
             type: "Impliquer"
         }) AS relations,
         collect(p1) as p1List
    """
    for level in range(1, depth):
        # Define variables for the current level
        current_person = f"p{level + 1}"
        current_phone = f"ph{level + 1}"
        previous_person = f"p{level}"
        previous_phone = f"ph{level}"
        previous_list = f"p{level}List"

        # Add the OPTIONAL MATCH for the current level
        query += f"""
        OPTIONAL MATCH ({previous_person})<-[:Proprietaire]-({previous_phone})-[:Appel_telephone]-({current_phone}:Phone)-[:Proprietaire]->({current_person}:Personne)
        WHERE  NOT ({current_person} IN {previous_person}List) AND {current_person}.identity IS NOT NULL  
        WITH a, p1, personnesNodes, relations, """
        
        # Include all previous level nodes and relationships
        for l in range(1, level):
            query += f"personnesLevel{l}Nodes, relationsLevel{l}, "
        
        query += f"""
            collect({{
                identity: {current_person}.identity,
                type: "Personne"            
                }}) AS personnesLevel{level}Nodes,
            collect({{
                source: {previous_person}.identity,
                target: {current_person}.identity,
                type: "Contact"
            }}) AS relationsLevel{level},
            collect({current_person}) AS {current_person}List  // Collect {current_person} for use in next level
        """

    # Combine all nodes and relationships
    query += """
    WITH a,
        personnesNodes + """
    for level in range(1, depth):
        query += f"personnesLevel{level}Nodes + "
    query += """[{identity: a.identity, type: "Affaire", level: 0}] AS allNodes,  // Level 0 for Affaire
        relations + """
    for level in range(1, depth):
        query += f"relationsLevel{level} + "
    query = query.rstrip(" + ")  # Remove the last "+"
    query += """ AS allRelations
    """
   

    # Filter out nodes and relationships with null identities
    query += """
    WITH a,
         [node IN allNodes WHERE node.identity IS NOT NULL] AS filteredNodes,
         [rel IN allRelations WHERE rel.source IS NOT NULL AND rel.target IS NOT NULL] AS filteredRelations
    // Collect all nodes and relationships across all Affaire entities
    WITH 
         collect(filteredNodes) AS allFilteredNodes,
         collect(filteredRelations) AS allFilteredRelations
    // Flatten the lists and remove duplicates
    WITH 
         apoc.coll.toSet(apoc.coll.flatten(allFilteredNodes)) AS nodes,
         apoc.coll.toSet(apoc.coll.flatten(allFilteredRelations)) AS relations
    // Return a single JSON object containing all nodes and relationships
    RETURN {
        nodes: nodes,
        relations: relations
    } AS result
    """

    # Print the query for debugging
    print(query)
    # Execute the query using the run_query function
    params = {"id_affaires": id_affaires}
    data = run_query(query, params)

    # Return the result as a JSON response
    return JsonResponse(data, safe=False)


@api_view(['POST'])
def aggregate_hira(request):
    # Extract the date and depth from the request body
    id_affaires = request.data.get('id_affaires', [1171])  # Default date if not provided
    depth = int(request.data.get('depth',3))  # Default depth if not provided
    print(id_affaires)
    print(depth)
    # Base query
    query = """
MATCH (c:Affaire)-[:Impliquer]-(p:Personne) 
WHERE c.identity IN $id_affaires
// Collect all Personne nodes directly involved in each Affaire
WITH c, COLLECT(p) AS DirectlyInvolvedPersons

// Collect initial NodesTable (Affaire + DirectlyInvolvedPersons)
WITH c, DirectlyInvolvedPersons, 
     apoc.coll.toSet(
         [{identity: c.identity, type: "Affaire"}] + 
         [p IN DirectlyInvolvedPersons | {identity: p.identity, type: "Personne"}]
     ) AS NodesTable

// Construct relations table with only node identities
WITH c, DirectlyInvolvedPersons, NodesTable, 
     [p IN DirectlyInvolvedPersons | {source: c.identity, target: p.identity, relation: "Impliquer"}] AS ImpliquerRelations

// Expand paths starting from each involved Personne node to find additional connections
UNWIND DirectlyInvolvedPersons AS p
CALL apoc.path.expandConfig(p, {
    relationshipFilter: "Proprietaire,Appel_telephone,Proprietaire|Appel_telephone",
    minLevel: 0,
    maxLevel: $depth,
    labelFilter: "+Personne|+Phone"  // Restrict traversal to Personne and Phone
}) YIELD path

// Extract all Personne nodes from the path
WITH c, DirectlyInvolvedPersons, NodesTable, ImpliquerRelations, nodes(path) AS nodesInPath
UNWIND nodesInPath AS node
WITH c, DirectlyInvolvedPersons, NodesTable, ImpliquerRelations, node
WHERE node:Personne  // Keep only Personne nodes

// Collect all unique Personne nodes found in the path
WITH c, DirectlyInvolvedPersons, NodesTable, ImpliquerRelations, COLLECT(DISTINCT node) AS ContactedPersons

// Ensure DirectlyInvolvedPersons are always included in ContactedPersons
WITH c, DirectlyInvolvedPersons, NodesTable, ImpliquerRelations, 
     apoc.coll.toSet(DirectlyInvolvedPersons + ContactedPersons) AS AllInvolvedPersons

// Add extra Personne nodes to NodesTable
WITH c, DirectlyInvolvedPersons, ImpliquerRelations, AllInvolvedPersons,
     apoc.coll.toSet(
         NodesTable + 
         [p IN AllInvolvedPersons | {identity: p.identity, type: "Personne"}]
     ) AS UpdatedNodesTable

// Find all pairs of Personne nodes connected via shared Phone nodes
OPTIONAL MATCH (p1:Personne)-[:Proprietaire]-(phone1:Phone)-[:Appel_telephone]-(phone2:Phone)-[:Proprietaire]-(p2:Personne)
WHERE p1 IN AllInvolvedPersons AND p2 IN AllInvolvedPersons AND p1 <> p2

// Count the number of Appel_telephone relationships between each pair of Personne nodes
WITH c, DirectlyInvolvedPersons, UpdatedNodesTable, ImpliquerRelations, AllInvolvedPersons, 
     p1, p2, COUNT(*) AS contactCount

// Ensure only one direction for each Contact relation (avoid duplicates)
WITH c, DirectlyInvolvedPersons, UpdatedNodesTable, ImpliquerRelations, AllInvolvedPersons, 
     COLLECT(DISTINCT CASE 
         WHEN p1 IS NOT NULL AND p2 IS NOT NULL 
         THEN {source: CASE WHEN p1.identity < p2.identity THEN p1.identity ELSE p2.identity END, 
               target: CASE WHEN p1.identity < p2.identity THEN p2.identity ELSE p1.identity END, 
               relation: "Contact", 
               count: contactCount} 
         ELSE NULL 
     END) AS ContactRelations

// Filter out NULL entries from ContactRelations
WITH UpdatedNodesTable, ImpliquerRelations + [r IN ContactRelations WHERE r IS NOT NULL] AS RelationsTable

// Aggregate all nodes and relations across all Affaire nodes
WITH 
    apoc.coll.toSet([n IN UpdatedNodesTable | n]) AS NodesList,
    apoc.coll.toSet([r IN RelationsTable | r]) AS RelationsList

// Collect everything into a single result across all Affaire nodes
WITH COLLECT(DISTINCT NodesList) AS AllNodesList, COLLECT(DISTINCT RelationsList) AS AllRelationsList

// Flatten lists to return a single unified result
RETURN {
    nodes: apoc.coll.toSet(apoc.coll.flatten(AllNodesList)),
    relations: apoc.coll.toSet(apoc.coll.flatten(AllRelationsList))
} AS Result;
"""
    # Print the query for debugging
    print(query)
    # Execute the query using the run_query function
    params = {"id_affaires": id_affaires,"depth":depth*3}
    data = run_query(query, params)

    # Return the result as a JSON response
    return JsonResponse(data, safe=False)




from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse

@api_view(['POST'])
def aggregate_with_algo(request):
    # Extract parameters from the request body
    id_affaires = request.data.get('id_affaires', [1171])  # Default value if not provided
    depth = int(request.data.get('depth', 3))  # Default depth if not provided
    patterns = request.data.get('patterns', [
        "-[:Proprietaire]-(:Phone)-[:Appel_telephone]-(:Phone)-[:Proprietaire]-"
    ])  # Default pattern if not provided
    rel_type = request.data.get('rel_type', 'CONNECTED')  # Default relationship type

    # Validate inputs
    if depth < 1:
        return JsonResponse({"error": "Depth must be at least 1."}, status=400)
    if not patterns:
        return JsonResponse({"error": "At least one pattern must be provided."}, status=400)

    # Initialize the base query
    query = """
    UNWIND $id_affaires AS id_affaire
    MATCH (c:Affaire)-[r0:Impliquer]-(p1:Personne)
    WHERE c.identity = id_affaire
    WITH id_affaire, c, p1, r0
    """

    # Lists to collect nodes and virtual relationships
    nodes = ["c", "p1"]
    vrels = ["r0"]  # Keep the original Impliquer relationship

    # Build the query dynamically for each depth level and pattern
    for i in range(1, depth):
        # For each depth level, match any of the provided patterns
        pattern_matches = []
        for pattern in patterns:
            pattern_match = f"(p{i}){pattern}(p{i+1}:Personne)"
            pattern_matches.append(pattern_match)

        # Combine all pattern matches with OR logic
        match_clause = "MATCH " + " OR ".join(pattern_matches)
        query += f"""
        {match_clause}
        WHERE id_affaire IN p{i+1}._affiresoutin AND p{i+1}._Lvl_of_Implications[{i}] > p{i}._Lvl_of_Implications[{i-1}]
        CALL apoc.create.vRelationship(p{i}, $rel_type, {{depth: {i}, pattern: '{patterns[0]}'}}, p{i+1}) YIELD rel AS vrel{i}
        WITH id_affaire, {', '.join(nodes)}, {', '.join(vrels)}, vrel{i}, p{i+1}
        """
        nodes.append(f"p{i+1}")
        vrels.append(f"vrel{i}")

    # Finalize the query to return nodes and relationships
    query += f"""
    WITH apoc.coll.toSet([{', '.join(nodes)}]) AS allNodes,
         apoc.coll.toSet([{', '.join(vrels)}]) AS allRels
    UNWIND allNodes AS node
    UNWIND allRels AS rel
    RETURN {{
        nodes: COLLECT(DISTINCT node),
        relationships: COLLECT(DISTINCT rel)
    }} AS graph
    """

    # Debugging: Print the generated query
    print(query)

    # Execute the query with parameters
    params = {
        "id_affaires": id_affaires,
        "depth": depth,
        "rel_type": rel_type
    }
    
    try:
        data = parse_to_graph_with_transformer(query, params)
        # print("rel1", data)

        # Post-process to remove duplicate virtual relationships
        if data and 'nodes' in data and 'edges' in data:
            filtered_relationships = []
            seen_node_pairs = set()

            for rel in data['edges']:
                # Extract start and end node IDs (assuming relationships have 'startNode' and 'endNode')

                print("rel2", rel)
                start_node = rel.get('startNode')
                end_node = rel.get('endNode')
                node_pair = (start_node, end_node)

                # Only keep the first relationship for each node pair
                if node_pair not in seen_node_pairs:
                    filtered_relationships.append(rel)
                    seen_node_pairs.add(node_pair)

            # Update the data with filtered relationships
            data['edges'] = filtered_relationships

        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@api_view(['POST'])
def aggregate_with_algo_old(request):
    # Extract the id_affaires and depth from the request body
    id_affaires = request.data.get('id_affaires', [1171])  # Default value if not provided
    depth = int(request.data.get('depth', 3))  # Default depth if not provided

    # Validate depth
    if depth < 1:
        return JsonResponse({"error": "Depth must be at least 1."}, status=400)

    # Initialize the query variable
    query = """
    UNWIND $id_affaires AS id_affaire
    MATCH (c:Affaire)-[:Impliquer]-(p1:Personne)
    WHERE c.identity = id_affaire
    """

    # Dynamically build the query for the given depth
    nodes = ["COLLECT(DISTINCT {identity: c.identity, type: 'Affaire'})", 
             "COLLECT(DISTINCT {identity: p1.identity, type: 'Personne'})"]
    relations = ["COLLECT(DISTINCT {source: c.identity, target: p1.identity, relation: 'Impliquer'})"]

    for i in range(1, depth):
        query += f"""
        MATCH (p{i})-[:Proprietaire]-(:Phone)-[:Appel_telephone]-(:Phone)-[:Proprietaire]-(p{i+1}:Personne)
        WHERE id_affaire IN p{i+1}._affiresoutin AND p{i+1}._Lvl_of_Implications[{i}] > p{i}._Lvl_of_Implications[{i-1}]
        """
        nodes.append(f"COLLECT(DISTINCT {{identity: p{i+1}.identity, type: 'Personne'}})")
        relations.append(f"COLLECT(DISTINCT {{source: p{i}.identity, target: p{i+1}.identity, relation: 'Contact with phone'}})")

    # Finalize the query
    query += f"""
    WITH 
        {' + '.join(nodes)} AS nodes,
        {' + '.join(relations)} AS relations
    RETURN {{
        nodes: nodes,
        relations: relations
    }} AS Result;
    """

    # Print the query for debugging
    # print("identity : ", id_affaires)
    print(query)

    # Execute the query using the run_query function
    params = {"id_affaires": id_affaires, "depth": depth}
    data = run_query(query, params)

    # print('result : ', data)

    # Return the result as a JSON response
    return JsonResponse(data, safe=False)




