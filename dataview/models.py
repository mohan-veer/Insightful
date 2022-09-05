from django.db import models
from django.utils import timezone

# Create your models here.

class FileMetaData(models.Model):
    table_name = models.CharField(max_length=100, null=False, blank=False)
    uploaded_on = models.DateTimeField(default=timezone.now, null=False, blank=False)
    last_modified = models.DateTimeField(default=timezone.now, null=True, blank=True)
    data_cleaning = models.BooleanField(default=False)
    column_headers = models.CharField(max_length=500, null=False, blank=False)
    total_cols = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.table_name} uploaded on {self.uploaded_on} with cols count as {self.total_cols}"

