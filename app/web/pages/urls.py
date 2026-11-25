from django.urls import path

from . import views as v

urlpatterns = [
    path('', v.home, name='home'),
    path('book/', v.book, name='book'),
    path('manage/', v.manage_lookup, name='manage'),
    path('manage/booking/', v.manage_detail, name='manage_detail'),
    path('manage/change/', v.manage_change, name='manage_change'),
    path('manage/cancel/', v.manage_cancel, name='manage_cancel'),
    path('owner/login/', v.owner_login, name='owner_login'),
    path('owner/logout/', v.owner_logout, name='owner_logout'),
    path('owner/', v.dashboard, name='dashboard'),
    path('owner/booking/<int:pk>/', v.owner_booking, name='owner_booking'),
    path('owner/booking/<int:pk>/change/', v.owner_change, name='owner_change'),
    path('owner/manual/', v.owner_manual, name='owner_manual'),
    path('owner/hours/', v.hours, name='hours'),
    path('owner/services/', v.services, name='services'),
    path('owner/services/<int:pk>/', v.services, name='service_edit'),
    path('owner/blocks/', v.blocks, name='blocks'),
    path('owner/blocks/<int:pk>/remove/', v.unblock, name='unblock'),
    path('owner/settings/', v.shop_settings, name='settings'),
    path('owner/password/', v.password_change, name='password_change'),
]
