from rest_framework import serializers
from .models import Document, Query

class DocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Document
        #fields = "__all__"
        fields = ('name', 'title', 'keywords', 'extension')

class QuerySerializer(serializers.ModelSerializer):

    class Meta:
        model = Query
        fields = ['query']