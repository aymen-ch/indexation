from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from .utils import *
from graph.Utility_QueryExecutors import run_query


@api_view(['POST'])
def execute_query(request):
    """
    Executes a Neo4j query and returns the result as JSON.

    This function takes a query and parameters as input, and returns the query result.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the query and parameters.

    Returns:
        JsonResponse: A JSON response with the query result.

    Raises:
        Exception: If any error occurs during query execution.
    """
    try:
        # Parse the JSON payload
        data = request.data
        query = data.get('query')
        parameters = data.get('parameters', {})  # Default to empty dict if no parameters provided
        print(query)
        print(parameters)
        # Validate the query
        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)

        # Run the query using the utility function
        result = run_query(query, parameters)

        # Return the query result as JSON
        return JsonResponse({'result': result}, status=200)

    except Exception as e:
        # Handle any errors
        return JsonResponse({'error': str(e)}, status=500)
    
import re


@api_view(['POST'])
def chatbot(request):
    
    """
    Handles the POST request to the /chatbot endpoint.

    This function takes a question, answer type, and model as input, and returns a response.
    It uses the LLM to generate a Cypher query, executes the query, and returns the result.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the question, answer type, and model.

    Returns:
        Response: A JSON response with the query result and Cypher query.

    Raises:
        json.JSONDecodeError: If the request body contains invalid JSON.
        Exception: If any other error occurs.
    """
    
    try:
        # Parse the request body
        data = json.loads(request.body)
        question = data.get('question')  # Extract the user's question
        answer_type = data.get('answer_type', 'Text')  # Default to 'Text' if not provided
        modele = data.get('model')  # Default to 'Text' if not provide
        selected_nodes = data.get('selected_nodes', '')
        print(request.body)
        if not question:
            return Response({"error": "No question provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate the Cypher query using the LLM
        if selected_nodes:
            # Use prompt with selected nodes if provided
            prompt = simple_prompt_with_selected_nodes(question=question, type=answer_type, selected_nodes=selected_nodes)
        else:
            if answer_type == 'graph':
                prompt = prompt_graph_query(question=question)
            else:
                prompt = prompt_table_query(question=question)
        cypher_response = call_ollama(prompt=prompt, model=modele)

        # Extract the query between <Query> tags
        query_match = re.search(r'<Query>(.*?)</Query>', cypher_response, re.DOTALL)
        if query_match:
            cypher_query = query_match.group(1).strip()
        else:
            cypher_query = cypher_response  # Fallback if no tags are found
        # Replace specific terms in the Cypher query
    
        query_result, success = execute_query_for_response_generation(cypher_query)
        # Debugging: Print the Cypher query
        print("Generated Cypher Query:", cypher_query)

        if not success:
            # Re-execute the corrected query
            query_result, success = execute_query_for_response_generation(cypher_query)
            
            if not success:
                # If the corrected query still fails, return the error
                return Response(
                    {
                        "cypher": cypher_query,
                        "response": 'je ne peux pas répondre'  # Updated error message
                    },
                    status=status.HTTP_200_OK
                )
            else:
                # Update cypher_query to the corrected one for the response
                cypher_query = cypher_query

        # Handle response based on answer type
        if answer_type == 'graph':
            return JsonResponse({"cypher":cypher_query}, status=status.HTTP_200_OK)
        if answer_type == 'table':
            return JsonResponse({"cypher":cypher_query}, status=status.HTTP_200_OK)

        elif answer_type == 'JSON':
            # Return the query result and Cypher query as JSON
            return Response(
                {
                    "response": query_result,
                    "cypher": cypher_query
                },
                status=status.HTTP_200_OK
            )

        else:
            return Response(
                {
                    "response": query_result,
                    "cypher": cypher_query
                },
                status=status.HTTP_200_OK
            )

    except json.JSONDecodeError:
        return Response(
            {"error": "Invalid JSON in request body"},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        # Log the error for debugging
        print(f"Error in chatbot endpoint: {str(e)}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
def chatbot_generate_action(request):
    """
    Handles the POST request to the /chatbot/generate/action endpoint.

    This function takes a question, node type, and model as input, and returns a Cypher query and response.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the question, node type, and model.

    Returns:
        JsonResponse: A JSON response with the Cypher query and response.

    Raises:
        Exception: If any error occurs.
    """
    try:
        # Parse the request body
        data = json.loads(request.body)
        question = data.get('question')  # Extract the user's question
        node_type = data.get('node_type', 'Affaire')  # Default to 'Text' if not provided
        modele = data.get('model')  # Default to 'Text' if not provide
        print(question)
        print(request.body)
        if not question:
            return Response({"error": "No question provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        

        prompt = cypher_promp_action(question=question, node_type=node_type)
       
        # cypher_response = call_ollama(prompt=prompt, model=modele)
        cypher_response="hi"
        # Extract the query between <Query> tags
        query_match = re.search(r'<Query>(.*?)</Query>', cypher_response, re.DOTALL)
        if query_match:
            cypher_query = query_match.group(1).strip()
        else:
            cypher_query = cypher_response  # Fallback if no tags are found
        # Replace specific terms in the Cypher query

        query_result, success = execute_query_for_response_generation(cypher_query)
        # Debugging: Print the Cypher query
        print("Generated Cypher Query:", cypher_query)

        if not success:
            # Re-execute the corrected query
            query_result, success = execute_query_for_response_generation(cypher_query)
            
            if not success:
                # If the corrected query still fails, return the error
                return Response(
                    {
                        "cypher": cypher_query,
                        "response": 'je ne peux pas répondre'  # Updated error message
                    },
                    status=status.HTTP_200_OK
                )
            else:
                # Update cypher_query to the corrected one for the response
                cypher_query = cypher_query

        # Handle response based on answer type
        return JsonResponse({"cypher":cypher_query}, status=status.HTTP_200_OK)


    except json.JSONDecodeError:
        return Response(
            {"error": "Invalid JSON in request body"},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        # Log the error for debugging
        print(f"Error in chatbot endpoint: {str(e)}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
def chatbot_resume(request):
    """
    Handles the POST request to the /chatbot/resume endpoint.

    This function takes the raw response from a previous call, a model, and a question as input, and returns a resumed response.

    Parameters:
        request (HttpRequest): The HTTP request object.
        data (dict): The JSON payload containing the raw response, model, and question.

    Returns:
        Response: A JSON response with the resumed content and Cypher query.

    Raises:
        json.JSONDecodeError: If the request body contains invalid JSON.
        Exception: If any other error occurs.
    """
    try:
        # Parse the request body
        data = json.loads(request.body)
        raw_response = data.get('raw_response')  # Extract the raw response from the previous call
        model = data.get('model')  # Extract the model
        question=data.get('question')
        cypher_query=data.get('cypher_query')
        print(data)
        if not raw_response:
            return Response(
                {"error": "No raw response provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not model:
            return Response(
                {"error": "No model provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        prompt = simple_prompet_resume(context=raw_response, question=question, cypher_query=cypher_query) # Adjust based on how simple_prompet works
        resume_response = call_ollama(prompt=prompt, model=model)

        # Extract the content between <Resume> tags
        resume_match = re.search(r'<Resume>(.*?)</Resume>', resume_response, re.DOTALL)
        if resume_match:
            resumed_content = resume_match.group(1).strip()
        else:
            resumed_content = resume_response  # Fallback if no tags are found

        
        # Return the resumed response
        response_data = {
            "response": resumed_content,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response(
            {"error": "Invalid JSON in request body"},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        # Log the error for debugging
        print(f"Error in chatbot_resume endpoint: {str(e)}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )