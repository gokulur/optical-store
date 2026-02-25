from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('track/',          views.job_track,        name='track'),
    path('my-jobs/',        views.my_jobs,           name='my_jobs'),
    path('my-jobs/<str:job_number>/', views.job_detail_user, name='detail'),
]
