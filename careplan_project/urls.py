from django.urls import path
from careplan import views

urlpatterns = [
    path('', views.home),
    path('api/generate-careplan/', views.generate_careplan),
]
