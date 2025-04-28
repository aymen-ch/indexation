from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import status
from elasticsearch import Elasticsearch
from .models import Document, Query, Permission
from .serializers import DocumentSerializer, QuerySerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.parsers import FileUploadParser
from rest_framework.pagination import PageNumberPagination
from .filters import DocumentFilter, QueryFilter
import hashlib
from datetime import datetime
import os
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
# Create your views here.


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_suggestion(request):
    filterset = QueryFilter(request.GET, queryset=Query.objects.all().order_by('query'))
    
    if not filterset.is_valid():
        return Response({"error": "Invalid filters", "details": filterset.errors}, status=400)
    
    queryset = filterset.qs.distinct()
    queryset = filterset.qs.values('query').distinct().order_by('query')
    
    # On formate la réponse pour qu'elle retourne une liste d'objets avec clé "query"
    suggestions = [{"query": q["query"]} for q in queryset]
    serializer = QuerySerializer(queryset, many=True)
    
    return Response({
        "queries": suggestions
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_document_metadata(request):
    resPage = 10
    paginator = PageNumberPagination()
    paginator.page_size = resPage  # Définir la taille des pages pour la pagination
    
    filterset = DocumentFilter(request.GET, queryset=Document.objects.all().order_by('title'))
    
    if not filterset.is_valid():
        return Response({"error": "Invalid filters", "details": filterset.errors}, status=400)
    
    queryset = paginator.paginate_queryset(filterset.qs, request)
    
    serializer = DocumentSerializer(queryset, many=True)
    
    return paginator.get_paginated_response({
        "documents": serializer.data,
        "per_page": resPage,
        "count": filterset.qs.count(),
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_document_content(request):
    es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])
    query = request.GET.get('query', '')
    print(query)
    query_data = {
        "query": str(query)
    }
    serializer = QuerySerializer(data = query_data)
    if serializer.is_valid():
        Query.objects.create(**query_data, user=request.user)
        
    else:
        return Response(serializer.errors)
    if int(request.GET.get('page', '')) == 1:
        from_doc = 0
    else:
        from_doc = (int(request.GET.get('page', '')) * 10) - 1
    search_query = {
        "_source": ["file.filename", "file.extension", "file.indexing_date"],
        "from": from_doc,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["content"]
            }
        },
        "highlight": {
            "fields": {
                "content": {
                    "number_of_fragments": 5,
                    "fragment_size": 100,
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"]
                }
            }
        }
    } 
    results = es.search(index="investigation", body=search_query, size=10)
    print(results)
    official_results = {"auth": [], "not_auth": [], "permission": []}

    for item in results["hits"]["hits"]:
        try:
            user_owner = Document.objects.get(name=item["_source"]["file"]["filename"]).user
            temp_doc = {"file": item["_source"]["file"], "highlight": item["highlight"]}
            if user_owner == request.user:
                official_results["auth"].append(temp_doc)
            else:
                doc = Document.objects.filter(name=item["_source"]["file"]["filename"]).first()
                perm = Permission.objects.filter(document=doc, user_request=request.user).first()
                if perm:
                    if perm.is_active:
                        official_results["permission"].append(temp_doc)
                    else:
                        official_results["not_auth"].append(temp_doc)
                else:
                    official_results["not_auth"].append(temp_doc)
        except:
            pass
    
    if len(official_results["auth"]) == 0 and len(official_results["not_auth"]) == 0:
        return Response({"details": "you do not have results"})
    response_data = {
        "auth": official_results["auth"],
        "not_auth": official_results["not_auth"],
        "permission" : official_results["permission"]
    }
    return Response(response_data)
    #return Response(official_results)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def new_document(request):
    data = request.data
    parser_classes = (FileUploadParser,)
    file = request.data.get('file', None)
    if file:
        file_name = file.name
        destination = 'media/'
        ext = str(os.path.splitext(file_name)[1]).replace(".", "").lower()
        print(ext)
        if ext in ['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'csv', 'xslx','txt']:
            print("yessssssssssssssssssssssss")
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            str_to_hash = file_name + current_date
            hash = str(hashlib.sha256(str_to_hash.encode()).hexdigest()[:6]) + "_"
            data_doc = {
                "name" : f'{hash}{file_name}',
                "title" : data.get("title"),
                "keywords" : data.get("keywords").split(", "),
                "extension" : ext
            }
            serializer = DocumentSerializer(data = data_doc)
            if serializer.is_valid():
                doc = Document.objects.create(**data_doc, user=request.user)
                res = DocumentSerializer(doc, many=False)
                output = f'{destination}{hash}{file_name}'
                fn = open(output, 'wb+')
                for chunk in file.chunks():
                    fn.write(chunk)
                fn.close
                return Response({"details": "file is recived", "document": res.data}, status=200)
            else:
                return Response(serializer.errors)
        else:
            return Response({"error": "file extension not allowed"})
    else:
        return Response({"error": "file is None"}, status=400)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doc(request, filename):
        print("**********************")
        print(filename)
        print("*********USER TOKE***************")
        print(request.user)
        user_owner = Document.objects.get(name=filename).user
        print("*********USER Query***************")
        print(user_owner)
        if user_owner == request.user:
            print("yessssss")
            file_path = os.path.join(settings.MEDIA_ROOT, filename)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return HttpResponse(f.read(), content_type='application/octet-stream')
            else:
                return Response({"error":"file does not exist"})
        else:
            doc = Document.objects.filter(name=filename).first()
            perm = Permission.objects.filter(document=doc, user_request=request.user).first()
            if perm:
                if perm.is_active:
                    file_path = os.path.join(settings.MEDIA_ROOT, filename)
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            return HttpResponse(f.read(), content_type='application/octet-stream')
                    else:
                        return Response({"error":"file does not exist"})
                else:
                    return Response({"details": "You do not have permission"})        
            return Response({"details": "You do not have permission"})
        
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def new_request_permission(request, filename):
    try:
        user_request = request.user
        reason = request.data.get("reason")

        # Récupération du document
        document = Document.objects.filter(name=filename).first()
        if not document:
            return Response({"error": "Document not found"}, status=404)

        user_response = document.user

        # Création de la permission
        Permission.objects.create(
            user_request=user_request,
            user_response=user_response,
            document=document,
            reason=reason
        )
        return Response({"details": "Permission request created successfully!"}, status=201)

    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_permission_details(request):
    
    try:
        user = request.user
        print(user)
        documents_accepted = Permission.objects.filter(user_request=user, is_active=True).order_by('-responseAt')
        docs_accepted_json = []
        for item in documents_accepted:
            temp = {
                "filename": item.document.name,
                "owner": item.user_response.first_name+ " " +item.user_response.last_name,
                "request_date": item.requestAt,
                "response_date": item.responseAt
            }
            docs_accepted_json.append(temp)
        documents_request = Permission.objects.filter(user_response=user, is_active=False,responseAt__isnull=True)
        docs_request_json = []
        for item in documents_request:
            temp = {
                "filename": item.document.name,
                "user_request": item.user_request.first_name+ " " +item.user_request.last_name,
                "request_date": item.requestAt,
                "reason": item.reason,
                "permission_id": item.permission_id
            }
            docs_request_json.append(temp)
        response = {"documents_accepted": docs_accepted_json, "documents_resquest": docs_request_json}
        return Response(response, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def accept_permission(request, permission_id):
    try:
        perm = Permission.objects.filter(permission_id=permission_id).first()
        if perm:
            user = request.user
            user_owner = perm.user_response
            if user == user_owner:
                perm.is_active = True
                perm.responseAt = timezone.now()
                perm.save()
                return Response({"details": "Accès au document accepté"}, status=200)
            else:
                return Response({"details": "Vous n'avez pas la permission"}, status=403)
        else:
            return Response({"details": "Demande non trouvée"}, status=400)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def denied_permission(request, permission_id):
    try:
        perm = Permission.objects.filter(permission_id=permission_id).first()
        if perm:
            user = request.user
            user_owner = perm.user_response
            if user == user_owner:
                perm.is_active = False
                perm.responseAt = timezone.now()
                perm.save()
                return Response({"details": "Accès au document réfusé"}, status=200)
            else:
                return Response({"details": "Vous n'avez pas la permission"}, status=403)
        else:
            return Response({"details": "Demande non trouvée"}, status=400)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    