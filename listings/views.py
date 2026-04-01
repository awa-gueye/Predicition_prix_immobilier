"""
listings/views.py
Vues pour : Vente, Location, Ajout annonce, Profil, Modification profil.
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import UserProfile, Listing, ListingImage
from .forms import ProfileForm, ListingForm, ListingImageForm

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────
def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _ctx(request, extra=None):
    from immoanalytics_dash.views import get_user_role
    ctx = {'user': request.user, 'role': get_user_role(request.user)}
    if extra:
        ctx.update(extra)
    return ctx


def _fmt(p):
    if not p: return "—"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _scraped_listings(transaction):
    """
    Charge les annonces scraées depuis les 4 sources pour vente/location.
    transaction: 'vente' ou 'location'
    """
    from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
                                   LogerDakarProperty, DakarVenteProperty)
    import re

    KW_LOC = ['louer','location','locat','bail','mensuel','loyer','a louer']
    KW_VTE = ['vendre','vente','achat','cession','a vendre']

    def is_location(row_dict):
        text = ' '.join([
            str(row_dict.get('statut') or ''),
            str(row_dict.get('title') or ''),
            str(row_dict.get('property_type') or ''),
        ]).lower()
        sl = sum(k in text for k in KW_LOC)
        sv = sum(k in text for k in KW_VTE)
        if sl > sv: return True
        if sv > sl: return False
        price = float(row_dict.get('price') or 0)
        return 0 < price <= 3_000_000

    results = []
    SRCS = [
        (CoinAfriqueProperty,  'coinafrique', '#F59E0B'),
        (ExpatDakarProperty,   'expat_dakar', '#2563EB'),
        (LogerDakarProperty,   'loger_dakar', '#0E6B4A'),
        (DakarVenteProperty,   'dakarvente',  '#C0392B'),
    ]

    for model, src_name, color in SRCS:
        try:
            avail = [f.name for f in model._meta.get_fields()]
            fields = [f for f in ['id','title','price','surface_area','bedrooms',
                                  'bathrooms','city','property_type','statut',
                                  'description','latitude','longitude'] if f in avail]
            qs = list(model.objects.filter(price__isnull=False, price__gt=0).values(*fields)[:3000])
            for row in qs:
                loc = is_location(row)
                if (transaction == 'location' and loc) or (transaction == 'vente' and not loc):
                    results.append({
                        'id':            str(row.get('id','')),
                        'title':         row.get('title') or 'Annonce',
                        'price':         row.get('price') or 0,
                        'price_fmt':     _fmt(row.get('price') or 0),
                        'price_unit':    '/mois' if loc else '',
                        'surface_area':  row.get('surface_area'),
                        'bedrooms':      row.get('bedrooms'),
                        'bathrooms':     row.get('bathrooms'),
                        'city':          str(row.get('city') or '').split(',')[0].strip().title() or 'Dakar',
                        'property_type': str(row.get('property_type') or 'Bien').split(',')[0][:40],
                        'description':   str(row.get('description') or '')[:200],
                        'latitude':      row.get('latitude'),
                        'longitude':     row.get('longitude'),
                        'source':        src_name,
                        'source_color':  color,
                        'image':         None,  # pas d'image pour les scraped
                        'is_scraped':    True,
                    })
        except Exception as e:
            logger.warning(f"_scraped_listings {src_name}: {e}")
            continue

    return results


# ══════════════════════════════════════════════════════════════
# VENTE
# ══════════════════════════════════════════════════════════════
@login_required(login_url='/immo/login/')
def vente_page(request):
    """Onglet Vente — annonces scraées + annonces vendeurs."""
    q        = request.GET.get('q', '').strip()
    type_f   = request.GET.get('type', '')
    city_f   = request.GET.get('city', '')
    sort_f   = request.GET.get('sort', 'recent')

    # Annonces vendeurs en vente
    seller_qs = Listing.objects.filter(
        transaction='vente', status='active'
    ).prefetch_related('images', 'seller__profile')

    # Annonces scraées
    scraped = _scraped_listings('vente')

    # Filtres vendeurs
    if q:
        seller_qs = seller_qs.filter(
            Q(title__icontains=q) | Q(city__icontains=q) |
            Q(neighborhood__icontains=q) | Q(description__icontains=q))
    if type_f:
        seller_qs = seller_qs.filter(property_type__icontains=type_f)
    if city_f:
        seller_qs = seller_qs.filter(Q(city__icontains=city_f) | Q(neighborhood__icontains=city_f))

    # Tri vendeurs
    if sort_f == 'price_asc':  seller_qs = seller_qs.order_by('price')
    elif sort_f == 'price_desc': seller_qs = seller_qs.order_by('-price')
    else: seller_qs = seller_qs.order_by('-created_at')

    # Filtres annonces scraées
    if q:
        scraped = [s for s in scraped if (s.get('title') and q.lower() in s['title'].lower()) or (s.get('city') and q.lower() in s['city'].lower())]
    if type_f:
        scraped = [s for s in scraped if s.get('property_type') and type_f.lower() in s['property_type'].lower()]
    if city_f:
        scraped = [s for s in scraped if s.get('city') and city_f.lower() in s['city'].lower()]

    # Tri annonces scraées
    if sort_f == 'price_asc':  scraped.sort(key=lambda x: x['price'])
    elif sort_f == 'price_desc': scraped.sort(key=lambda x: x['price'], reverse=True)

    # Pagination annonces scraées
    paginator = Paginator(scraped, 12)
    page_obj  = paginator.get_page(request.GET.get('page_sc', 1))

    # Villes disponibles pour filtre
    cities = sorted(set(
        [s['city'] for s in _scraped_listings('vente')[:500] if s['city']] +
        list(Listing.objects.filter(transaction='vente', status='active')
             .values_list('city', flat=True).distinct())
    ))

    return render(request, 'immoanalytics/vente.html', _ctx(request, {
        'page_title':    'Biens en Vente',
        'seller_listings': list(seller_qs[:20]),
        'scraped_page':  page_obj,
        'scraped_total': len(scraped),
        'seller_total':  seller_qs.count(),
        'q': q, 'type_f': type_f, 'city_f': city_f, 'sort_f': sort_f,
        'cities':    cities[:80],
        'types':     Listing.TYPE_CHOICES,
        'sort_opts': [('recent','Plus récents'),('price_asc','Prix ↑'),('price_desc','Prix ↓')],
    }))


# ══════════════════════════════════════════════════════════════
# LOCATION
# ══════════════════════════════════════════════════════════════
@login_required(login_url='/immo/login/')
def location_page(request):
    """Onglet Location — annonces scraées + annonces vendeurs."""
    q      = request.GET.get('q', '').strip()
    type_f = request.GET.get('type', '')
    city_f = request.GET.get('city', '')
    sort_f = request.GET.get('sort', 'recent')

    seller_qs = Listing.objects.filter(
        transaction='location', status='active'
    ).prefetch_related('images', 'seller__profile')

    scraped = _scraped_listings('location')

    if q:
        seller_qs = seller_qs.filter(
            Q(title__icontains=q) | Q(city__icontains=q) | Q(description__icontains=q))
        scraped = [s for s in scraped if (s.get('title') and q.lower() in s['title'].lower()) or (s.get('city') and q.lower() in s['city'].lower())]
    if type_f:
        seller_qs = seller_qs.filter(property_type__icontains=type_f)
        scraped = [s for s in scraped if s.get('property_type') and type_f.lower() in s['property_type'].lower()]
    if city_f:
        seller_qs = seller_qs.filter(Q(city__icontains=city_f))
        scraped = [s for s in scraped if s.get('city') and city_f.lower() in s['city'].lower()]

    if sort_f == 'price_asc':   seller_qs = seller_qs.order_by('price');  scraped.sort(key=lambda x: x['price'])
    elif sort_f == 'price_desc': seller_qs = seller_qs.order_by('-price'); scraped.sort(key=lambda x: x['price'], reverse=True)
    else: seller_qs = seller_qs.order_by('-created_at')

    paginator = Paginator(scraped, 12)
    page_obj  = paginator.get_page(request.GET.get('page_sc', 1))

    cities = sorted(set(
        [s['city'] for s in _scraped_listings('location')[:500] if s['city']] +
        list(Listing.objects.filter(transaction='location', status='active')
             .values_list('city', flat=True).distinct())
    ))

    return render(request, 'immoanalytics/location.html', _ctx(request, {
        'page_title':    'Biens en Location',
        'seller_listings': list(seller_qs[:20]),
        'scraped_page':  page_obj,
        'scraped_total': len(scraped),
        'seller_total':  seller_qs.count(),
        'q': q, 'type_f': type_f, 'city_f': city_f, 'sort_f': sort_f,
        'cities':    cities[:80],
        'types':     Listing.TYPE_CHOICES,
        'sort_opts': [('recent','Plus récents'),('price_asc','Prix ↑'),('price_desc','Prix ↓')],
    }))


# ══════════════════════════════════════════════════════════════
# DETAIL ANNONCE VENDEUR
# ══════════════════════════════════════════════════════════════
@login_required(login_url='/immo/login/')
def listing_detail(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status='active')
    listing.views_count += 1
    listing.save(update_fields=['views_count'])
    return render(request, 'immoanalytics/listing_detail.html', _ctx(request, {
        'listing': listing,
        'images':  listing.images.all(),
        'seller_profile': _get_or_create_profile(listing.seller),
    }))


# ══════════════════════════════════════════════════════════════
# AJOUT ANNONCE
# ══════════════════════════════════════════════════════════════
@login_required(login_url='/immo/login/')
def add_listing(request):
    profile = _get_or_create_profile(request.user)

    # Vérifier que c'est un vendeur
    if profile.role != 'seller':
        messages.warning(request,
            "Vous devez être vendeur pour ajouter une annonce. "
            "Modifiez votre statut dans votre profil.")
        return redirect('edit_profile')

    if request.method == 'POST':
        form = ListingForm(request.POST)
        files = request.FILES.getlist('images')

        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()

            # Sauvegarder les images
            for i, f in enumerate(files[:8]):  # max 8 images
                ListingImage.objects.create(
                    listing  = listing,
                    image    = f,
                    is_main  = (i == 0),
                    order    = i,
                )

            messages.success(request, "✅ Votre annonce a été publiée !")
            if listing.transaction == 'vente':
                return redirect('vente')
            return redirect('location')
    else:
        form = ListingForm()

    return render(request, 'immoanalytics/add_listing.html', _ctx(request, {
        'form':    form,
        'profile': profile,
    }))


# ══════════════════════════════════════════════════════════════
# MODIFICATION ANNONCE
# ══════════════════════════════════════════════════════════════
@login_required(login_url='/immo/login/')
def edit_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if request.method == 'POST':
        form  = ListingForm(request.POST, instance=listing)
        files = request.FILES.getlist('images')

        if form.is_valid():
            listing = form.save()

            for i, f in enumerate(files[:8]):
                ListingImage.objects.create(
                    listing = listing,
                    image   = f,
                    is_main = (i == 0 and not listing.images.filter(is_main=True).exists()),
                    order   = listing.images.count() + i,
                )

            messages.success(request, "✅ Annonce mise à jour.")
            return redirect('my_listings')
    else:
        form = ListingForm(instance=listing)

    return render(request, 'immoanalytics/add_listing.html', _ctx(request, {
        'form':    form,
        'listing': listing,
        'edit':    True,
    }))


@login_required(login_url='/immo/login/')
@require_POST
def delete_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    listing.delete()
    messages.success(request, "Annonce supprimée.")
    return redirect('my_listings')


@login_required(login_url='/immo/login/')
def my_listings(request):
    listings = Listing.objects.filter(seller=request.user).prefetch_related('images')
    return render(request, 'immoanalytics/my_listings.html', _ctx(request, {
        'listings': listings,
    }))


# ══════════════════════════════════════════════════════════════
# PROFIL
# ══════════════════════════════════════════════════════════════
@login_required(login_url='/immo/login/')
def profile_view(request):
    profile  = _get_or_create_profile(request.user)
    listings = Listing.objects.filter(seller=request.user).prefetch_related('images')[:6]

    user_perms = [
        {"icon": "fas fa-chart-line",    "label": "Dashboard",   "has": True},
        {"icon": "fas fa-home",          "label": "Vente",       "has": True},
        {"icon": "fas fa-key",           "label": "Location",    "has": True},
        {"icon": "fas fa-calculator",    "label": "Estimation",  "has": True},
        {"icon": "fas fa-plus-circle",   "label": "Ajouter bien","has": profile.role == 'seller'},
        {"icon": "fas fa-crown",         "label": "Admin Panel", "has": request.user.is_superuser},
    ]

    return render(request, 'immoanalytics/profile.html', _ctx(request, {
        'profile':    profile,
        'listings':   listings,
        'user_perms': user_perms,
    }))


@login_required(login_url='/immo/login/')
def edit_profile(request):
    profile = _get_or_create_profile(request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            # Mettre à jour User
            u = request.user
            u.first_name = form.cleaned_data.get('first_name', u.first_name)
            u.last_name  = form.cleaned_data.get('last_name',  u.last_name)
            u.email      = form.cleaned_data.get('email',      u.email)
            u.save()
            form.save()
            messages.success(request, "✅ Profil mis à jour.")
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile, initial={
            'first_name': request.user.first_name,
            'last_name':  request.user.last_name,
            'email':      request.user.email,
        })

    return render(request, 'immoanalytics/edit_profile.html', _ctx(request, {
        'form':    form,
        'profile': profile,
    }))


@login_required(login_url='/immo/login/')
@require_POST
def delete_listing_image(request, img_id):
    img = get_object_or_404(ListingImage, pk=img_id, listing__seller=request.user)
    img.delete()
    return JsonResponse({'ok': True})
