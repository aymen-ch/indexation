from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from datetime import datetime
import uuid
from graph.views import run_query

@api_view(['POST'])
def get_daira_and_commune(request):
    wilaya_name = request.data.get('wilaya_name', '').strip()
    if not wilaya_name:
        return JsonResponse({"error": "Wilaya name is required."}, status=400)
    query = """
    MATCH (w:Wilaya {nom_francais: $wilaya_name})<-[:appartient]-(d:Daira)<-[:appartient]-(c:Commune)
    RETURN d.nom_francais AS daira_name, collect(c.nom_francais) AS communes
    """
    params = {'wilaya_name': wilaya_name}

    try:
        result = run_query(query, params)
        if not result:
            return JsonResponse({"error": "No data found for the given wilaya."}, status=404)
        
        # Format the response
        response_data = {
            "wilaya_name": wilaya_name,
            "dairas": [
                {
                    "daira_name": record['daira_name'],
                    "communes": record['communes']
                } for record in result
            ]
        }
        return JsonResponse(response_data, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
def get_all_affaire_types(request):
    """
    Get all distinct 'Affaire' types from the database.
    """
    try:
        # Cypher query to get all distinct 'Affaire' types
        query = """
        MATCH (a:Affaire)
        RETURN DISTINCT a.Type AS affaire_type
        """
        
        # Execute the query using the utility function
        results = run_query(query, {})
        
        # Extract affaire types from the results
        affaire_types = [record["affaire_type"] for record in results]
        
        # Return the response as a JSON
        return JsonResponse({"affaire_types": affaire_types}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['POST'])
def count_affaires(request):
    try:
        affaire_types = request.data.get('Affaire_type', [])
        wilaya_id = request.data.get('wilaya_id', None)
        daira_id = request.data.get('daira_id', None)
        commune_id = request.data.get('commune_id', None)
        start_date = request.data.get('startDate', None)
        end_date = request.data.get('endDate', None)
        if not affaire_types:
            return JsonResponse({"error": "At least one Affaire_type is required."}, status=400)
        print(wilaya_id)
        match_clause = """
        MATCH (crime:Affaire)
        WHERE crime.Type IN $affaire_types
        """
        if wilaya_id is not None:
            match_clause += """
            MATCH (crime)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya)
            WHERE ID(w) = $wilaya_id
            """
            if daira_id is not None:
                match_clause += """
                AND ID(d) = $daira_id
                """
                if commune_id is not None:
                    match_clause += """
                    AND ID(c) = $commune_id
                    """
        if start_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) >= date($start_date)
            """
        if end_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) <= date($end_date)
            """
        query = f"""
        {match_clause}
        RETURN count(crime) AS total_affaires
        """
        params = {
            "affaire_types": affaire_types,
            "wilaya_id": wilaya_id,
            "daira_id": daira_id,
            "commune_id": commune_id,
            "start_date": start_date,
            "end_date": end_date
        }
        result = run_query(query, params)
        return JsonResponse({"total_affaires": result[0]["total_affaires"]}, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
@api_view(['POST'])
def filter_affaire_relations(request):
    try:
        # Extract parameters from the request
        affaire_types = request.data.get('Affaire_type', [])  # Required list of types
        wiliaya_id = request.data.get('wilaya_id', None)
        daira_id = request.data.get('daira_id', None)
        commune_id = request.data.get('commune_id', None)
        start_date = request.data.get('startDate', None)
        end_date = request.data.get('endDate', None)
        node_types = request.data.get('selectedNodeTypes', [])  # Optional list of types
        depth = int(request.data.get('depth', 1))  # Default depth is 1

        print("Node types:", node_types)
        # Validate required parameters
        if not affaire_types:  # Check if the list is empty
            return JsonResponse({"error": "At least one Affaire_type is required."}, status=400)

        # Construct label filter for apoc.path.expandConfig
        label_filter = "-Affaire"  # Always exclude Affaire
        if node_types:  # If specific node types are provided, whitelist them
            label_filter = f"{'|'.join('+' + nt for nt in node_types)},-Affaire"

        print("Label filter:", label_filter)
        # Base MATCH clause to get the starting crime node
        match_clause = """
        MATCH (crime:Affaire)
        WHERE crime.Type IN $affaire_types
        """

        # Add filters for optional parameters (using ID instead of identity)
        if wiliaya_id is not None:
            match_clause += """
            MATCH (crime)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya)
            WHERE ID(w) = $wiliaya_id
            """
            if daira_id is not None:
                match_clause += """
                AND ID(d) = $daira_id
                """
                if commune_id is not None:
                    match_clause += """
                    AND ID(c) = $commune_id
                    """

        if start_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) >= date($start_date)
            """
        if end_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) <= date($end_date)
            """

        # Complete query with apoc.path.expandConfig using ID instead of identity
        query = f"""
        {match_clause}
        CALL apoc.path.expandConfig(crime, {{
            minLevel: 0,
            maxLevel: $depth,
            uniqueness: 'NODE_PATH',
            labelFilter: '{label_filter}'
        }}) YIELD path
        WITH crime,
             [node IN nodes(path) | node] AS path_nodes,
             [rel IN relationships(path) | rel] AS path_rels
        RETURN {{
            id: ID(crime),
            properties: properties(crime)
        }} AS crime,
               COLLECT({{
                   id: ID(path_nodes[-1]), 
                   labels: labels(path_nodes[-1]), 
                   properties: properties(path_nodes[-1])
               }}) AS collected_nodes,
               COLLECT({{
                   id: toString(ID(path_rels[-1])), 
                   type: type(path_rels[-1]), 
                   properties: properties(path_rels[-1]), 
                   startId: ID(startNode(path_rels[-1])), 
                   endId: ID(endNode(path_rels[-1]))
               }}) AS collected_relations
        """

        # Set query parameters
        params = {
            "affaire_types": affaire_types,
            "wiliaya_id": wiliaya_id,
            "daira_id": daira_id,
            "commune_id": commune_id,
            "start_date": start_date,
            "end_date": end_date,
            "depth": depth
        }

        print("Params:", params)
        print("Query:", query)
        # Execute the query
        print("Start execution")
        results = run_query(query, params)

        # Format the results
        formatted_results = []
        for record in results:
            crime = record["crime"]
            nodes = record["collected_nodes"]
            relations = record["collected_relations"]

            # Filter nodes based on selected node_types
            filtered_nodes = []
            filtered_node_ids = set()
            for node in nodes:
                node_labels = node["labels"]
                if not node_types or any(label in node_types for label in node_labels):
                    node_type = next((label for label in node_labels if label in node_types), node_labels[0] if node_labels else "Unknown")
                    filtered_nodes.append({
                        "node_type": node_type,
                        "id": str(node["id"]),  # Use Neo4j ID as string
                        "properties": node["properties"]
                    })
                    filtered_node_ids.add(node["id"])

            # Include the crime node explicitly
            filtered_nodes.append({
                "node_type": "Affaire",
                "id": str(crime["id"]),
                "properties": crime["properties"]
            })
            filtered_node_ids.add(crime["id"])

            # Filter relations
            filtered_relations = [
                rel for rel in relations
                if rel["startId"] in filtered_node_ids and rel["endId"] in filtered_node_ids
            ]

            # Remove duplicate relations
            unique_relations = {}
            for rel in filtered_relations:
                unique_relations[(rel["startId"], rel["endId"], rel["type"])] = rel
            formatted_edges = list(unique_relations.values())

            # Ensure nodes are connected to the crime node
            connected_node_ids = set()
            nodes_to_process = {crime["id"]}
            while nodes_to_process:
                current_node_id = nodes_to_process.pop()
                connected_node_ids.add(current_node_id)
                for rel in formatted_edges:
                    if rel["startId"] == current_node_id and rel["endId"] not in connected_node_ids:
                        nodes_to_process.add(rel["endId"])
                    elif rel["endId"] == current_node_id and rel["startId"] not in connected_node_ids:
                        nodes_to_process.add(rel["startId"])

            # Final filtering
            final_nodes = [
                node for node in filtered_nodes 
                if int(node["id"]) in connected_node_ids
            ]
            final_edges = [
                rel for rel in formatted_edges
                if rel["startId"] in connected_node_ids and rel["endId"] in connected_node_ids
            ]

            # Add formatted result
            formatted_results.append({
                "affaire": {
                    "id": str(crime["id"]),
                    "properties": crime["properties"]
                },
                "nodes": final_nodes,
                "relations": final_edges  # Renamed from "relations" to "edges"
            })

        # Sort by date with error handling
        def get_date_key(item):
            try:
                return datetime.strptime(item["affaire"]["properties"]["date"], "%d-%m-%Y")
            except (KeyError, ValueError, TypeError):
                return datetime.min  # Fallback for missing or invalid dates

        formatted_results.sort(key=get_date_key)

        print("End execution")
        print("Formatted results:", formatted_results)
        return JsonResponse({"results": formatted_results}, safe=False)

    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

# @api_view(['POST'])
# def filter_affaire_relation_old(request):
#     try:
#         # Extract parameters from the request
#         affaire_type = request.data.get('Affaire_type')  # Required
#         wiliaya_id = request.data.get('wilaya_id', None)
#         daira_id = request.data.get('daira_id', None)
#         commune_id = request.data.get('commune_id', None)
#         start_date = request.data.get('startDate', None)
#         end_date = request.data.get('endDate', None)
#         node_types = request.data.get('selectedNodeTypes', [])  # Optional list of types
#         depth = int(request.data.get('depth', 1))  # Default depth is 1
#         print(request.data)

#         # Validate required parameters
#         if not affaire_type:
#             return JsonResponse({"error": "Affaire_type is required."}, status=400)

#         # Remove 'Affaire' from node_types if present, as it is implied by the match clause
#         if 'Affaire' in node_types:
#             node_types.remove('Affaire')

#         # Base MATCH clause for crime relationships
#         match_clause = f"""
#         MATCH (crime:Affaire)-[r*..{depth}]-(n)
#         WHERE crime.Type = $affaire_type
#         """

#         # Add filters for optional parameters
#         if wiliaya_id:
#             match_clause += """
#             MATCH (crime:Affaire)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya)
#             WHERE ID(w) = $wiliaya_id
#             """
#             if daira_id:
#                 match_clause += """
#                 AND ID(d) = $daira_id
#                 """
#                 if commune_id:
#                     match_clause += """
#                     AND ID(c) = $commune_id
#                     """

#         if start_date:
#             match_clause += """
#             AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) >= date($start_date)
#             """
#         if end_date:
#             match_clause += """
#             AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) <= date($end_date)
#             """

#         # Combine the full query using ID instead of identity
#         query = f"""
#         {match_clause}
#         WITH crime,
#             COLLECT(n) AS nodes,
#             COLLECT(labels(n)) AS node_labels,
#             COLLECT([rel IN r | {{
#                 id: ID(rel), 
#                 type: type(rel), 
#                 properties: properties(rel), 
#                 startId: ID(startNode(rel)), 
#                 endId: ID(endNode(rel))
#             }}]) AS relations
#         RETURN {{
#             id: ID(crime),
#             properties: properties(crime)
#         }} AS crime,
#             nodes,
#             relations,
#             node_labels
#         """

#         print(query)
#         # Set query parameters
#         params = {
#             "affaire_type": affaire_type,
#             "wiliaya_id": wiliaya_id,
#             "daira_id": daira_id,
#             "commune_id": commune_id,
#             "start_date": start_date,
#             "end_date": end_date,
#         }

#         # Execute the query
#         results = run_query(query, params)

#         # Format the results
#         formatted_results = []
#         for record in results:
#             crime = record["crime"]
#             nodes = record["nodes"]
#             relations = record["relations"]
#             node_labels = record["node_labels"]

#             # Filter nodes based on selected node_types
#             filtered_nodes = []
#             for node, labels in zip(nodes, node_labels):
#                 if not node_types or any(node_type in labels for node_type in node_types):
#                     filtered_nodes.append((node, labels))  # Store node and labels together

#             # Format nodes with their Neo4j ID
#             formatted_nodes = []
#             filtered_node_ids = set()  # Use Neo4j IDs instead of identity
#             for node, labels in filtered_nodes:
#                 node_type = "Unknown"
#                 for label in labels:
#                     if not node_types or label in node_types:
#                         node_type = label
#                         break
#                 node_id = node.id  # Neo4j internal ID (neo4j.graph.Node object)
#                 formatted_nodes.append({
#                     "node_type": node_type,
#                     "id": str(node_id),  # Convert to string for JSON
#                     "properties": dict(node)  # Convert node properties to dict
#                 })
#                 filtered_node_ids.add(node_id)

#             # Flatten and filter relations
#             flat_relations = [rel for sublist in relations for rel in sublist]
#             filtered_relations = [
#                 rel for rel in flat_relations
#                 if (
#                     (rel["startId"] in filtered_node_ids and rel["endId"] in filtered_node_ids)
#                     or (rel["startId"] == crime["id"] and rel["endId"] in filtered_node_ids)
#                     or (rel["endId"] == crime["id"] and rel["startId"] in filtered_node_ids)
#                 )
#             ]

#             # Remove duplicate relations
#             unique_relations = {}
#             for rel in filtered_relations:
#                 unique_relations[(rel["startId"], rel["endId"], rel["type"])] = rel

#             formatted_relations = list(unique_relations.values())

#             # Extract unique node IDs from filtered relations
#             relation_node_ids = set()
#             for rel in formatted_relations:
#                 relation_node_ids.add(rel["startId"])
#                 relation_node_ids.add(rel["endId"])

#             # Ensure nodes are connected to the crime node
#             connected_node_ids = set()
#             nodes_to_process = {crime["id"]}  # Use crime's Neo4j ID

#             while nodes_to_process:
#                 current_node_id = nodes_to_process.pop()
#                 connected_node_ids.add(current_node_id)
#                 for rel in formatted_relations:
#                     if rel["startId"] == current_node_id and rel["endId"] not in connected_node_ids:
#                         nodes_to_process.add(rel["endId"])
#                     elif rel["endId"] == current_node_id and rel["startId"] not in connected_node_ids:
#                         nodes_to_process.add(rel["startId"])

#             # Filter nodes and relations based on connectivity
#             filtered_formatted_nodes = [
#                 node for node in formatted_nodes if int(node["id"]) in connected_node_ids
#             ]
#             final_filtered_relations = [
#                 rel for rel in formatted_relations
#                 if rel["startId"] in connected_node_ids and rel["endId"] in connected_node_ids
#             ]

#             # Add the formatted crime with filtered nodes and relations
#             formatted_results.append({
#                 "affaire": {
#                     "id": str(crime["id"]),  # Use Neo4j ID as string
#                     "properties": crime["properties"]
#                 },
#                 "nodes": filtered_formatted_nodes,
#                 "relations": final_filtered_relations
#             })

#         # Sort by date
#         formatted_results.sort(key=lambda x: datetime.strptime(x["affaire"]["properties"]["date"], "%d-%m-%Y"))
#         print(formatted_results)

#         # Return the response
#         return JsonResponse({"results": formatted_results}, safe=False)

#     except Exception as e:
#         print(f"Error: {e}")
#         return JsonResponse({"error": str(e)}, status=500)

@api_view(['GET'])
def get_all_wilaya(request):
    """
    Retrieve all Wilaya.
    """
    try:
        query = """
        MATCH (w:Wilaya)
        RETURN w.nom_francais AS wilaya_name, id(w) AS wilaya_id
        ORDER BY w.nom_francais
        """
        results = run_query(query)
        wilaya_list = [{"wilaya_id": record["wilaya_id"], "wilaya_name": record["wilaya_name"]} for record in results]
        return JsonResponse({"wilaya": wilaya_list}, safe=False)
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['POST'])
def get_daira_by_wilaya(request):
    """
    Retrieve all Daira for a specific Wilaya.
    """
    try:
        wilya_id = request.data.get("wilaya")  # Query parameter
        if not wilya_id:
            return JsonResponse({"error": "wilya_id is required."}, status=400)
        print(wilya_id)
        query = """
        MATCH (w:Wilaya)<-[:appartient]-(d:Daira)
        WHERE id(w) = $wilya_id
        RETURN d.nom_francais AS daira_name, id(d) AS daira_id
        ORDER BY d.nom_francais
        """
        params = {"wilya_id": wilya_id}
        results = run_query(query, params)
        daira_list = [{"daira_id": record["daira_id"], "daira_name": record["daira_name"]} for record in results]
        return JsonResponse({"daira": daira_list}, safe=False)
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)
@api_view(['POST'])
def get_commune_by_wilaya_and_daira(request):
    """
    Retrieve all Commune for a specific Wilaya and Daira.
    """
    try:
        wilaya_id = request.data.get("wilaya")  # Query parameter
        daira_id = request.data.get("daira")    # Query parameter

        if not wilaya_id or not daira_id:
            return JsonResponse({"error": "wilaya_id and daira_id are required."}, status=400)
     
        query = """
        MATCH (w:Wilaya)<-[:appartient]-(d:Daira)<-[:appartient]-(c:Commune)
        WHERE id(w) = $wilaya_id AND id(d) = $daira_id
        RETURN c.nom_francais AS commune_name, id(c) AS commune_id
        ORDER BY c.nom_francais
        """
        params = {"wilaya_id": wilaya_id, "daira_id": daira_id}
        results = run_query(query, params)
        commune_list = [{"commune_id": record["commune_id"], "commune_name": record["commune_name"]} for record in results]
        return JsonResponse({"commune": commune_list}, safe=False)
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

