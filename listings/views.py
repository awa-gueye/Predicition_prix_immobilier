"""
listings/views.py
Vues pour : Vente, Location, Ajout annonce, Profil, Modification profil.
Filtres corriges + price_range + tracking recherches pour recommandations.
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


# -- Helpers --
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
    if not p: return "--"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _parse_price_range(price_range):
    """Parse price_range filter like '25-50' into (min, max) in FCFA."""
    if not price_range:
        return None, None
    try:
        parts = price_range.split('-')
        if len(parts) == 2:
            mn = int(parts[0]) * 1_000_000 if parts[0] != '0' else None
            mx = int(parts[1]) * 1_000_000 if parts[1] != '0' else None
            # Handle "250-0" meaning 250M+
            if parts[1] == '0' and parts[0] != '0':
                mn = int(parts[0]) * 1_000_000
                mx = None
            return mn, mx
    except (ValueError, IndexError):
        pass
    return None, None


def _track_search(user, city=None, property_type=None, transaction=None):
    """Track user search for recommendation system."""
    try:
        from .models import SearchHistory
        SearchHistory.objects.create(
            user=user,
            city=city or '',
            property_type=property_type or '',
            transaction=transaction or '',
        )
    except Exception:
        pass


def _get_recommendations(user, transaction='vente', limit=4):
    """Get recommendations based on user search history."""
    try:
        from .models import SearchHistory
        from collections import Counter

        recent = SearchHistory.objects.filter(user=user).order_by('-created_at')[:20]
        if not recent.exists():
            return []

        # Find most searched cities and types
        cities = Counter(s.city for s in recent if s.city)
        types  = Counter(s.property_type for s in recent if s.property_type)

        top_city = cities.most_common(1)[0][0] if cities else None
        top_type = types.most_common(1)[0][0] if types else None

        # Search for matching properties
        results = _scraped_listings(transaction)
        scored = []
        for r in results:
            score = 0
            if top_city and r.get('city') and top_city.lower() in r['city'].lower():
                score += 3
            if top_type and r.get('property_type') and top_type.lower() in r['property_type'].lower():
                score += 2
            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]
    except Exception:
        return []


def _scraped_listings(transaction):
    """
    Charge les annonces scrapees depuis les 4 sources pour vente/location.
    transaction: 'vente' ou 'location'
    """
    from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
                                   LogerDakarProperty, DakarVenteProperty)
    import re

    KW_LOC = ['louer', 'location', 'locat', 'bail', 'mensuel', 'loyer', 'a louer']
    KW_VTE = ['vendre', 'vente', 'achat', 'cession', 'a vendre']

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
            fields = [f for f in ['id', 'title', 'price', 'surface_area', 'bedrooms',
                                  'bathrooms', 'city', 'property_type', 'statut',
                                  'description', 'latitude', 'longitude'] if f in avail]
            qs = list(model.objects.filter(price__isnull=False, price__gt=0).values(*fields)[:3000])
            for row in qs:
                loc = is_location(row)
                if (transaction == 'location' and loc) or (transaction == 'vente' and not loc):
                    results.append({
                        'id':            str(row.get('id', '')),
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
                        'image':         None,
                        'is_scraped':    True,
                    })
        except Exception as e:
            logger.warning(f"_scraped_listings {src_name}: {e}")
            continue

    return results


def _apply_filters(scraped, q='', type_f='', city_f='', price_min=None, price_max=None):
    """Apply filters to scraped listings with robust matching."""
    filtered = scraped

    if q:
        q_lower = q.lower()
        filtered = [s for s in filtered if
            (s.get('title') and q_lower in s['title'].lower()) or
            (s.get('city') and q_lower in s['city'].lower()) or
            (s.get('property_type') and q_lower in s['property_type'].lower()) or
            (s.get('description') and q_lower in s['description'].lower())]

    if type_f:
        type_lower = type_f.lower()
        # Match against both the exact type and partial matches
        filtered = [s for s in filtered if s.get('property_type') and (
            type_lower in s['property_type'].lower() or
            s['property_type'].lower() in type_lower or
            # Also check first 4 chars for fuzzy matching
            type_lower[:4] in s['property_type'].lower()
        )]

    if city_f:
        city_lower = city_f.lower()
        filtered = [s for s in filtered if s.get('city') and (
            city_lower in s['city'].lower() or
            s['city'].lower() in city_lower
        )]

    if price_min is not None:
        filtered = [s for s in filtered if s.get('price', 0) >= price_min]

    if price_max is not None:
        filtered = [s for s in filtered if s.get('price', 0) <= price_max]

    return filtered


# ==========================================
# VENTE
# ==========================================
@login_required(login_url='/immo/login/')
def vente_page(request):
    q           = request.GET.get('q', '').strip()
    type_f      = request.GET.get('type', '')
    city_f      = request.GET.get('city', '')
    sort_f      = request.GET.get('sort', 'recent')
    price_range = request.GET.get('price_range', '')

    price_min, price_max = _parse_price_range(price_range)

    # Track search
    if q or type_f or city_f:
        _track_search(request.user, city=city_f, property_type=type_f, transaction='vente')

    # Seller listings
    seller_qs = Listing.objects.filter(
        transaction='vente', status='active'
    ).prefetch_related('images', 'seller__profile')

    # Scraped listings
    scraped = _scraped_listings('vente')

    # Apply filters to seller listings
    if q:
        seller_qs = seller_qs.filter(
            Q(title__icontains=q) | Q(city__icontains=q) |
            Q(neighborhood__icontains=q) | Q(description__icontains=q))
    if type_f:
        seller_qs = seller_qs.filter(property_type__icontains=type_f)
    if city_f:
        seller_qs = seller_qs.filter(Q(city__icontains=city_f) | Q(neighborhood__icontains=city_f))
    if price_min is not None:
        seller_qs = seller_qs.filter(price__gte=price_min)
    if price_max is not None:
        seller_qs = seller_qs.filter(price__lte=price_max)

    # Sort seller listings
    if sort_f == 'price_asc':    seller_qs = seller_qs.order_by('price')
    elif sort_f == 'price_desc': seller_qs = seller_qs.order_by('-price')
    else:                        seller_qs = seller_qs.order_by('-created_at')

    # Apply filters to scraped (using robust filter function)
    scraped = _apply_filters(scraped, q=q, type_f=type_f, city_f=city_f,
                             price_min=price_min, price_max=price_max)

    # Sort scraped
    if sort_f == 'price_asc':    scraped.sort(key=lambda x: x['price'])
    elif sort_f == 'price_desc': scraped.sort(key=lambda x: x['price'], reverse=True)

    # Pagination
    paginator = Paginator(scraped, 12)
    page_obj  = paginator.get_page(request.GET.get('page_sc', 1))

    # Cities for filter (cached from first 500)
    cities = sorted(set(
        [s['city'] for s in _scraped_listings('vente')[:500] if s.get('city')] +
        list(Listing.objects.filter(transaction='vente', status='active')
             .values_list('city', flat=True).distinct())
    ))

    # Recommendations
    recommendations = _get_recommendations(request.user, 'vente', 4)

    return render(request, 'immoanalytics/vente.html', _ctx(request, {
        'page_title':      'Biens en Vente',
        'seller_listings': list(seller_qs[:20]),
        'scraped_page':    page_obj,
        'scraped_total':   len(scraped),
        'seller_total':    seller_qs.count(),
        'q': q, 'type_f': type_f, 'city_f': city_f, 'sort_f': sort_f,
        'price_range':     price_range,
        'cities':          cities[:80],
        'types':           Listing.TYPE_CHOICES,
        'sort_opts':       [('recent', 'Plus recents'), ('price_asc', 'Prix croissant'), ('price_desc', 'Prix decroissant')],
        'recommendations': recommendations,
    }))


# ==========================================
# LOCATION
# ==========================================
@login_required(login_url='/immo/login/')
def location_page(request):
    q           = request.GET.get('q', '').strip()
    type_f      = request.GET.get('type', '')
    city_f      = request.GET.get('city', '')
    sort_f      = request.GET.get('sort', 'recent')
    price_range = request.GET.get('price_range', '')

    price_min, price_max = _parse_price_range(price_range)

    if q or type_f or city_f:
        _track_search(request.user, city=city_f, property_type=type_f, transaction='location')

    seller_qs = Listing.objects.filter(
        transaction='location', status='active'
    ).prefetch_related('images', 'seller__profile')

    scraped = _scraped_listings('location')

    if q:
        seller_qs = seller_qs.filter(
            Q(title__icontains=q) | Q(city__icontains=q) | Q(description__icontains=q))
    if type_f:
        seller_qs = seller_qs.filter(property_type__icontains=type_f)
    if city_f:
        seller_qs = seller_qs.filter(Q(city__icontains=city_f))
    if price_min is not None:
        seller_qs = seller_qs.filter(price__gte=price_min)
    if price_max is not None:
        seller_qs = seller_qs.filter(price__lte=price_max)

    if sort_f == 'price_asc':    seller_qs = seller_qs.order_by('price');  scraped.sort(key=lambda x: x['price'])
    elif sort_f == 'price_desc': seller_qs = seller_qs.order_by('-price'); scraped.sort(key=lambda x: x['price'], reverse=True)
    else:                        seller_qs = seller_qs.order_by('-created_at')

    scraped = _apply_filters(scraped, q=q, type_f=type_f, city_f=city_f,
                             price_min=price_min, price_max=price_max)

    paginator = Paginator(scraped, 12)
    page_obj  = paginator.get_page(request.GET.get('page_sc', 1))

    cities = sorted(set(
        [s['city'] for s in _scraped_listings('location')[:500] if s.get('city')] +
        list(Listing.objects.filter(transaction='location', status='active')
             .values_list('city', flat=True).distinct())
    ))

    recommendations = _get_recommendations(request.user, 'location', 4)

    return render(request, 'immoanalytics/location.html', _ctx(request, {
        'page_title':      'Biens en Location',
        'seller_listings': list(seller_qs[:20]),
        'scraped_page':    page_obj,
        'scraped_total':   len(scraped),
        'seller_total':    seller_qs.count(),
        'q': q, 'type_f': type_f, 'city_f': city_f, 'sort_f': sort_f,
        'price_range':     price_range,
        'cities':          cities[:80],
        'types':           Listing.TYPE_CHOICES,
        'sort_opts':       [('recent', 'Plus recents'), ('price_asc', 'Prix croissant'), ('price_desc', 'Prix decroissant')],
        'recommendations': recommendations,
    }))


# ==========================================
# DETAIL ANNONCE
# ==========================================
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


# ==========================================
# AJOUT ANNONCE
# ==========================================
@login_required(login_url='/immo/login/')
def add_listing(request):
    profile = _get_or_create_profile(request.user)

    if profile.role != 'seller':
        messages.warning(request,
            "Vous devez etre vendeur pour ajouter une annonce. "
            "Modifiez votre statut dans votre profil.")
        return redirect('edit_profile')

    if request.method == 'POST':
        form = ListingForm(request.POST)
        files = request.FILES.getlist('images')

        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()

            for i, f in enumerate(files[:8]):
                ListingImage.objects.create(
                    listing  = listing,
                    image    = f,
                    is_main  = (i == 0),
                    order    = i,
                )

            messages.success(request, "Votre annonce a ete publiee avec succes !")
            if listing.transaction == 'vente':
                return redirect('vente')
            return redirect('location')
    else:
        form = ListingForm()

    return render(request, 'immoanalytics/add_listing.html', _ctx(request, {
        'form':    form,
        'profile': profile,
    }))


# ==========================================
# MODIFICATION ANNONCE
# ==========================================
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

            messages.success(request, "Annonce mise a jour.")
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
    messages.success(request, "Annonce supprimee.")
    return redirect('my_listings')


@login_required(login_url='/immo/login/')
def my_listings(request):
    listings = Listing.objects.filter(seller=request.user).prefetch_related('images')
    return render(request, 'immoanalytics/my_listings.html', _ctx(request, {
        'listings': listings,
    }))


# ==========================================
# PROFIL
# ==========================================
@login_required(login_url='/immo/login/')
def profile_view(request):
    profile  = _get_or_create_profile(request.user)
    listings = Listing.objects.filter(seller=request.user).prefetch_related('images')[:6]

    user_perms = [
        {"icon": "fas fa-chart-line",    "label": "Dashboard",   "has": True},
        {"icon": "fas fa-home",          "label": "Vente",       "has": True},
        {"icon": "fas fa-key",           "label": "Location",    "has": True},
        {"icon": "fas fa-calculator",    "label": "Estimation",  "has": True},
        {"icon": "fas fa-plus-circle",   "label": "Ajouter bien", "has": profile.role == 'seller'},
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
            u = request.user
            u.first_name = form.cleaned_data.get('first_name', u.first_name)
            u.last_name  = form.cleaned_data.get('last_name',  u.last_name)
            u.email      = form.cleaned_data.get('email',      u.email)
            u.save()
            form.save()
            messages.success(request, "Profil mis a jour avec succes.")
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
