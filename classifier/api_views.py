"""
API Views cho Chatbot và thông tin giống chó
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Min, Max, Count

from .models import DogBreed, Dog
from .chatbot_service import get_chatbot


# ==================== CHATBOT API ====================

@csrf_exempt
@require_http_methods(["POST"])
def chatbot_message_api(request):
    """
    API endpoint để gửi tin nhắn cho chatbot
    
    POST /api/chatbot/message/
    Body: {"message": "Xin chào"}
    
    Response:
    {
        "success": true,
        "response": "...",
        "intent": "greeting",
        "data": {...}
    }
    """
    try:
        body = json.loads(request.body)
        message = body.get('message', '').strip()
        
        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message is required'
            }, status=400)
        
        chatbot = get_chatbot()
        result = chatbot.process_message(message)
        
        return JsonResponse({
            'success': True,
            'response': result['response'],
            'intent': result['intent'],
            'data': result['data']
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== BREEDS API ====================

@require_http_methods(["GET"])
def breeds_list_api(request):
    """
    GET /api/breeds/
    
    Lấy danh sách tất cả giống chó
    
    Response:
    {
        "success": true,
        "count": 10,
        "breeds": [
            {
                "id": 1,
                "name": "Golden Retriever",
                "description": "...",
                "characteristics": "...",
                "origin": "Scotland",
                "available_dogs_count": 5
            },
            ...
        ]
    }
    """
    breeds = DogBreed.objects.annotate(
        available_dogs_count=Count('dogs', filter=models.Q(dogs__is_available=True))
    ).order_by('name')
    
    breeds_data = []
    for breed in breeds:
        # Lấy giá min/max
        dogs = Dog.objects.filter(breed=breed, is_available=True)
        price_range = dogs.aggregate(min_price=Min('price'), max_price=Max('price'))
        
        breeds_data.append({
            'id': breed.id,
            'name': breed.name,
            'description': breed.description,
            'characteristics': breed.characteristics,
            'origin': breed.origin,
            'available_dogs_count': breed.available_dogs_count,
            'price_range': {
                'min': float(price_range['min_price']) if price_range['min_price'] else None,
                'max': float(price_range['max_price']) if price_range['max_price'] else None,
            }
        })
    
    return JsonResponse({
        'success': True,
        'count': len(breeds_data),
        'breeds': breeds_data
    })


@require_http_methods(["GET"])
def breed_detail_api(request, breed_id):
    """
    GET /api/breeds/<id>/
    
    Lấy chi tiết một giống chó
    
    Response:
    {
        "success": true,
        "breed": {
            "id": 1,
            "name": "Golden Retriever",
            "description": "...",
            "characteristics": "...",
            "origin": "Scotland",
            "available_dogs": [...]
        }
    }
    """
    try:
        breed = DogBreed.objects.get(id=breed_id)
    except DogBreed.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Breed not found'
        }, status=404)
    
    # Lấy danh sách chó đang bán
    available_dogs = Dog.objects.filter(breed=breed, is_available=True)
    dogs_data = [{
        'id': dog.id,
        'name': dog.name,
        'age_months': dog.age_months,
        'color': dog.color,
        'price': float(dog.price),
        'description': dog.description,
        'image_url': dog.image.url if dog.image else None,
    } for dog in available_dogs]
    
    price_range = available_dogs.aggregate(min_price=Min('price'), max_price=Max('price'))
    
    return JsonResponse({
        'success': True,
        'breed': {
            'id': breed.id,
            'name': breed.name,
            'description': breed.description,
            'characteristics': breed.characteristics,
            'origin': breed.origin,
            'available_dogs_count': available_dogs.count(),
            'price_range': {
                'min': float(price_range['min_price']) if price_range['min_price'] else None,
                'max': float(price_range['max_price']) if price_range['max_price'] else None,
            },
            'available_dogs': dogs_data
        }
    })


# ==================== DOGS API ====================

@require_http_methods(["GET"])
def dogs_list_api(request):
    """
    GET /api/dogs/
    
    Query params:
    - breed_id: Filter theo giống
    - min_price: Giá tối thiểu
    - max_price: Giá tối đa
    - search: Tìm kiếm theo tên
    - limit: Số lượng kết quả (default: 20)
    - offset: Offset cho pagination (default: 0)
    
    Response:
    {
        "success": true,
        "count": 100,
        "dogs": [...]
    }
    """
    dogs = Dog.objects.filter(is_available=True).select_related('breed')
    
    # Filters
    breed_id = request.GET.get('breed_id')
    if breed_id:
        dogs = dogs.filter(breed_id=breed_id)
    
    min_price = request.GET.get('min_price')
    if min_price:
        try:
            dogs = dogs.filter(price__gte=float(min_price))
        except ValueError:
            pass
    
    max_price = request.GET.get('max_price')
    if max_price:
        try:
            dogs = dogs.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    search = request.GET.get('search')
    if search:
        dogs = dogs.filter(
            models.Q(name__icontains=search) | 
            models.Q(breed__name__icontains=search)
        )
    
    # Pagination
    try:
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
    except ValueError:
        limit, offset = 20, 0
    
    total_count = dogs.count()
    dogs = dogs.order_by('-created_at')[offset:offset + limit]
    
    dogs_data = [{
        'id': dog.id,
        'name': dog.name,
        'breed': {
            'id': dog.breed.id,
            'name': dog.breed.name
        },
        'age_months': dog.age_months,
        'color': dog.color,
        'price': float(dog.price),
        'description': dog.description,
        'image_url': dog.image.url if dog.image else None,
        'created_at': dog.created_at.isoformat()
    } for dog in dogs]
    
    return JsonResponse({
        'success': True,
        'count': total_count,
        'limit': limit,
        'offset': offset,
        'dogs': dogs_data
    })


@require_http_methods(["GET"])
def dog_detail_api(request, dog_id):
    """
    GET /api/dogs/<id>/
    
    Lấy chi tiết một con chó
    """
    try:
        dog = Dog.objects.select_related('breed', 'seller').get(id=dog_id)
    except Dog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Dog not found'
        }, status=404)
    
    # Chó liên quan (cùng giống)
    related_dogs = Dog.objects.filter(
        breed=dog.breed, 
        is_available=True
    ).exclude(id=dog_id)[:4]
    
    related_data = [{
        'id': d.id,
        'name': d.name,
        'price': float(d.price),
        'image_url': d.image.url if d.image else None,
    } for d in related_dogs]
    
    return JsonResponse({
        'success': True,
        'dog': {
            'id': dog.id,
            'name': dog.name,
            'breed': {
                'id': dog.breed.id,
                'name': dog.breed.name,
                'description': dog.breed.description,
                'characteristics': dog.breed.characteristics,
                'origin': dog.breed.origin,
            },
            'age_months': dog.age_months,
            'color': dog.color,
            'price': float(dog.price),
            'description': dog.description,
            'image_url': dog.image.url if dog.image else None,
            'is_available': dog.is_available,
            'seller': {
                'id': dog.seller.id,
                'username': dog.seller.username
            },
            'created_at': dog.created_at.isoformat(),
            'related_dogs': related_data
        }
    })


# Import models for Q objects
from django.db import models
