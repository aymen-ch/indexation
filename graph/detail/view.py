

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
from graph.utility_neo4j  import run_query
@api_view(['POST'])
def getdata(request):
    identity = request.data.get('identity')
    if not identity:
        return Response(
            {"error": "Identity is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        query = """
        MATCH (n)  where id(n) = $identity RETURN n 
        """
        results = run_query(query, {"identity": identity}, database=settings.NEO4J_DATABASE)
        if not results:
            return Response(
                {"error": "Node not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        node_data = results[0]["n"]
        return Response(node_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def getrelationData(request):
    identity = request.data.get('identity')
    path = request.data.get('path')
    print(f"Identity: {identity}, Path: {path}")
    
    if not identity:
        return Response(
            {"error": "Identity is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        if isinstance(identity, str) and '-' in identity:
            if not path or not isinstance(path, list) or len(path) % 2 == 0 or len(path) < 3:
                return Response(
                    {"error": "A valid path array with odd length >= 3 is required for virtual relations."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                start_id, end_id = map(int, identity.split('-'))
            except ValueError:
                return Response(
                    {"error": "Virtual relation identity must contain valid integers separated by hyphen."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Calculate the index of the middle relation
            num_relations = (len(path) - 1) // 2  # Number of relations
            middle_rel_index = num_relations // 2  # Index of the middle relation
            middle_relation = path[middle_rel_index * 2 + 1]  # Middle relation type
            
            match_clauses = []
            for i in range(0, len(path) - 1, 2):
                    node1 = path[i]
                    rel = path[i + 1]
                    node2 = path[i + 2]
                    
                    # Node variables should be unique and sequential
                    n1_var = f"n{i//2}"
                    n2_var = f"n{i//2 + 1}"
                    rel_var = "r" if i // 2 == middle_rel_index else f"r{i//2}"
                    print(rel_var)
                    if i == 0:
                        if len(path) == 3:  # Special case for length 3
                            pattern = f"({n1_var}:{node1} WHERE id({n1_var}) = $start_id)-[{rel_var}:{rel}]-({n2_var}:{node2} WHERE id({n2_var}) = $end_id)"
                        else:
                            # First segment with start_id
                            pattern = f"({n1_var}:{node1} WHERE id({n1_var}) = $start_id)-[{rel_var}:{rel}]-({n2_var}:{node2})"
                    else:
                        # Subsequent segments
                        pattern = f"-[{rel_var}:{rel}]-({n2_var}:{node2})"
                        if i == len(path) - 3:
                            pattern = f"-[{rel_var}:{rel}]-({n2_var}:{node2} WHERE id({n2_var}) = $end_id)"
                    
                    match_clauses.append(pattern)

            # Join the clauses into a single continuous path
            query = (
                f"MATCH {''.join(match_clauses)}\n"
                "WITH collect(r) as relations\n"
                f"RETURN {{type: '{middle_relation}', count: size(relations), detail: [rel in relations | {{identity: rel.identity, properties: properties(rel)}}]}} as relation_data"
            )
            print(query)
            
            results = run_query(query, {"start_id": start_id, "end_id": end_id}, database=settings.NEO4J_DATABASE)
            if not results:
                return Response(
                    {"error": "Virtual relation not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            relation_data = results[0]["relation_data"]
            formatted_relation = {
                "type": relation_data["type"],
                "count": relation_data["count"],
                "identity": identity,
                "detail": {
                    f"{middle_relation.lower()}{i+1}": rel 
                    for i, rel in enumerate(relation_data["detail"])
                }
            }
            print(relation_data)
            return Response(formatted_relation, status=status.HTTP_200_OK)

        else:
            try:
                identity = int(identity)
            except ValueError:
                return Response(
                    {"error": "Normal relation identity must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            print("identity21",identity)
            query = """
            MATCH ()-[n]->()
            WHERE id(n) = $identity
            RETURN {
                identity:  toString(id(n)),
                type: type(n),
                properties: properties(n)
            } as relation_data
            """
            results = run_query(query, {"identity": identity}, database=settings.NEO4J_DATABASE)
            if not results:
                return Response(
                    {"error": "Node not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            relation_data = results[0]["relation_data"]
            return Response(relation_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['GET'])
def node_type_analysis(request):
    try:
        # Step 1: Fetch all distinct node types
        label_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH DISTINCT label
        RETURN label
        """
        label_results = run_query(label_query, database=settings.NEO4J_DATABASE)
        node_types = [record["label"] for record in label_results]

        if not node_types:
            return Response(
                {"error": "No node types found in the database."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Step 2: Analyze each node type
        response_data = []
        for node_type in node_types:
            # Query to compute analytical properties
            analysis_query = f"""
            MATCH (n:{node_type})
            OPTIONAL MATCH (n)<-[r_in]-()
            OPTIONAL MATCH (n)-[r_out]->()
            WITH n, 
                 COUNT(r_in) AS incoming_links,
                 COUNT(r_out) AS outgoing_links,
                 COLLECT(r_in) AS incoming_rels,
                 COLLECT(r_out) AS outgoing_rels
            WITH incoming_links,
                 outgoing_links,
                 incoming_rels,
                 outgoing_rels,
                 [rel IN incoming_rels | [k IN keys(rel) WHERE k <> 'identity' AND apoc.meta.type(rel[k]) IN ['INTEGER', 'LONG', 'FLOAT', 'DOUBLE'] | rel[k]]] AS in_values,
                 [rel IN outgoing_rels | [k IN keys(rel) WHERE k <> 'identity' AND apoc.meta.type(rel[k]) IN ['INTEGER', 'LONG', 'FLOAT', 'DOUBLE'] | rel[k]]] AS out_values
            WITH incoming_links,
                 outgoing_links,
                 REDUCE(s = 0, vals IN in_values | s + REDUCE(inner_s = 0, v IN vals | inner_s + COALESCE(v, 0))) AS sum_incoming_values,
                 REDUCE(s = 0, vals IN out_values | s + REDUCE(inner_s = 0, v IN vals | inner_s + COALESCE(v, 0))) AS sum_outgoing_values
            RETURN incoming_links,
                   outgoing_links,
                   sum_incoming_values,
                   sum_outgoing_values
            LIMIT 1
            """
            analysis_results = run_query(analysis_query, database=settings.NEO4J_DATABASE)
            
            # Default values if no relationships exist
            analysis_data = {
                "incoming_links": 0,
                "outgoing_links": 0,
                "sum_incoming_values": 0,
                "sum_outgoing_values": 0
            }
            
            if analysis_results:
                record = analysis_results[0]
                analysis_data = {
                    "incoming_links": record["incoming_links"],
                    "outgoing_links": record["outgoing_links"],
                    "sum_incoming_values": record["sum_incoming_values"],
                    "sum_outgoing_values": record["sum_outgoing_values"]
                }

            # Combine with node type
            response_data.append({
                "node_type": node_type,
                "properties_analyse": analysis_data
            })

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    


@api_view(['POST'])
def node_analysis(request):
    node_id = request.data.get('id')
    
    if node_id is None:
        return Response(
            {"error": "Node ID is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        node_id = int(node_id)  # Ensure ID is an integer
    except (ValueError, TypeError):
        return Response(
            {"error": "Node ID must be a valid integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Query to compute analytical properties for the node
        analysis_query = """
       MATCH (n)
WHERE id(n) = $id
OPTIONAL MATCH (n)<-[r_in]-()
OPTIONAL MATCH (n)-[r_out]->()
WITH COUNT(r_in) AS incoming_links,
     COUNT(r_out) AS outgoing_links,
     COLLECT(r_in) AS incoming_rels,
     COLLECT(r_out) AS outgoing_rels
WITH incoming_links,
     outgoing_links,
     [rel IN incoming_rels | [k IN keys(rel) WHERE k <> 'identity' | rel[k]]] AS in_values,
     [rel IN outgoing_rels | [k IN keys(rel) WHERE k <> 'identity' | rel[k]]] AS out_values
WITH incoming_links,
     outgoing_links,
     REDUCE(s = 0, vals IN in_values | s + REDUCE(inner_s = 0, v IN vals | inner_s + (CASE WHEN v IS NOT NULL AND toFloat(v) = toInteger(v) THEN COALESCE(toInteger(v), 0) ELSE 0 END))) AS sum_incoming_values,
     REDUCE(s = 0, vals IN out_values | s + REDUCE(inner_s = 0, v IN vals | inner_s + (CASE WHEN v IS NOT NULL AND toFloat(v) = toInteger(v) THEN COALESCE(toInteger(v), 0) ELSE 0 END))) AS sum_outgoing_values
RETURN incoming_links,
       outgoing_links,
       sum_incoming_values,
       sum_outgoing_values
        """
        params = {"id": node_id}
        analysis_results = run_query(analysis_query, params, database=settings.NEO4J_DATABASE)

        if not analysis_results:
            return Response(
                {"error": f"No node found with id {node_id}."},
                status=status.HTTP_404_NOT_FOUND
            )

        record = analysis_results[0]
        response_data = {
            "id": node_id,
            "properties_analyse": {
                "incoming_links": record["incoming_links"],
                "outgoing_links": record["outgoing_links"],
                "sum_incoming_values": record["sum_incoming_values"],
                "sum_outgoing_values": record["sum_outgoing_values"]
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(e)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )