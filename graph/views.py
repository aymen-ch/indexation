from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from datetime import datetime
import uuid
from .utility import fetch_node_types, fetch_node_properties,driver


def run_query(query, params=None):
    with driver.session() as session:
        results = session.run(query, params or {})
        return [record.data() for record in results]

@api_view(['POST'])
def getdata(request):
    # Extract the identity from the request data
    identity = request.data.get('identity')
    print(identity)
    if not identity:
        return Response(
            {"error": "Identity is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        # Define the Cypher query
        query = """
        MATCH (n {identity: $identity}) RETURN n 
        """
        print("nn")

        # Execute the query using the Neo4j driver
        with driver.session() as session:
            results = session.run(query, {"identity": identity})
            records = list(results)  # Convert the result to a list of records

            if not records:
                return Response(
                    {"error": "Node not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Extract the first result (node data)
            node_data = records[0]["n"]
            return Response(node_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
def recherche(request):
    search_value = request.data.get('query')
    print(f"Search query: {search_value}")
    
    if not search_value:
        return Response(
            {"error": "Search value is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with driver.session() as session:
            # Step 1: Handle node full-text indexes
            index_count_query = """
            SHOW FULLTEXT INDEXES
            YIELD name, type, entityType
            WHERE entityType = 'NODE'
            RETURN count(name) AS index_count, collect(name) AS index_names
            """
            index_result = session.run(index_count_query)
            index_record = index_result.single()
            node_index_count = index_record["index_count"] if index_record else 0
            node_index_names = index_record["index_names"] if index_record else []

            label_count_query = """
            MATCH (n)
            UNWIND labels(n) AS label
            WITH DISTINCT label
            RETURN count(label) AS label_count, collect(label) AS labels
            """
            label_result = session.run(label_count_query)
            label_record = label_result.single()
            label_count = label_record["label_count"]
            all_labels = label_record["labels"]

            if node_index_count < label_count:
                existing_index_labels = [name.replace("index_", "") for name in node_index_names]
                missing_labels = [label for label in all_labels if label not in existing_index_labels]

                for label in missing_labels:
                    properties_query = """
                    MATCH (n:%s)
                    UNWIND keys(n) AS property
                    RETURN collect(DISTINCT property) AS properties
                    """ % label
                    prop_result = session.run(properties_query)
                    prop_record = prop_result.single()
                    properties = prop_record["properties"] if prop_record else []

                    if properties:
                        property_list = ", ".join([f"n.`{prop}`" for prop in properties])
                        create_index_query = f"""
                        CREATE FULLTEXT INDEX index_{label} IF NOT EXISTS
                        FOR (n:{label}) ON EACH [{property_list}]
                        OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'standard-no-stop-words' }} }}
                        """
                        session.run(create_index_query)
                        print(f"Created node index for {label}: {create_index_query}")

                updated_node_result = session.run(index_count_query)
                updated_node_record = updated_node_result.single()
                node_index_names = updated_node_record["index_names"]

            # Step 2: Handle relationship full-text indexes
            rel_index_count_query = """
            SHOW FULLTEXT INDEXES
            YIELD name, type, entityType
            WHERE entityType = 'RELATIONSHIP'
            RETURN count(name) AS rel_index_count, collect(name) AS rel_index_names
            """
            rel_index_result = session.run(rel_index_count_query)
            rel_index_record = rel_index_result.single()
            rel_index_count = rel_index_record["rel_index_count"] if rel_index_record else 0
            rel_index_names = rel_index_record["rel_index_names"] if rel_index_record else []

            rel_type_count_query = """
            MATCH ()-[r]->()
            WITH DISTINCT type(r) AS rel_type
            RETURN count(rel_type) AS rel_type_count, collect(rel_type) AS rel_types
            """
            rel_type_result = session.run(rel_type_count_query)
            rel_type_record = rel_type_result.single()
            rel_type_count = rel_type_record["rel_type_count"]
            all_rel_types = rel_type_record["rel_types"]

            if rel_index_count < rel_type_count:
                existing_rel_indexes = [name for name in rel_index_names]
                for rel_type in all_rel_types:
                    index_name = f"index_{rel_type.lower()}_rel"
                    if index_name not in existing_rel_indexes:
                        rel_properties_query = """
                        MATCH ()-[r:%s]->()
                        UNWIND keys(r) AS property
                        RETURN collect(DISTINCT property) AS properties
                        """ % rel_type
                        rel_prop_result = session.run(rel_properties_query)
                        rel_prop_record = rel_prop_result.single()
                        rel_properties = rel_prop_record["properties"] if rel_prop_record else []

                        if rel_properties:
                            rel_property_list = ", ".join([f"r.`{prop}`" for prop in rel_properties])
                            create_rel_index_query = f"""
                            CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
                            FOR ()-[r:{rel_type}]-() ON EACH [{rel_property_list}]
                            OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'standard-no-stop-words' }} }}
                            """
                            session.run(create_rel_index_query)
                            print(f"Created relationship index for {rel_type}: {create_rel_index_query}")

                updated_rel_result = session.run(rel_index_count_query)
                updated_rel_record = updated_rel_result.single()
                rel_index_names = updated_rel_record["rel_index_names"]

            # Step 3: Check if there are any indexes to search
            if not node_index_names and not rel_index_names:
                return Response(
                    {"error": "No full-text indexes available for search."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Step 4: Search nodes and relationships with full-text capabilities
            search_query = ""
            if node_index_names:
                search_query += """
                UNWIND $node_index_names AS node_index_name
                CALL db.index.fulltext.queryNodes(node_index_name, $search_value) YIELD node, score
                RETURN labels(node)[0] AS type, node.identity AS identity, properties(node) AS properties, score
                """
            if rel_index_names:
                if node_index_names:
                    search_query += " UNION "
                search_query += """
                UNWIND $rel_index_names AS rel_index_name
                CALL db.index.fulltext.queryRelationships(rel_index_name, $search_value) YIELD relationship, score
                RETURN type(relationship) AS type, relationship.identity AS identity, properties(relationship) AS properties, score
                """

            if not search_query:
                return Response(
                    {"error": "No search query generated."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Enhance search_value for broader matching if needed
            # Example: Add wildcard if not already a Lucene query
            if not any(c in search_value for c in ['*', '?', '"', '+', '-', 'AND', 'OR', 'NOT']):
                search_value = f"{search_value}*"  # Add wildcard for partial matching

            results = session.run(search_query, {
                "search_value": search_value,
                "node_index_names": node_index_names,
                "rel_index_names": rel_index_names
            })
            records = list(results)

            # Step 5: Process results into a response
            response_data = [
                {
                    "identity": record["identity"],
                    "properties": record["properties"],
                    "score": record["score"],
                    "type": record["type"]
                }
                for record in records
            ]
            
            return Response(response_data, status=status.HTTP_200_OK)
            
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
                    # First segment with start_id
                    pattern = f"({n1_var}:{node1} {{identity: $start_id}})-[{rel_var}:{rel}]-({n2_var}:{node2})"
                else:
                    # Subsequent segments
                    pattern = f"-[{rel_var}:{rel}]-({n2_var}:{node2})"
                    if i == len(path) - 3:
                        pattern = f"-[{rel_var}:{rel}]-({n2_var}:{node2} {{identity: $end_id}})"
                
                match_clauses.append(pattern)

            # Join the clauses into a single continuous path
            query = (
                f"MATCH {''.join(match_clauses)}\n"
                "WITH collect(r) as relations\n"
                f"RETURN {{type: '{middle_relation}', count: size(relations), detail: [rel in relations | {{identity: rel.identity, properties: properties(rel)}}]}} as relation_data"
            )
            print(query)
            
            with driver.session() as session:
                results = session.run(query, {
                    "start_id": start_id,
                    "end_id": end_id
                })
                records = list(results)

                if not records:
                    return Response(
                        {"error": "Virtual relation not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                relation_data = records[0]["relation_data"]
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
                
            query = """
                MATCH ()-[n {identity: $identity}]-()
                RETURN {
                    identity: n.identity,
                    type: type(n),
                    properties: properties(n)
                } as relation_data
            """

            with driver.session() as session:
                results = session.run(query, {"identity": identity})
                records = list(results)

                if not records:
                    return Response(
                        {"error": "Node not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                relation_data = records[0]["relation_data"]
                return Response(relation_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Execute query using Neo4j driver
@api_view(['GET'])
def get_node_types(request):
    try:
        node_types = fetch_node_types()
        return Response({"node_types": node_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_node_properties(request):
    """
    Endpoint to fetch properties and their types of a specific node type.
    """
    node_type = request.GET.get('node_type', '')
    if not node_type:
        return Response(
            {"error": "Missing required parameter 'node_type'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        properties = fetch_node_properties(node_type)
        return Response(
            {"node_type": node_type, "properties": properties},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['POST'])
def search_nodes(request):
    try:
        # Get data from request body
        node_type = request.data.get('node_type')
        search_payload = request.data.get('properties', {})
        
        if not node_type or not isinstance(search_payload, dict):
            return Response(
                {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Expecting search_payload to contain 'values' and 'operations'
        values = search_payload.get('values', {})
        operations = search_payload.get('operations', {})
        print(operations)
        if not isinstance(values, dict) or not isinstance(operations, dict):
            return Response(
                {"error": "'properties' must contain 'values' and 'operations' dictionaries."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Construct the Cypher query dynamically based on provided properties and operations
        match_conditions = []
        parameters = {}
        
        for key, value in values.items():
            if value is None or value == '':
                continue  # Skip empty or null values

            operation = operations.get(key, '=')  # Default to '=' if no operation specified
            
            # Handle different operations
            if operation == '=':
                match_conditions.append(f"n.{key} = ${key}")
                parameters[key] = value
            elif operation == '!=':
                match_conditions.append(f"n.{key} <> ${key}")
                parameters[key] = value
            elif operation in ['>', '<', '>=', '<=']:
                match_conditions.append(f"n.{key} {operation} ${key}")
                parameters[key] = value
            elif operation == 'contains':
                match_conditions.append(f"n.{key} CONTAINS ${key}")
                parameters[key] = str(value)  # Ensure value is a string for CONTAINS
            elif operation == 'startswith':
                match_conditions.append(f"n.{key} STARTS WITH ${key}")
                parameters[key] = str(value)  # Ensure value is a string
            elif operation == 'endswith':
                match_conditions.append(f"n.{key} ENDS WITH ${key}")
                parameters[key] = str(value)  # Ensure value is a string
            else:
                return Response(
                    {"error": f"Unsupported operation '{operation}' for property '{key}'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if not match_conditions:
            query = f"MATCH (n:{node_type}) RETURN n"
        else:
            query = f"""
            MATCH (n:{node_type})
            WHERE {' AND '.join(match_conditions)}
            RETURN n
            """

        # Debugging logs
        print("Generated Cypher Query:", query)
        print("Parameters:", parameters)

        with driver.session() as session:
            result = session.run(query, parameters)
            nodes = [record['n'] for record in result]  # Extract nodes from the result

        formatted_nodes = []
        for node in nodes:
            # Exclude 'elementId' and 'identity' properties
            filtered_node = {key: value for key, value in dict(node).items() if key not in ['elementId']}
            formatted_nodes.append(filtered_node)

        return Response(
            {"node_type": node_type, "results": formatted_nodes},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def getPersonneCrimes(request):
    if request.method == 'POST':
        try:
            # Extract node IDs from the request body
            data = request.data
            node_ids = data.get('nodeIds', [])  # Expecting a list of node IDs
            print(node_ids)
            if not node_ids:
                return JsonResponse({'error': 'No node IDs provided'}, status=400)

            # Query to count crimes for each "Personne" node
            query = """
            MATCH (p:Personne)-[:Impliquer]-(c:Affaire)
            WHERE p.identity IN $nodeIds
            RETURN p.identity AS nodeId, COUNT(c) AS crimeCount
            """
            params = {'nodeIds': node_ids}

            # Execute the query
            results = run_query(query, params)

            # Format the results into a dictionary {nodeId: crimeCount}
            crime_counts = {result['nodeId']: result['crimeCount'] for result in results}

            # Include nodes with 0 crimes (if needed)
            for node_id in node_ids:
                if node_id not in crime_counts:
                    crime_counts[node_id] = 0

            return JsonResponse(crime_counts, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


@api_view(['POST'])
def get_possible_relations(request):
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    properties = request.data.get('properties', {})

    if not node_type or not isinstance(properties, dict):
        return Response(
            {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Construct the Cypher query dynamically based on provided properties
    match_conditions = []
    parameters = {}
    for key, value in properties.items():
        # Use backticks around property names to handle spaces or special characters
        match_conditions.append(f"n.`{key}` = $`{key}`")
        parameters[key] = value

    # Base Cypher query to fetch distinct relationship types
    query = f"""
    MATCH (n:{node_type})-[r]-()
    WHERE {' AND '.join(match_conditions)}
    RETURN DISTINCT type(r) AS relationship_type
    """

    # Debug: Print the final query and parameters
    query_with_values = query
    for key, value in parameters.items():
        value_str = f"'{value}'" if isinstance(value, str) else str(value)
        query_with_values = query_with_values.replace(f"${key}", value_str)
    print("Final Cypher Query with Substituted Parameters:")
    print(query_with_values)

    try:
        # Execute the query using the Neo4j driver
        with driver.session() as session:
            result = session.run(query, parameters)
            relationship_types = [record["relationship_type"] for record in result]

            return Response({"relations": relationship_types}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from neo4j import GraphDatabase

# Assuming you have your Neo4j driver initialized somewhere
# driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from neo4j import GraphDatabase

# Assuming driver is initialized
# driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))



@api_view(['POST'])
def personne_criminal_network(request):
    # Get properties from request body
    properties = request.data.get('properties', {})
    
    if not isinstance(properties, dict) or 'identity' not in properties:
        return Response(
            {"error": "Missing or invalid 'properties'. Must include 'identity'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Updated Cypher query using apoc.path.expandConfig
    query = """
    MATCH (context:Personne {identity: $identity})
    CALL apoc.path.expandConfig(context, {
      relationshipFilter: "Proprietaire|Appel_telephone|Impliquer",
      minLevel: 1,
      maxLevel: 5
    })
    YIELD path
    WHERE last(nodes(path)):Affaire
    WITH collect(nodes(path)) AS all_node_lists, collect(relationships(path)) AS all_rel_lists
    WITH apoc.coll.flatten(all_node_lists) AS all_nodes, apoc.coll.flatten(all_rel_lists) AS all_rels
    WITH apoc.coll.toSet(all_nodes) AS unique_nodes, apoc.coll.toSet(all_rels) AS unique_rels
    RETURN {
      nodes: [n IN unique_nodes | {id: ID(n), labels: labels(n), properties: properties(n)}],
      edges: [r IN unique_rels | {id: ID(r), type: type(r), startNode: ID(startNode(r)), endNode: ID(endNode(r)), properties: properties(r)}]
    } AS result
    """
    
    parameters = {'identity': properties['identity']}
    
    try:
        with driver.session() as session:
            result = session.run(query, parameters)
            record = result.single()  # Single row with all unique nodes and edges
            
            if record:
                network_data = record["result"]
                return Response(network_data, status=status.HTTP_200_OK)
            else:
                return Response({"nodes": [], "edges": []}, status=status.HTTP_200_OK)
                
    except Exception as e:
        return Response(
            {"error": f"Error executing query: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    



@api_view(['POST'])
def personne_criminal_network_old(request):
    # Get properties from request body
    properties = request.data.get('properties', {})
    
    if not isinstance(properties, dict) or 'identity' not in properties:
        return Response(
            {"error": "Missing or invalid 'properties'. Must include 'identity'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Generalized Cypher query to collect unique nodes and edges from all paths
    query = """
    MATCH (context:Personne {identity: $identity})
    MATCH path = (context)-[rels:Proprietaire|Appel_telephone|Impliquer*1..5]-(affaire:Affaire)
    
    // Extract all nodes and relationships from all paths
    WITH nodes(path) AS path_nodes, relationships(path) AS path_rels
    WITH collect(path_nodes) AS all_nodes_collection, collect(path_rels) AS all_rels_collection
    
    // Flatten and deduplicate nodes
    WITH 
        [node IN apoc.coll.flatten(all_nodes_collection) | {
            id: ID(node),
            labels: labels(node),
            properties: properties(node)
        }] AS all_nodes,
        [rel IN apoc.coll.flatten(all_rels_collection) | {
            id: ID(rel),
            type: type(rel),
            startNode: ID(startNode(rel)),
            endNode: ID(endNode(rel)),
            properties: properties(rel)
        }] AS all_edges
    
    // Remove duplicates
    WITH 
        apoc.coll.toSet(all_nodes) AS unique_nodes,
        apoc.coll.toSet(all_edges) AS unique_edges
    
    RETURN {nodes: unique_nodes, edges: unique_edges} AS result
    """
    
    parameters = {'identity': properties['identity']}
    
    try:
        with driver.session() as session:
            result = session.run(query, parameters)
            record = result.single()  # Single row with all unique nodes and edges
            
            if record:
                network_data = record["result"]
                return Response(network_data, status=status.HTTP_200_OK)
            else:
                return Response({"nodes": [], "edges": []}, status=status.HTTP_200_OK)
                
    except Exception as e:
        return Response(
            {"error": f"Error executing query: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )   
@api_view(['POST'])
def get_node_relationships(request):
    # Get data from the request body
    print(request.data)
    node_type = request.data.get('node_type')
    properties = request.data.get('properties', {})
    relation_type = request.data.get('relation_type')  # New: Get the specific relation type

    if not node_type or not isinstance(properties, dict):
        return Response(
            {"error": "Missing or invalid 'node_type' or 'properties'. 'properties' must be a dictionary."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Construct the Cypher query dynamically based on provided properties
    match_conditions = []
    parameters = {}
    for key, value in properties.items():
        # Use backticks around property names to handle spaces or special characters
        match_conditions.append(f"n.`{key}` = $`{key}`")
        parameters[key] = value

    # Base Cypher query with relationships
    query = f"""
    MATCH (n:{node_type})-[r]-(related)
    WHERE {' AND '.join(match_conditions)}
    """

    # Add condition to filter by specific relationship type if provided
    if relation_type:
        query += f" AND type(r) = $relation_type"
        parameters['relation_type'] = relation_type

    # Complete the query
    query += """
    RETURN n, related, r, type(r) AS relationship, labels(related) AS related_labels
    LIMIT 100
    """

    # Debug: Print the final query and parameters
    query_with_values = query
    for key, value in parameters.items():
        value_str = f"'{value}'" if isinstance(value, str) else str(value)
        query_with_values = query_with_values.replace(f"${key}", value_str)
    print("Final Cypher Query with Substituted Parameters:")
    print(query_with_values)

    try:
        with driver.session() as session:
            result = session.run(query, parameters)  # Execute the query with parameters
            relationships = []
            for record in result:
                node = record["n"]
                related_node = record["related"]
                relationship = record["r"]
                relationship_type = record["relationship"]
                related_labels = record["related_labels"]  # This will contain the list of labels (node types) for the related node

                # Remove 'elementId' and 'identity' from both the main node and the related node
                node_dict = {key: value for key, value in dict(node).items() if key not in ['elementId', 'identity']}
                related_node_dict = {key: value for key, value in dict(related_node).items() if key not in ['elementId']}
                relationship_dict = {key: value for key, value in dict(relationship).items() if key not in ['elementId']}

                relationships.append({
                    "related": {
                        "node_type": list(related_labels)[0],
                        "properties": related_node_dict  # Add the related node without unwanted properties
                    },
                    "relationship": {
                        "identity": relationship_dict.get("identity"),
                        "type": relationship_type,  # Relationship type
                        "properties": relationship_dict  # Relationship properties
                    }
                })

            return Response(relationships, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
