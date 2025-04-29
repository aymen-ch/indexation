from django.contrib import admin

from .models import Document, Query, Permission

# Register your models here.
admin.site.register(Document)
admin.site.register(Query)
admin.site.register(Permission)