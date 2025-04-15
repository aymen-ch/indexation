# node_config/views.py
import json
import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

CONFIG_FILE = os.path.join(settings.BASE_DIR, 'config_style.json')

@api_view(['GET'])
def get_node_config(request):
    print("called me ")
    print(request)
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
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
        node_type = request.data.get('nodeType')
        config = request.data.get('config', {})

        if not node_type:
            return Response({'error': 'nodeType is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Read existing config
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
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
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(node_config, f, indent=2, ensure_ascii=False)

        return Response({'message': 'Node config updated'}, status=status.HTTP_200_OK)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON in configuration file'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)