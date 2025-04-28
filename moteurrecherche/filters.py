import django_filters

from .models import Document, Query

class DocumentFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')
    keywords = django_filters.CharFilter(field_name="keywords", lookup_expr='icontains')
    before = django_filters.DateTimeFilter(field_name="uploadAt", lookup_expr='lte')
    after = django_filters.DateTimeFilter(field_name="uploadAt", lookup_expr='gte')


    class Meta:
        model = Document
        fields = ('title', 'extension', 'keywords', 'before', 'after')


class QueryFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Query
        fields = ['query']