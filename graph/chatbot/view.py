from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from .utils import *
from graph.views import run_query


@api_view(['POST'])
def execute_query(request):
    """
    Django view to execute a Neo4j query.
    Expects a JSON payload with 'query' and 'parameters'.
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
    
def validate_query(generated_query, schema_description, error):
    validation_prompt = f"""
Given the following Neo4j database schema:
{schema_description}

And the following Cypher query:
{generated_query}
and the error given by Neo4j:
{error}

Please return only the corrected Cypher query without any explanation.
"""
    response = call_ollama(validation_prompt, model="hf.co/DavidLanz/text2cypher-gemma-2-9b-it-finetuned-2024v1:latest")
    return response.strip()
@api_view(['POST'])
def chatbot(request):

    try:
        # Parse the request body
        data = json.loads(request.body)
        question = data.get('question')  # Extract the user's question
        answer_type = data.get('answer_type', 'Text')  # Default to 'Text' if not provided

        if not question:
            return Response({"error": "No question provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate the Cypher query using the LLM
        formatted_prompt = few_shot_prompt.format(question=question, schema_description=schema_description)
        cypher_query = call_ollama(formatted_prompt, model="hf.co/DavidLanz/text2cypher-gemma-2-9b-it-finetuned-2024v1:latest")
        
        # Replace specific terms in the Cypher query
        cypher_query = cypher_query.replace("nationel_id", "`رقم التعريف الوطني`")
        cypher_query = cypher_query.replace("birth_date", "`تاريخ الميلاد`")
        cypher_query = cypher_query.replace("firstname", "الاسم")
        cypher_query = cypher_query.replace("lastname", "اللقب")
        cypher_query = cypher_query.replace("->", "-")
        cypher_query = cypher_query.replace("<-", "-")
        query_result, success = execute_query_for_response_generation(cypher_query)
        # Debugging: Print the Cypher query
        print("Generated Cypher Query:", cypher_query)

        if not success:
            # If the query execution fails, attempt to validate and correct it
            print(f"Query failed with error: {query_result}")
            corrected_query = validate_query(cypher_query, schema_description, query_result)
            print("Corrected Cypher Query:", corrected_query)
            
            # Re-execute the corrected query
            query_result, success = execute_query_for_response_generation(corrected_query)
            
            if not success:
                # If the corrected query still fails, return the error
                return Response(
                    {
                        "cypher_query": corrected_query,
                        "response": 'je ne peux pas répondre'  # Updated error message
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            else:
                # Update cypher_query to the corrected one for the response
                cypher_query = corrected_query

        # Handle response based on answer type
        if answer_type == 'graph':
            return JsonResponse({"cypher":cypher_query}, status=status.HTTP_200_OK)

        elif answer_type == 'JSON':
            # Return the query result and Cypher query as JSON
            return Response(
                {
                    "response": query_result,
                    "cypher_query": cypher_query
                },
                status=status.HTTP_200_OK
            )

        else:
            # For 'Text' answer type, generate a human-readable response
            formatted_table_prompt = zero_shot_prompt.format(input_question=question, Cypher=cypher_query, input_context=query_result)
            answer = call_ollama(formatted_table_prompt, model="hf.co/DavidLanz/text2cypher-gemma-2-9b-it-finetuned-2024v1:latest")
            
            return Response(
                {
                    "response": answer,
                    "cypher_query": cypher_query
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