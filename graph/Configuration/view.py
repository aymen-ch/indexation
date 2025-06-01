import os
import json
import re
import uuid
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pathlib import Path

from graph.Utility_QueryExecutors import parse_to_graph_with_transformer
from graph.Utility_QueryExecutors import run_query,driver


# Base configuration directory
CONFIG_BASE_DIR = Path(settings.BASE_DIR) / 'configuration'

def get_db_config_path(database_name):
    """Get the configuration directory path for a specific database"""
    return CONFIG_BASE_DIR / database_name

def ensure_db_config_files(database_name):
    """Create configuration directory and default empty files for a database"""
    db_config_path = get_db_config_path(database_name)
    db_config_path.mkdir(parents=True, exist_ok=True)
    
    # Default configuration files
    config_files = {
        'config_style.json':{
  "defaultNodeSize": 90,
  "groupNodeSize": 70,
  "defaultNodeWidth": "200px",
  "defaultNodeHeight": "200px",
  "groupNodeWidth": "220px",
  "groupNodeHeight": "220px",
  "centerWrapperWidth": "160px",
  "centerWrapperHeight": "160px",
  "groupCenterWrapperWidth": "180px",
  "groupCenterWrapperHeight": "180px",
  "defaultImageWidth": "120px",
  "defaultImageHeight": "120px",
  "groupImageWidth": "100px",
  "groupImageHeight": "100px",
  "captionBottom": "-45px",
  "edgeColor": "red",
  "edgeWidth": 7,
  "captionSize": 5,
  "captionFontSize": "40px",
  "captionColor": "rgb(211, 70, 54)",
  "captionBackgroundColor": "#f1c40f",
  "captionPadding": "5px",
  "captionBorderRadius": "3px",
  "captionTextShadow": "1px 1px 2px #000",

  "nodeTypes": {
    "default": {
    "color": "#CCCCCC",
    "size": 90,
    "icon": "/icon/default.png",
    "labelKey": "identity"
  }
  }
},
        'actions.json': [],
        'aggregation.json': [],
        'questions.json': []
    }
    
    # Create default empty files if they don't exist
    for file_name, default_content in config_files.items():
        file_path = db_config_path / file_name
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_content, f, indent=2, ensure_ascii=False)
    # Crée le répertoire pour les visualisations
    visualisations_dir = db_config_path / 'visualisations'
    visualisations_dir.mkdir(exist_ok=True)


def sanitize_filename(name):
    """Nettoie le nom pour en faire un nom de fichier valide"""
    # Remplace les caractères non alphanumériques par des underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    # Limite la longueur pour éviter les problèmes
    return sanitized[:100]

@api_view(['POST'])
def save_visualization(request):
    """Enregistre une nouvelle visualisation dans le répertoire des visualisations"""
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        visualisations_dir = get_db_config_path(database_name) / 'visualisations'

        # Valide les champs requis
        required_fields = ['name', 'nodes', 'edges']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"error": f"Champ requis manquant : {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Récupère les données de la visualisation
        visualization_data = {
            "name": request.data['name'],
            "nodes": request.data['nodes'],
            "edges": request.data['edges']
        }

        # Valide que nodes et edges sont des listes
        if not isinstance(visualization_data['nodes'], list) or not isinstance(visualization_data['edges'], list):
            return Response(
                {"error": "Les champs 'nodes' et 'edges' doivent être des listes"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Génère un ID unique pour la visualisation
        visualization_id = str(uuid.uuid4())
        # Crée un nom de fichier sécurisé
        file_name = f"{sanitize_filename(visualization_data['name'])}_{visualization_id}.json"
        file_path = visualisations_dir / file_name

        # Sauvegarde la visualisation
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(visualization_data, file, indent=2, ensure_ascii=False)

        return Response(
            {
                "message": f"Visualisation '{visualization_data['name']}' enregistrée avec succès",
                "id": visualization_id,
                "name": visualization_data['name'],
                "file": str(file_path)
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"Erreur lors de l'enregistrement de la visualisation : {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def get_visualizations(request):
    """Récupère la liste des visualisations ou une visualisation spécifique par ID"""
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        visualisations_dir = get_db_config_path(database_name) / 'visualisations'

        visualization_id = request.query_params.get('id')
        visualizations = []

        if visualization_id:
            # Recherche une visualisation spécifique par ID
            for file_path in visualisations_dir.glob('*.json'):
                if visualization_id in file_path.stem:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        visualization_data = json.load(file)
                        return Response(visualization_data, status=status.HTTP_200_OK)
            return Response(
                {"error": f"Visualisation avec l'ID '{visualization_id}' non trouvée"},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            # Liste toutes les visualisations
            for file_path in visualisations_dir.glob('*.json'):
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    # Extrait l'ID du nom du fichier (après le dernier underscore)
                    file_id = file_path.stem.split('_')[-1]
                    visualizations.append({
                        "id": file_id,
                        "name": data.get('name', file_path.stem),
                        "file": str(file_path)
                    })
            return Response(visualizations, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Erreur lors de la récupération des visualisations : {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def add_action(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        actions_file = get_db_config_path(database_name) / 'actions.json'

        # Validate required fields
        required_fields = ['name', 'description', 'node_type', 'id_field', 'query']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"error": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        new_action = {
            "name": request.data['name'],
            "description": request.data['description'],
            "node_type": request.data['node_type'],
            "id_field": request.data['id_field'],
            "query": request.data['query']
        }

        # Get node_id if provided, otherwise fetch a random one
        node_id = request.data.get('node_id')
        if not node_id:
            try:
                random_id_query = f"MATCH (n:{new_action['node_type']}) RETURN id(n) AS id LIMIT 1"
                result = run_query(random_id_query)  # Assuming run_query is defined elsewhere
                if not result:
                    return Response(
                        {"error": f"No node found for type '{new_action['node_type']}'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                node_id = result[0]['id']
            except Exception as e:
                return Response(
                    {"error": f"Failed to fetch random node ID: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Test the Cypher query
        try:
            query = new_action['query']
            id_field = new_action['id_field']
            parameters = {id_field: int(node_id)}
            graph_data = parse_to_graph_with_transformer(query, parameters)  # Assuming this function exists

            if not graph_data["nodes"] and not graph_data["edges"]:
                return Response(
                    {"error": "Query did not return any nodes, relationships, or paths"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {"error": f"Invalid Cypher query: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load existing actions
        try:
            with open(actions_file, 'r', encoding='utf-8') as file:
                actions_config = json.load(file)
        except FileNotFoundError:
            actions_config = []

        # Check for duplicate action name
        if any(action['name'] == new_action['name'] for action in actions_config):
            return Response(
                {"error": f"Action '{new_action['name']}' already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Append new action
        actions_config.append(new_action)

        # Save updated config
        with open(actions_file, 'w', encoding='utf-8') as file:
            json.dump(actions_config, file, indent=2, ensure_ascii=False)

        return Response(
            {"message": f"Action '{new_action['name']}' added successfully"},
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return Response(
            {"error": f"Error adding action: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def get_node_config(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        config_file = get_db_config_path(database_name) / 'config_style.json'

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return Response(config, status=status.HTTP_200_OK)
    except FileNotFoundError:
        return Response({'error': 'Configuration file not found'}, status=status.HTTP_404_NOT_FOUND)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON in configuration file'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def update_node_config(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        config_file = get_db_config_path(database_name) / 'config_style.json'
        print(config_file)
        node_type = request.data.get('nodeType')
        config = request.data.get('config', {})

        if not node_type:
            return Response({'error': 'nodeType is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Read existing config
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                node_config = json.load(f)
        except FileNotFoundError:
            node_config = {'nodeTypes': {}}

        # Initialize nodeTypes if not present
        if not node_config.get('nodeTypes'):
            node_config['nodeTypes'] = {}

        # Initialize node type if not present
        if not node_config['nodeTypes'].get(node_type):
            node_config['nodeTypes'][node_type] = {}

        # Update configuration
        if 'color' in config:
            node_config['nodeTypes'][node_type]['color'] = config['color']
        if 'size' in config:
            try:
                node_config['nodeTypes'][node_type]['size'] = int(config['size'])
            except (ValueError, TypeError):
                return Response({'error': 'size must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        if 'icon' in config:
            node_config['nodeTypes'][node_type]['icon'] = config['icon']
        if 'labelKey' in config:
            
            node_config['nodeTypes'][node_type]['labelKey'] = config['labelKey']

        # Write updated config
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(node_config, f, indent=2, ensure_ascii=False)

        return Response({'message': 'Node config updated'}, status=status.HTTP_200_OK)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON in configuration file'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def add_predefined_question(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        questions_file = get_db_config_path(database_name) / 'questions.json'

        # Validate required fields
        required_fields = ['question', 'query', 'parameters', 'parameterTypes']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"error": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validate parameter types
        for param, param_type in request.data['parameterTypes'].items():
            if param_type not in ['string', 'integer', 'float', 'boolean']:
                return Response(
                    {"error": f"Invalid parameter type for {param}: {param_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Test nessiter un logique soit donner la main a l'utilisateur de voir
      
        try:
            with open(questions_file, 'r', encoding='utf-8') as file:
                questions = json.load(file)
        except FileNotFoundError:
            questions = []

        # Generate new ID
        max_id = max([q['id'] for q in questions], default=0)
        new_question = {
            'id': max_id + 1,
            'question': request.data['question'],
            'query': request.data['query'],
            'parameters': request.data['parameters'],
            'parameterTypes': request.data['parameterTypes']
        }

        # Check for duplicate question
        if any(q['question'] == new_question['question'] for q in questions):
            return Response(
                {"error": f"Question '{new_question['question']}' already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Append new question
        questions.append(new_question)

        # Save updated questions
        with open(questions_file, 'w', encoding='utf-8') as file:
            json.dump(questions, file, indent=2, ensure_ascii=False)

        return Response(
            {"message": f"Question '{new_question['question']}' added successfully"},
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return Response(
            {"error": f"Error adding question: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def get_predefined_questions(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        questions_file = get_db_config_path(database_name) / 'questions.json'

        with open(questions_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        return Response(questions, status=status.HTTP_200_OK)
    except FileNotFoundError:
        return Response({'error': 'Questions file not found'}, status=status.HTTP_404_NOT_FOUND)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON in questions file'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def add_aggregation(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        aggregation_file = get_db_config_path(database_name) / 'aggregation.json'

        # Validate required fields
        required_fields = ['name', 'path']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"error": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        new_aggregation = {
            "name": request.data['name'],
            "path": request.data['path']
        }

        # Load existing aggregations
        try:
            with open(aggregation_file, 'r', encoding='utf-8') as file:
                aggregations = json.load(file)
        except FileNotFoundError:
            aggregations = []

        # Check for duplicate aggregation name
        if any(agg['name'] == new_aggregation['name'] for agg in aggregations):
            return Response(
                {"error": f"Aggregation '{new_aggregation['name']}' already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Append new aggregation
        aggregations.append(new_aggregation)

        # Save updated aggregations
        with open(aggregation_file, 'w', encoding='utf-8') as file:
            json.dump(aggregations, file, indent=2, ensure_ascii=False)

        return Response(
            {"message": f"Aggregation '{new_aggregation['name']}' added successfully"},
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return Response(
            {"error": f"Error adding aggregation: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def get_aggregations(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        aggregation_file = get_db_config_path(database_name) / 'aggregation.json'

        with open(aggregation_file, 'r', encoding='utf-8') as f:
            aggregations = json.load(f)
        return Response(aggregations, status=status.HTTP_200_OK)
    except FileNotFoundError:
        return Response({'error': 'Aggregation file not found'}, status=status.HTTP_404_NOT_FOUND)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON in aggregation file'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def get_actions_by_node_type(request):
    try:
        database_name = settings.NEO4J_DATABASE
        ensure_db_config_files(database_name)
        actions_file = get_db_config_path(database_name) / 'actions.json'
        # Validate required field
        node_type = request.data.get('node_type')
        if not node_type:
            return Response(
                {'error': 'node_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load actions
        try:
            with open(actions_file, 'r', encoding='utf-8') as f:
                actions = json.load(f)
        except FileNotFoundError:
            return Response(
                {'error': 'Actions file not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except json.JSONDecodeError:
            return Response(
                {'error': 'Invalid JSON in actions file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Filter actions by node_type
        filtered_actions = [
            action for action in actions 
            if action.get('node_type') == node_type
        ]
        
        return Response(filtered_actions, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': f'Error retrieving actions: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
def get_schema(request):
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        try:
            result = session.run("CALL db.schema.visualization()")
            record = result.single()

            if not record:
                return Response({'error': 'No schema data found'}, status=status.HTTP_404_NOT_FOUND)

            # Extraire les noeuds et relations
            nodes = record["nodes"]
            relationships = record["relationships"]

            # Transformer en format JSON-sérialisable
            formatted_nodes = [
                {
                    "id": node.id,
                    "labels": list(node.labels),
                    "properties": dict(node.items())
                } for node in nodes
            ]

            formatted_relationships = [
                {
                    "id": rel.id,
                    "type": rel.type,
                    "startNode": rel.start_node.id,
                    "endNode": rel.end_node.id,
                    "properties": dict(rel.items())
                } for rel in relationships
            ]

            return Response({
                "nodes": formatted_nodes,
                "relationships": formatted_relationships
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            driver.close()


