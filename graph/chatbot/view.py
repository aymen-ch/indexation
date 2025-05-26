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
    
import re
def validate_query(generated_query, schema_description, error):
    validation_prompt = f"""
Given the following Neo4j database schema:
{schema_description}

And the following Cypher query:
{generated_query}
and the error given by Neo4j:
{error}

Please correct the query to avoid the error and return only the corrected Cypher query without any explanation  in this format

<Query>
   ....
</Query>
.
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
        modele = data.get('model')  # Default to 'Text' if not provide
        selected_nodes = data.get('selected_nodes', '')
        print(request.body)
        if not question:
            return Response({"error": "No question provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate the Cypher query using the LLM
        if selected_nodes:
            # Use prompt with selected nodes if provided
            prompt = simple_prompt_with_nodes(question=question, type=answer_type, selected_nodes=selected_nodes)
        else:
            if answer_type == 'graph':
                prompt = simple_prompt_graph(question=question)
            else:
                prompt = simple_prompt_table(question=question)
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
            # If the query execution fails, attempt to validate and correct it
            # print(f"Query failed with error: {query_result}")
            # corrected_query = validate_query(cypher_query, schema_description, query_result)
            # query_match = re.search(r'<Query>(.*?)</Query>', corrected_query, re.DOTALL)
            # if query_match:
            #     cypher_query = query_match.group(1).strip()
            # else:
            #     cypher_query = corrected_query  # Fallback if no tags are found

            
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
def chatbot_action(request):
    
    try:
        # Parse the request body
        data = json.loads(request.body)
        question = data.get('question')  # Extract the user's question
        node_type = data.get('node_type', 'Affaire')  # Default to 'Text' if not provided
        modele = data.get('model')  # Default to 'Text' if not provide
     
        print(request.body)
        if not question:
            return Response({"error": "No question provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        

        prompt = cypher_prompt_graph(question=question, node_type=node_type)
       
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
            # If the query execution fails, attempt to validate and correct it
            # print(f"Query failed with error: {query_result}")
            # corrected_query = validate_query(cypher_query, schema_description, query_result)
            # query_match = re.search(r'<Query>(.*?)</Query>', corrected_query, re.DOTALL)
            # if query_match:
            #     cypher_query = query_match.group(1).strip()
            # else:
            #     cypher_query = corrected_query  # Fallback if no tags are found

            
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