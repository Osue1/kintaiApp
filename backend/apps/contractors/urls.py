from django.urls import path

from .views import ContractorListCreateView, WorkRecordListView

urlpatterns = [
    path("", ContractorListCreateView.as_view(), name="contractors-list"),
    path("work-records", WorkRecordListView.as_view(), name="contractors-work-records"),
]
