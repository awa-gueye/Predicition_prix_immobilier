"""
=== REMPLACER register_view dans immoanalytics_dash/views.py ===
Cette fonction collecte le numéro de téléphone à l'inscription.
"""
from django.contrib.auth.models import User
from django.contrib.auth import login


def register_view(request):
    """Inscription avec collecte du numéro de téléphone."""
    error = None

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        # Validations
        if not username:
            error = "Le nom d'utilisateur est obligatoire."
        elif User.objects.filter(username=username).exists():
            error = "Ce nom d'utilisateur est déjà pris."
        elif not email:
            error = "L'email est obligatoire."
        elif User.objects.filter(email=email).exists():
            error = "Cette adresse email est déjà utilisée."
        elif not phone:
            error = "Le numéro de téléphone est obligatoire."
        elif password1 != password2:
            error = "Les mots de passe ne correspondent pas."
        elif len(password1) < 8:
            error = "Le mot de passe doit contenir au moins 8 caractères."
        else:
            # Créer le User
            user = User.objects.create_user(
                username   = username,
                email      = email,
                password   = password1,
                first_name = first_name,
                last_name  = last_name,
            )
            # Créer / mettre à jour le profil avec le téléphone
            try:
                from listings.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.phone = phone
                profile.save()
            except Exception:
                pass  # listings pas encore installé

            login(request, user)
            return redirect('dashboard')

    return render(request, 'immoanalytics/register.html', {'error': error})
