from .views import FileMetaDataView, FileTableView, ComputeDataView, PlotDataView
from django.urls import path

urlpatterns = [
    path('datasets', FileMetaDataView.as_view()),
    path('datasets/<str:tablename>', FileTableView.as_view()),
    path('datasets/<str:tablename>/compute', ComputeDataView.as_view()),
    path('datasets/<str:tablename>/plot', PlotDataView.as_view())
]