from . import views
from django.urls import path

urlpatterns = [
    path('', views.homePage, name="home-page"),
    path('data/', views.dataPage, name="data-page"),
    path('data/upload/', views.uploadCSV, name="uploadCSV"),
    path('plot/', views.plotData, name="plot-page"),
    path('plot/compute/', views.computeData, name="compute"),
    path('plot/graph/', views.plotGraph, name="graph"),
]