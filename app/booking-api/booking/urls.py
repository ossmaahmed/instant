from django.urls import path

from . import views

urlpatterns = [
    path('healthz', views.healthz),
    path('api/booking/services/', views.ServiceList.as_view()),
    path('api/booking/shop/', views.ShopDetail.as_view()),
    path('api/booking/schedules/', views.ScheduleList.as_view()),
    path('api/booking/availability/', views.Availability.as_view()),
    path('api/booking/bookings/', views.BookingCreate.as_view()),
    path('api/booking/bookings/lookup/', views.BookingLookup.as_view()),
    path('api/booking/bookings/<str:code>/availability/', views.GuestBookingAvailability.as_view()),
    path('api/booking/bookings/<str:code>/change/', views.GuestBookingChange.as_view()),
    path('api/booking/bookings/<str:code>/cancel/', views.GuestBookingCancel.as_view()),
    path('api/booking/owner/bookings/', views.OwnerBookingList.as_view()),
    path('api/booking/owner/bookings/<int:pk>/', views.OwnerBookingDetail.as_view()),
    path('api/booking/owner/bookings/<int:pk>/change/', views.OwnerBookingChange.as_view()),
    path('api/booking/owner/bookings/<int:pk>/status/', views.OwnerBookingStatus.as_view()),
    path('api/booking/owner/bookings/<int:pk>/availability/', views.OwnerBookingAvailability.as_view()),
    path('api/booking/owner/schedules/', views.OwnerScheduleList.as_view()),
    path('api/booking/owner/weekly/', views.OwnerWeekly.as_view()),
    path('api/booking/owner/services/', views.OwnerServiceList.as_view()),
    path('api/booking/owner/services/<int:pk>/', views.OwnerServiceDetail.as_view()),
    path('api/booking/owner/blocks/', views.OwnerBlockList.as_view()),
    path('api/booking/owner/blocks/<int:pk>/remove/', views.OwnerBlockRemove.as_view()),
    path('api/booking/owner/shop/', views.OwnerShopUpdate.as_view()),
]
