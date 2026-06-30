from django.contrib import admin
from .models import Payment, MpesaTransaction

admin.site.register(Payment)
admin.site.register(MpesaTransaction)
