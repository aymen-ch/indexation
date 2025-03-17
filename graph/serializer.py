from rest_framework import serializers


class NodeTypeSerializer(serializers.Serializer):
    type = serializers.CharField()


class NodeSearchSerializer(serializers.Serializer):
    node_type = serializers.CharField()
    property = serializers.CharField()
    value = serializers.CharField()
