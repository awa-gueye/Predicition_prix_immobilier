from django.urls import path
from . import views

urlpatterns = [
    path('vente/',              views.vente_page,          name='vente'),
    path('location/',           views.location_page,       name='location'),
    path('annonce/<uuid:pk>/',  views.listing_detail,      name='listing_detail'),
    path('ajouter/',            views.add_listing,         name='add_listing'),
    path('modifier/<uuid:pk>/', views.edit_listing,        name='edit_listing'),
    path('supprimer/<uuid:pk>/',views.delete_listing,      name='delete_listing'),
    path('mes-annonces/',       views.my_listings,         name='my_listings'),
    path('profil/',             views.profile_view,        name='profile'),
    path('profil/modifier/',    views.edit_profile,        name='edit_profile'),
    path('image/<int:img_id>/supprimer/', views.delete_listing_image, name='delete_listing_image'),
]
