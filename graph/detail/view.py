

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
from graph.Utility_QueryExecutors  import run_query
@api_view(['POST'])
def getdata(request):
    """
    Retrieves a node from the Neo4j database based on its identity.

    Input:
        - identity (str): The ID of the node to retrieve.

    Output:
        - node_data (dict): The retrieved node data.

    Description:
        Handles a POST request to retrieve a node from the Neo4j database based on its identity.
    """
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
    """
    Retrieves relationship data between nodes in the Neo4j database.

    Input:
        - identity (str): The ID of the starting node.
        - path (list): A list of node labels and relationship types.

    Output:
        - relationship_data (dict): The retrieved relationship data.

    Description:
        Handles a POST request to retrieve relationship data between nodes in the Neo4j database.
    """
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
    
   
@api_view(['POST'])
def node_type_attribute_insert(request):
    """
    Inserts attributes for a node type in the Neo4j database.

    Input:
        - node_type (str): The type of node to insert attributes for.
        - attribute_name (str): The name of the attribute to insert.
        - attribute_value (str): The value of the attribute to insert.

    Output:
        - result (dict): A dictionary containing the result of the insertion.

    Description:
        Handles a POST request to insert attributes for a node type in the Neo4j database.
    """
    try:
        # Step 1: Extract node type from request data
        node_type = request.data.get('node_type')
        if not node_type:
            return Response(
                {"error": "Node type is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Verify if the node type exists in the database
        label_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH DISTINCT label
        RETURN label
        """
        label_results = run_query(label_query, database=settings.NEO4J_DATABASE)
        node_types = [record["label"] for record in label_results]

        if node_type not in node_types:
            return Response(
                {"error": f"Node type '{node_type}' not found in the database."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Step 3: Compute degree_in and degree_out for nodes of the specified type
        analysis_query = f"""
        MATCH (n:{node_type})
        OPTIONAL MATCH (n)<-[r_in]-()
        OPTIONAL MATCH (n)-[r_out]->()
        WITH n, 
             COUNT(r_in) AS degree_in,
             COUNT(r_out) AS degree_out
        SET n.degree_in = degree_in,
            n.degree_out = degree_out
        RETURN COUNT(n) AS updated_nodes
        """
        analysis_results = run_query(analysis_query, database=settings.NEO4J_DATABASE)

        # Step 4: Check the number of updated nodes
        updated_nodes = analysis_results[0]["updated_nodes"] if analysis_results else 0

        # Step 5: Return success message
        return Response(
            {
                "message": f"Successfully updated {updated_nodes} nodes of type '{node_type}' with degree_in and degree_out attributes.",
                "node_type": node_type,
                "updated_nodes": updated_nodes
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def get_outgoing_relationship_attributes(request):
    """
    Retrieves outgoing relationship attributes for a node in the Neo4j database.

    Input:
        - node_id (int): The ID of the node to retrieve outgoing relationship attributes for.

    Output:
        - attributes (dict): A dictionary containing the outgoing relationship attributes.

    Description:
        Handles a POST request to retrieve outgoing relationship attributes for a node in the Neo4j database.
    """
    try:
        # Step 1: Extract node type from request data
        node_type = request.data.get('node_type')
        if not node_type:
            return Response(
                {"error": "Node type is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Verify if the node type exists
        label_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH DISTINCT label
        RETURN label
        """
        label_results = run_query(label_query, database=settings.NEO4J_DATABASE)
        node_types = [record["label"] for record in label_results]

        if node_type not in node_types:
            return Response(
                {"error": f"Node type '{node_type}' not found in the database."},
                status=status.HTTP_404_NOT_FOUND
            )


        # Step 3: Fetch distinct properties of outgoing relationships
        attributes_query = f"""
        MATCH (n:{node_type})-[r]->()
        UNWIND keys(r) AS key
        WITH DISTINCT key
        WHERE key <> 'identity'
        RETURN key
        """
        attributes_results = run_query(attributes_query, database=settings.NEO4J_DATABASE)
        attributes = [record["key"] for record in attributes_results]

        # Step 4: Return the attributes
        return Response(
            {
                "node_type": node_type,
                "attributes": attributes
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def get_incoming_relationship_attributes(request):
    """
    Retrieves incoming relationship attributes for a node in the Neo4j database.

    Input:
        - node_id (int): The ID of the node to retrieve incoming relationship attributes for.

    Output:
        - attributes (dict): A dictionary containing the incoming relationship attributes.

    Description:
        Handles a POST request to retrieve incoming relationship attributes for a node in the Neo4j database.
    """
    try:
        # Step 1: Extract node type from request data
        node_type = request.data.get('node_type')
        if not node_type:
            return Response(
                {"error": "Node type is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Verify if the node type exists
        label_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH DISTINCT label
        RETURN label
        """
        label_results = run_query(label_query, database=settings.NEO4J_DATABASE)
        node_types = [record["label"] for record in label_results]

        if node_type not in node_types:
            return Response(
                {"error": f"Node type '{node_type}' not found in the database."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Step 3: Fetch distinct properties of incoming relationships
        attributes_query = f"""
        MATCH (n:{node_type})<-[r]-()
        UNWIND keys(r) AS key
        WITH DISTINCT key
        WHERE key <> 'identity'
        RETURN key
        """
        attributes_results = run_query(attributes_query, database=settings.NEO4J_DATABASE)
        attributes = [record["key"] for record in attributes_results]
        print(attributes)
        # Step 4: Return the attributes
        return Response(
            {
                "node_type": node_type,
                "attributes": attributes
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
   
@api_view(['POST'])
def insert_node_attribute(request):
    """
    Inserts an attribute for a node in the Neo4j database.

    Input:
        - node_id (int): The ID of the node to insert an attribute for.
        - attribute_name (str): The name of the attribute to insert.
        - attribute_value (str): The value of the attribute to insert.

    Output:
        - result (dict): A dictionary containing the result of the insertion.

    Description:
        Handles a POST request to insert an attribute for a node in the Neo4j database.
    """
    try:
        # Step 1: Extract input from request data
        node_type = request.data.get('node_type')
        calc_type = request.data.get('calc_type')  # 'degree_in', 'sum_degree_in', 'degree_out', 'sum_degree_out'
        attribute_name = request.data.get('attribute_name')  # Custom name for the new attribute
        rel_attribute = request.data.get('rel_attribute')  # Attribute to aggregate (for sum_degree_in/out)
        aggregation = request.data.get('aggregation')  # 'sum' or 'multiplication' (for sum_degree_in/out)

        # Validate inputs
        if not node_type or not calc_type or not attribute_name:
            return Response(
                {"error": "node_type, calc_type, and attribute_name are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if calc_type not in ['degree_in', 'sum_degree_in', 'degree_out', 'sum_degree_out']:
            return Response(
                {"error": "calc_type must be 'degree_in', 'sum_degree_in', 'degree_out', or 'sum_degree_out'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if calc_type in ['sum_degree_in', 'sum_degree_out'] and (not rel_attribute or not aggregation):
            return Response(
                {"error": "rel_attribute and aggregation are required for sum_degree_in or sum_degree_out."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if calc_type in ['sum_degree_in', 'sum_degree_out'] and aggregation not in ['sum', 'multiplication']:
            return Response(
                {"error": "aggregation must be 'sum' or 'multiplication'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        attribute_name = f"_{attribute_name}"
        # Step 2: Verify if the node type exists
        label_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH DISTINCT label
        RETURN label
        """
        label_results = run_query(label_query, database=settings.NEO4J_DATABASE)
        node_types = [record["label"] for record in label_results]

        if node_type not in node_types:
            return Response(
                {"error": f"Node type '{node_type}' not found in the database."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Step 3: Build and execute the Cypher query
        if calc_type == 'degree_in':
            analysis_query = f"""
            MATCH (n:{node_type})
            OPTIONAL MATCH (n)<-[r_in]-()
            WITH n, COUNT(r_in) AS degree_in
            SET n.{attribute_name} = degree_in
            RETURN COUNT(n) AS updated_nodes
            """
        elif calc_type == 'degree_out':
            analysis_query = f"""
            MATCH (n:{node_type})
            OPTIONAL MATCH (n)-[r_out]->()
            WITH n, COUNT(r_out) AS degree_out
            SET n.{attribute_name} = degree_out
            RETURN COUNT(n) AS updated_nodes
            """
        elif calc_type == 'sum_degree_in':
            default_value = "0" if aggregation == "sum" else "1"
            reduce_op = "s + v" if aggregation == "sum" else "p * v"
            analysis_query = f"""
            MATCH (n:{node_type})
            OPTIONAL MATCH (n)<-[r_in]-()
            WITH n, COLLECT(COALESCE(toFloat(r_in.{rel_attribute}), {default_value})) AS values
            SET n.{attribute_name} = REDUCE(s = {default_value}, v IN values | {reduce_op})
            RETURN COUNT(n) AS updated_nodes
            """
        else:  # sum_degree_out
            default_value = "0" if aggregation == "sum" else "1"
            reduce_op = "s + v" if aggregation == "sum" else "p * v"
            analysis_query = f"""
            MATCH (n:{node_type})
            OPTIONAL MATCH (n)-[r_out]->()
            WITH n, COLLECT(COALESCE(toFloat(r_out.{rel_attribute}), {default_value})) AS values
            SET n.{attribute_name} = REDUCE(s = {default_value}, v IN values | {reduce_op})
            RETURN COUNT(n) AS updated_nodes
            """

        analysis_results = run_query(analysis_query, database=settings.NEO4J_DATABASE)

        # Step 4: Check the number of updated nodes
        updated_nodes = analysis_results[0]["updated_nodes"] if analysis_results else 0

        # Step 5: Return success message
        return Response(
            {
                "message": f"Mise à jour réussie de {updated_nodes} nœuds de type '{node_type}' avec l’attribut '{attribute_name}'.",
                "node_type": node_type,
                "attribute_name": attribute_name,
                "updated_nodes": updated_nodes
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

@api_view(['POST'])
def get_relationship_properties(request):
    """
    Retrieves properties for a relationship in the Neo4j database.

    Input:
        - relationship_type (str): The type of relationship to retrieve properties for.

    Output:
        - properties (dict): A dictionary containing the properties of the relationship.

    Description:
        Handles a POST request to retrieve properties for a relationship in the Neo4j database.
    """
    try:
        relationship_type = request.data.get('relationship_type')
        if not relationship_type:
            return Response(
                {"error": "relationship_type is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch property keys for relationships of the given type
        query = """
        MATCH ()-[r]->()
        WHERE type(r) = $relationship_type
        RETURN DISTINCT keys(r) AS property_keys
        LIMIT 1
        """
        params = {"relationship_type": relationship_type}
        results = run_query(query, params, database=settings.NEO4J_DATABASE)

        if not results:
            return Response(
                {"error": f"No relationships found with type '{relationship_type}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Extract property keys
        property_keys = results[0]["property_keys"]

        return Response(
            {
                "relationship_type": relationship_type,
                "properties": property_keys
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(['POST'])
def get_node_properties(request):
    """
    Retrieves properties for a node in the Neo4j database.

    Input:
        - node_type (str): The type of node to retrieve properties for.

    Output:
        - properties (dict): A dictionary containing the properties of the node.

    Description:
        Handles a POST request to retrieve properties for a node in the Neo4j database.
    """
    try:
        node_type = request.data.get('node_type')
        print(node_type)

        if not node_type:
            return Response(
                {"error": "node_type is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch property keys for nodes of the given type
        query = """
        MATCH (n)
        WHERE $node_type IN labels(n)
        RETURN DISTINCT keys(n) AS property_keys
        LIMIT 1
        """
        params = {"node_type": node_type}
        results = run_query(query, params, database=settings.NEO4J_DATABASE)

        if not results:
            return Response(
                {"error": f"No nodes found with type '{node_type}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Extract property keys (assuming all nodes of the same type have the same schema)
        property_keys = results[0]["property_keys"]

        return Response(
            {
                "node_type": node_type,
                "properties": property_keys
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
      
@api_view(['POST'])
def node_analysis(request):
    """
    Performs an analysis of a node in the Neo4j database.

    Input:
        request: A Django request object containing the node ID in the request body.
        id: The ID of the node to analyze.

    Output:
        A JSON response containing the results of the analysis.

    Description:
        This function performs an analysis of a node in the Neo4j database, including calculating the number of incoming and outgoing relationships, and summing the values of the relationships.
    """
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