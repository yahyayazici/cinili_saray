from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def home(request):
    return render(request, "home.html")


def login_view(request):
    error_message = None

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            auth_login(request, user)
            return redirect("dashboard")

        error_message = "Kullanıcı adı veya şifre hatalı."

    return render(
        request,
        "login.html",
        {"error_message": error_message},
    )


@login_required(login_url="login")
def dashboard(request):
    return render(request, "dashboard.html")