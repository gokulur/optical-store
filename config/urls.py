from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),   

    path('adminpanel/', include('adminpanel.urls')),
    path('catalog/', include('catalog.urls')),
    path('cart/', include('cart.urls')),
    path('lenses/', include('lenses.urls')),
    path('orders/', include('orders.urls')),
    path('prescriptions/', include('prescriptions.urls')),
    path('store/', include('store.urls')),
    path('accounts/', include('users.urls')),
    path('content/', include('content.urls')),
    path('reviews/', include('reviews.urls')),
    path('notifications/', include('notifications.urls')),
    path('promotions/', include('promotions.urls')),
    path('search/', include('search.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
