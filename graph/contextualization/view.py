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
def filter_affaire_relations(request):
    try:
        # Extract parameters from the request
        affaire_type = request.data.get('Affaire_type')  # Required
        wiliaya_id = request.data.get('wilaya_id', None)
        daira_id = request.data.get('daira_id', None)
        commune_id = request.data.get('commune_id', None)
        start_date = request.data.get('startDate', None)
        end_date = request.data.get('endDate', None)
        node_types = request.data.get('selectedNodeTypes', [])  # Optional list of types
        depth = int(request.data.get('depth', 1))  # Default depth is 1

        # Validate required parameters
        if not affaire_type:
            return JsonResponse({"error": "Affaire_type is required."}, status=400)

        # Base MATCH clause to get the starting crime node
        match_clause = """
        MATCH (crime:Affaire)
        WHERE crime.Type = $affaire_type
        """

        # Add filters for optional parameters
        if wiliaya_id:
            match_clause += """
            MATCH (crime)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya)
            WHERE w.identity = $wiliaya_id
            """
            if daira_id:
                match_clause += """
                AND d.identity = $daira_id
                """
                if commune_id:
                    match_clause += """
                    AND c.identity = $commune_id
                    """

        if start_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) >= date($start_date)
            """
        if end_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) <= date($end_date)
            """

        # Complete query with apoc.path.expandConfig
        query = f"""
        {match_clause}
        CALL apoc.path.expandConfig(crime, {{
            minLevel: 0,
            maxLevel: $depth,
            uniqueness: 'NODE_PATH'
        }}) YIELD path
        WITH crime, 
             [node IN nodes(path) | node] AS path_nodes,
             [rel IN relationships(path) | rel] AS path_rels
        WITH crime,
             path_nodes AS nodes,
             path_rels AS relations
        RETURN crime,
               COLLECT({{
                   identity: id(nodes[-1]), 
                   labels: labels(nodes[-1]), 
                   properties: properties(nodes[-1])
               }}) AS collected_nodes,
               COLLECT({{
                   identity: id(relations[-1]), 
                   type: type(relations[-1]), 
                   properties: properties(relations[-1]), 
                   startId: id(startNode(relations[-1])), 
                   endId: id(endNode(relations[-1]))
               }}) AS collected_relations
        """

        # Set query parameters
        params = {
            "affaire_type": affaire_type,
            "wiliaya_id": wiliaya_id,
            "daira_id": daira_id,
            "commune_id": commune_id,
            "start_date": start_date,
            "end_date": end_date,
            "depth": depth
        }

        # Execute the query
        print("start excution")
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
                        "properties": node["properties"]
                    })
                    filtered_node_ids.add(node["identity"])

            # Filter relations
            filtered_relations = [
                rel for rel in relations
                if (
                    (rel["startId"] in filtered_node_ids and rel["endId"] in filtered_node_ids)
                    or (rel["startId"] == crime["identity"] and rel["endId"] in filtered_node_ids)
                    or (rel["endId"] == crime["identity"] and rel["startId"] in filtered_node_ids)
                )
            ]

            # Remove duplicate relations
            unique_relations = {}
            for rel in filtered_relations:
                unique_relations[(rel["startId"], rel["endId"], rel["type"])] = rel
            formatted_relations = list(unique_relations.values())

            # Ensure nodes are connected to the crime node
            connected_node_ids = set()
            nodes_to_process = {crime["identity"]}

            while nodes_to_process:
                current_node_id = nodes_to_process.pop()
                connected_node_ids.add(current_node_id)
                for rel in formatted_relations:
                    if rel["startId"] == current_node_id and rel["endId"] not in connected_node_ids:
                        nodes_to_process.add(rel["endId"])
                    elif rel["endId"] == current_node_id and rel["startId"] not in connected_node_ids:
                        nodes_to_process.add(rel["startId"])

            # Final filtering
            final_nodes = [
                node for node in filtered_nodes 
                if node["properties"]["identity"] in connected_node_ids
            ]
            final_relations = [
                rel for rel in formatted_relations
                if rel["startId"] in connected_node_ids and rel["endId"] in connected_node_ids
            ]

            # Add formatted result
            formatted_results.append({
                "affaire": crime,
                "nodes": final_nodes,
                "relations": final_relations
            })

        # Sort by date
        formatted_results.sort(key=lambda x: datetime.strptime(x["affaire"]["date"], "%d-%m-%Y"))

        print("END excution")
        return JsonResponse({"results": formatted_results}, safe=False)

    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    

@api_view(['POST'])
def filter_affaire_relation_old(request):
    try:
        # Extract parameters from the request
        affaire_type = request.data.get('Affaire_type')  # Required
        wiliaya_id = request.data.get('wilaya_id', None)
        daira_id = request.data.get('daira_id', None)
        commune_id = request.data.get('commune_id', None)
        start_date = request.data.get('startDate', None)
        end_date = request.data.get('endDate', None)
        node_types = request.data.get('selectedNodeTypes')  # Optional list of types (e.g., ['Personne', 'Affaire'])
        depth = int(request.data.get('depth', 1))  # Default depth is 1
        print(request.data)
        # Validate required parameters
        if not affaire_type:
            return JsonResponse({"error": "Affaire_type is required."}, status=400)

        # Remove 'Affaire' from node_types if present, as it is implied by the match clause
        if 'Affaire' in node_types:
            node_types.remove('Affaire')

        # Base MATCH clause for crime relationships
        match_clause = f"""
        MATCH (crime:Affaire)-[r*..{depth}]-(n)
        WHERE  crime.Type = $affaire_type 
        """
        # Add filters for optional parameters
        if wiliaya_id:
            match_clause += """
            MATCH (crime:Affaire)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya)
            WHERE w.identity = $wiliaya_id
            """
            if daira_id:
                match_clause += """
                AND d.identity = $daira_id
                """
                if commune_id:
                    match_clause += """
                    AND c.identity = $commune_id
                    """

        if start_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) >= date($start_date)
            """
        if end_date:
            match_clause += """
            AND date(substring(crime.date, 6, 4) + "-" + substring(crime.date, 3, 2) + "-" + substring(crime.date, 0, 2)) <= date($end_date)
            """

        # Filter node types if specified

        # Combine the full query
        query = f"""
        {match_clause}
        WITH crime,
            COLLECT( n) AS nodes,
            COLLECT( labels(n)) AS node_labels,
            COLLECT([rel IN r | {{
                identity: rel.identity, 
                type: type(rel), 
                properties: properties(rel), 
                startId: startNode(rel).identity, 
                endId: endNode(rel).identity
            }}]) AS relations
            RETURN crime,
                nodes,
                relations,
                node_labels
        """

        print(query)
        # Set query parameters
        params = {
            "affaire_type": affaire_type,
            "wiliaya_id": wiliaya_id,
            "daira_id": daira_id,
            "commune_id": commune_id,
            "start_date": start_date,
            "end_date": end_date,
        }

        # Execute the query
        results = run_query(query, params)

        # Format the results
        formatted_results = []
        for record in results:
            crime = record["crime"]
            nodes = record["nodes"]
            relations = record["relations"]
            node_labels = record["node_labels"]
            # Step 2: Filter nodes based on the selected node_types while preserving their labels
            filtered_nodes = []
            for node, labels in zip(nodes, node_labels):
                if any(node_type in labels for node_type in node_types):
                    filtered_nodes.append((node, labels))  # Store both node and labels together
            formatted_nodes = []
            filtered_node_ids = set()  # Set to store filtered node identities
            for node, labels in filtered_nodes:
                node_type = "Unknown"  # Default value if no matching type is found
                for label in labels:
                    if label in node_types:
                        node_type = label  # Assign the first matching label
                        break  # Exit loop once the label is found
                formatted_nodes.append({
                    "node_type": node_type,
                    "properties": node
                })
                filtered_node_ids.add(node["identity"])
            # Flatten the list of lists
            flat_relations = [rel for sublist in relations for rel in sublist]

            # Filter relations to include only those where both startId and endId are in filtered_node_ids
            filtered_relations = [
                rel for rel in flat_relations
                if (
                    (rel["startId"] in filtered_node_ids and rel["endId"] in filtered_node_ids)
                    or (rel["startId"] == crime["identity"] and rel["endId"] in filtered_node_ids)
                    or (rel["endId"] == crime["identity"] and rel["startId"] in filtered_node_ids)
                )
            ]

            # Remove duplicate relations
            unique_relations = {}
            for rel in filtered_relations:
                unique_relations[(rel["startId"], rel["endId"], rel["type"])] = rel

            formatted_relations = list(unique_relations.values())

            # Extract unique node IDs from filtered relations
            relation_node_ids = set()
            for rel in formatted_relations:
                relation_node_ids.add(rel["startId"])
                relation_node_ids.add(rel["endId"])

            # Ensure nodes are connected to the crime node
            connected_node_ids = set()
            nodes_to_process = {crime["identity"]}  # Start from the crime node

            # Pour éliminer les sous-graphes qui n'ont pas de relation avec l'affaire
            while nodes_to_process:
                current_node_id = nodes_to_process.pop()
                connected_node_ids.add(current_node_id)
                # Add neighbors connected by relations
                for rel in formatted_relations:
                    if rel["startId"] == current_node_id and rel["endId"] not in connected_node_ids:
                        nodes_to_process.add(rel["endId"])
                    elif rel["endId"] == current_node_id and rel["startId"] not in connected_node_ids:
                        nodes_to_process.add(rel["startId"])

            # Filter nodes to include only those connected to the crime node
            filtered_formatted_nodes = [
                node for node in formatted_nodes if node["properties"]["identity"] in connected_node_ids
            ]

            # Filter relations to include only those where both startId and endId are in filtered_formatted_nodes
            final_filtered_relations = [
                rel for rel in formatted_relations
                if rel["startId"] in connected_node_ids and rel["endId"] in connected_node_ids
            ]
            
           
            # Add the formatted crime with filtered nodes and relations
            formatted_results.append({
                "affaire": crime,
                "nodes": filtered_formatted_nodes,
                "relations": final_filtered_relations
            })
            formatted_results.sort(key=lambda x: datetime.strptime(x["affaire"]["date"], "%d-%m-%Y"))

        # Return the response
        return JsonResponse({"results": formatted_results}, safe=False)

    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['GET'])
def get_all_wilaya(request):
    """
    Retrieve all Wilaya.
    """
    try:
        query = """
        MATCH (w:Wilaya)
        RETURN w.nom_francais AS wilaya_name, w.identity AS wilaya_id
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
        WHERE w.identity = $wilya_id
        RETURN d.nom_francais AS daira_name, d.identity AS daira_id
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
        WHERE w.identity = $wilaya_id AND d.identity = $daira_id
        RETURN c.nom_francais AS commune_name, c.identity AS commune_id
        ORDER BY c.nom_francais
        """
        params = {"wilaya_id": wilaya_id, "daira_id": daira_id}
        results = run_query(query, params)
        commune_list = [{"commune_id": record["commune_id"], "commune_name": record["commune_name"]} for record in results]
        return JsonResponse({"commune": commune_list}, safe=False)
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

