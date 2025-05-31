from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import neo4j

# from graph.utility import  driver
from graph.Utility_QueryExecutors import parse_to_graph_with_transformer,run_query





@api_view(['POST'])
def aggregate(request):
    """
    Aggregates nodes and relationships based on given node IDs and aggregation type.

    The aggregation type is a list of lists, where each sublist represents a node-relationship-node pattern.
    The sublist must have an odd length, with the first and last elements being node types and the middle
    elements being relationship types.

    The response is a JSON object with two keys: "nodes" and "relationships". The "nodes" key contains a list
    of objects with the following properties: "id", "type", "properties", and "aggregated_properties". The
    "relationships" key contains a list of objects with the following properties: "startId", "endId", "type",
    and "count".

    If the query fails, a 500 status code is returned with an error message.

    :param request: The request object containing the node IDs and aggregation type.
    :return: A JSON response with the aggregated nodes and relationships.
    """
    id_nodes = request.data.get("node_ids", [1160, 126224, 129664, 129668, 136220, 1368, 1370, 34151, 34155])  # List of node IDs
    aggregation_path = request.data.get("aggregation_path", [["Personne", "Impliquer", "Affaire", "Impliquer", "Personne"]])
    type = request.data.get("type","memeaffaire")
    if not id_nodes:
        return Response({"error": "id_nodes parameter is required"}, status=400)

    print(id_nodes)
    query_parts = []
    params = {"id_nodes": id_nodes}
    alias_counter = {}  # Dictionary to track alias counts

    def get_alias(name):
        """
        Generate a unique alias based on the first letter of the node type.

        :param name: The node type to generate an alias for.
        :return: A unique alias for the node type.
        """
        """Generate a unique alias based on the first letter of the node type."""
        first_letter = name[0].upper()  # Take the first character and capitalize
        alias_counter[first_letter] = alias_counter.get(first_letter, 0) + 1
        return f"{first_letter}{alias_counter[first_letter]}"

    for sublist in aggregation_path:
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










