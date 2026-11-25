from django.urls import path

from . import views

urlpatterns = [
    path('healthz', views.healthz),
    path('api/identity/login/', views.Login.as_view()),
    path('api/identity/logout/', views.Logout.as_view()),
    path('api/identity/verify/', views.Verify.as_view()),
    path('api/identity/password/', views.PasswordChange.as_view()),
]
