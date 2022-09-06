from rest_framework import serializers
from .models import FileMetaData

class FileMetaDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileMetaData
        fields = '__all__'