from core.models import Etut


def panel_nav(request):
    """Sidebar için aktif etüt (Talebeler linki vb.)."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"nav_etut": None}

    qs = Etut.objects.filter(aktif=True)
    if user.is_superuser:
        etut = qs.first()
    else:
        own = qs.filter(hoca=user)
        etut = own.first() if own.exists() else qs.first()
    return {"nav_etut": etut}
