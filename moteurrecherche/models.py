from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class Extension(models.TextChoices):
    PDF = 'pdf'
    DOC = 'doc'
    DOCX = 'docx'
    PNG = 'png'
    JPG = 'jpg'
    JPEG = 'jpeg'
    CSV = 'csv'
    XLSX = 'xslx'
    TXT = 'txt'

class Document(models.Model):
    name = models.CharField(max_length=100, default="", blank=False)
    title = models.CharField(max_length=255, default="", blank=True)
    keywords = models.JSONField(default=list)
    extension = models.CharField(max_length=10, choices=Extension.choices, default="")
    uploadAt = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.title
    
class Query(models.Model):
    query = models.CharField(max_length=255, default="", blank=False)
    solicitAt = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)


    def __str__(self):
        return self.user.first_name
    

class Permission(models.Model):
    permission_id = models.AutoField(primary_key=True,default=1)
    user_request = models.ForeignKey(User, null=True, on_delete=models.SET_NULL,related_name='permissions_requested')
    user_response = models.ForeignKey(User, null=True, on_delete=models.SET_NULL,related_name='permissions_responded')
    document = models.ForeignKey(Document, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=255, default="", blank=True)
    is_active = models.BooleanField(default=False)
    requestAt = models.DateTimeField(auto_now_add=True)
    responseAt = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return self.user_request.first_name