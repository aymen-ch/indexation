from django.urls import path
from . import views


urlpatterns = [
    path('documents/metadata', views.get_document_metadata, name="get_document_metadata"),
    path('documents/suggestion', views.get_suggestion, name="get_suggestion"),
    path('documents/search', views.get_document_content, name="get_document_content"),
    path('documents/new', views.new_document, name="new_document"),
    path('media/<str:filename>', views.get_doc, name='get_doc'),
    path('permission/<str:filename>', views.new_request_permission, name='new_request_permission'),
    path('documents/permission', views.get_permission_details, name='get_permission_details'),
    path('documents/permission/accept/<int:permission_id>', views.accept_permission, name='accept_permission'),
    path('documents/permission/denied/<int:permission_id>', views.denied_permission, name='denied_permission'),
]