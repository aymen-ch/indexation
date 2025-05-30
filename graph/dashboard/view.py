from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from django.conf import settings
from django.core.cache import cache
from neo4j import GraphDatabase
from graph.Utility_QueryExecutors  import driver
@api_view(['GET'])
def get_database_stats_view(request):
    """
    API endpoint to get counts of nodes, relationships, labels, relationship types, and property keys.
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query for counts
            queries = {
                "nodes": "MATCH (n) RETURN COUNT(n) AS count",
                "relationships": "MATCH ()-[r]->() RETURN COUNT(r) AS count",
                "labels": "CALL db.labels() YIELD label RETURN COUNT(label) AS count",
                "relationship_types": "CALL db.relationshipTypes() YIELD relationshipType RETURN COUNT(relationshipType) AS count",
                "property_keys": "CALL db.propertyKeys() YIELD propertyKey RETURN COUNT(propertyKey) AS count",
            }

            stats = {}
            for key, query in queries.items():
                result = session.run(query)
                stats[key] = result.single()["count"]

            return Response({
                "nodes": stats["nodes"],
                "relationships": stats["relationships"],
                "labels": stats["labels"],
                "relationship_types": stats["relationship_types"],
                "property_keys": stats["property_keys"],
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
def get_relationship_type_counts_view(request):
    """
    API endpoint to get the count of relationships for each relationship type.
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get count of relationships per type
            query = """
            MATCH ()-[r]->()
            RETURN type(r) AS relationship_type, COUNT(*) AS count
            ORDER BY relationship_type
            """
            
            result = session.run(query)
            relationship_type_counts = {record["relationship_type"]: record["count"] for record in result}

            return Response({
                "relationship_type_counts": relationship_type_counts
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_node_type_counts_view(request):
    """
    API endpoint to get the count of nodes for each node type (label).
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get count of nodes per label
            query = """
            MATCH (n)
            WITH labels(n) AS node_labels
            UNWIND node_labels AS label
            RETURN label, COUNT(*) AS count
            ORDER BY label
            """
            
            result = session.run(query)
            node_type_counts = {record["label"]: record["count"] for record in result}

            return Response({
                "node_type_counts": node_type_counts
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
def get_affaire_counts_by_wilaya_view(request):
    """
    API endpoint to get the count of Affaire nodes grouped by Wilaya.
    Follows path: (Affaire)-[:Traiter]-(Unite)-[:Situer]-(Commune)-[:Appartient]-(Daira)-[:Appartient]-(Wilaya).
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to count Affaire nodes per Wilaya
            query = """
            MATCH (a:Affaire)-[:Traiter]-(u:Unite)-[:situer]-(c:Commune)-[:appartient]-(d:Daira)-[:appartient]-(w:Wilaya)
            RETURN w.nom_arabe AS wilaya, COUNT(DISTINCT a) AS affaire_count
            ORDER BY wilaya
            """
            
            result = session.run(query)
            affaire_counts = {record["wilaya"]: record["affaire_count"] for record in result}

            return Response({
                "affaire_counts_by_wilaya": affaire_counts
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
def get_affaire_counts_by_day_view(request):
    """
    API endpoint to get the count of Affaire nodes grouped by date.
    Expects Affaire nodes to have a 'date' attribute in 'DD-MM-YYYY' format.
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to count Affaire nodes per date
            query = """
            MATCH (a:Affaire)
            WHERE a.date IS NOT NULL
            RETURN a.date AS date, COUNT(a) AS affaire_count
            ORDER BY a.date
            """
            
            result = session.run(query)
            affaire_counts = {record["date"]: record["affaire_count"] for record in result}

            return Response({
                "affaire_counts_by_day": affaire_counts
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
def get_top_unite_by_affaire_count_view(request):
    """
    API endpoint to get the top 10 Unite nodes with the highest count of Affaire nodes connected via Traiter.
    GET request, no parameters required.
    """
    try:
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Query to get top 10 Unite nodes by Affaire count
            query = """
            MATCH (u:Unite)-[:Traiter]-(a:Affaire)
            RETURN u.nom_arabe AS unite, COUNT(DISTINCT a) AS affaire_count
            ORDER BY affaire_count DESC
            LIMIT 10
            """
            
            result = session.run(query)
            top_unites = [
                {"unite": record["unite"], "affaire_count": record["affaire_count"]}
                for record in result
            ]

            return Response({
                "top_unite_by_affaire_count": top_unites
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)