from django.contrib import admin
from .models import UserProfile, Listing, ListingImage


class ListingImageInline(admin.TabularInline):
    model  = ListingImage
    extra  = 1
    fields = ['image','caption','is_main','order']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user','phone','role','city','created_at']
    list_filter   = ['role']
    search_fields = ['user__username','user__email','phone']


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display   = ['title','seller','transaction','property_type','price','city','status','created_at']
    list_filter    = ['transaction','property_type','status']
    search_fields  = ['title','city','neighborhood','seller__username']
    inlines        = [ListingImageInline]
    readonly_fields= ['views_count','created_at','updated_at']
