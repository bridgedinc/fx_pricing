from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render


class UserLoginView(LoginView):

    form_class = AuthenticationForm
    template_name = "login.html"