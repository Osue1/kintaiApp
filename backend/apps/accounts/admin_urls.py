from django.urls import path

from .views import EmployeeDetailView, EmployeeListCreateView, EmployeeOptionsView

urlpatterns = [
    path("", EmployeeListCreateView.as_view(), name="employees-list"),
    path("options", EmployeeOptionsView.as_view(), name="employees-options"),
    path("<int:pk>", EmployeeDetailView.as_view(), name="employees-detail"),
]
