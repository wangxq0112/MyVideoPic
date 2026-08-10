from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('api/', include('videos.urls')),
    # 应急排障入口；日常操作全部走前端界面
    path('admin/', admin.site.urls),
]
