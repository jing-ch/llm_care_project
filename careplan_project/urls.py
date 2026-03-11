from django.urls import path
from careplan import views

urlpatterns = [
    path('', views.home),
    path('api/generate-careplan/', views.generate_careplan),
    path('api/careplan/search/', views.search_careplans),
    path('api/careplan/<int:care_plan_id>/status/', views.get_careplan_status),
    path('api/careplan/<int:care_plan_id>/', views.get_careplan),
    path('api/careplan/<int:care_plan_id>/download/', views.download_careplan),
]
