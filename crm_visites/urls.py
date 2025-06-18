"""
URL configuration for crm_visites project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import path, include
from django.contrib.auth import views as auth_views
from front.views import satisfaction_b2b

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('front.urls')),
    path('reset-password/', auth_views.PasswordResetView.as_view(
        template_name='front/reset_password.html',
        email_template_name='front/reset_password_email.html',
        subject_template_name='front/reset_password_subject.txt'
    ), name='reset_password'),
    path('reset-password/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='front/reset_password_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='front/new_password.html'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='front/reset_password_complete.html'
    ), name='password_reset_complete'),
    path('satisfaction-b2b/', satisfaction_b2b, name='satisfaction_b2b'),
]
