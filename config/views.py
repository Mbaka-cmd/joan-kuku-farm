from django.shortcuts import render
from django.http import JsonResponse

def home(request):
    return JsonResponse({
        'message': 'Welcome to Joan Kuku Farm API',
        'endpoints': {
            'admin': '/admin/',
            'products': '/api/products/',
            'categories': '/api/categories/',
            'orders': '/api/orders/',
        }
    })
